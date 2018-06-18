import asyncio
import json
import logging
import urllib.parse

from aiohttp import web
from aiohttp.web import Response
from sqlalchemy import select, join, text
from sqlalchemy.orm import aliased

import entity
import settings
import sql


class APIException(BaseException):
    pass


class Server(web.Application):
    def __init__(self, *args, db=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.router.add_get('/list', self.list)
        self.router.add_get('/add', self.add)
        self.router.add_get('/remove', self.remove)
        self.router.add_get('/add_check', self.add_check)
        self.router.add_get('/remove_check', self.remove_check)
        self.router.add_get('/add_proxy_check', self.add_proxy_check)
        self.router.add_get('/remove_proxy_check', self.remove_proxy_check)
        if not db:
            self.db = entity.get_session()
        else:
            self.db = db

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    @property
    def _ban_map(self):
        banned_at = {}
        for ban in self.db.execute(sql.GET_BANNED_AT).fetchall():
            ban = dict(ban)
            banned_at.setdefault(ban['id'], [])
            banned_at[ban['id']].append(ban['netloc'])
        return banned_at

    def _get_bool(self, value):
        return value in settings.TRUE_VALUES

    def add_validate(self, request):
        query = {}

        # Proxy checks
        query['proxy'] = request.query.get('proxy')
        if not isinstance(query['proxy'], str):
            raise APIException('Value of attribute \'proxy\' is wrong. Got \'{}\', but expected string'.format(query['proxy']))
        try:
            protocol, host, port = entity.get_proxy_parts(query['proxy'])
        except:
            protocol = host = port = None
        if not host or not port:
            raise APIException('Value of attribute \'proxy\' must be containt host and port of proxy, but \'{}\' got'.format(query['proxy']))

        # Recheck every checks
        query['recheck_every'] = request.query.get('recheck_every')
        if query['recheck_every'] is not None:
            try:
                query['recheck_every'] = int(query['recheck_every'])
            except ValueError:
                raise APIException('Value of attribute \'recheck_every\' must be int or number as string, but \'{}\' got'.format(query['recheck_every']))

        return query

    def list_validate(self, request):
        query = {}

        query['is_alive'] = self._get_bool(request.query.get('is_alive'))
        query['with_banned_at'] = self._get_bool(request.query.get('with_banned_at'))

        return query

    def remove_validate(self, request):
        query = {}
        
        query['id'] = request.query.get('id')
        try:
            query['id'] = int(query['id'])
        except ValueError:
            raise APIException('Value of attribute \'id\' must be int or number as string, but \'{}\' got'.format(query['id']))

        return query

    def add_check_validate(self, request):
        query = {}

        try:
            definition = json.loads(request.query.get('definition'))
        except:
            raise APIException('Value of attribute \'definition\' must be JSON string with check definition')

        query['url'] = definition.get('url')
        if query['url'] is None:
            raise APIException('Value of attribute \'url\' is not set'.format(query['url']))
        if not isinstance(query['url'], str):
            raise APIException('Value of attribute \'url\' must be string, but \'{}\' got'.format(query['url']))

        query['status'] = definition.get('status')
        if query['status'] is not None:
            if not isinstance(query['status'], list):
                raise APIException('Value of attribute \'status\' must be list of int, but \'{}\' got'.format(query['status']))

        query['xpath'] = definition.get('xpath')
        if query['xpath'] is not None:
            if not isinstance(query['xpath'], list):
                raise APIException('Value of attribute \'xpath\' must be list, but \'{}\' got'.format(query['xpath']))
            for xpath_item in query['xpath']:
                if not isinstance(xpath_item, str):
                    raise APIException('Value of attribute list \'xpath\' must be str, but \'{}\' got'.format(xpath_item))
                xpath_item['type'] = 'ban' if xpath_item.get('type') == 'ban' else 'alive'

        query['timeout'] = definition.get('timeout')
        if query['timeout'] is not None:
            try:
                query['timeout'] = int(query['timeout'])
            except ValueError:
                raise APIException('Value of attribute \'timeout\' must be int, but \'{}\' got'.format(query['timeout']))

        return query

    def remove_check_validate(self, request):
        query = {}

        query['id'] = request.query.get('id')
        try:
            query['id'] = int(query['id'])
        except ValueError:
            raise APIException('Value of attribute \'id\' must be intstring, but \'{}\' got'.format(query['id']))

        return query

    def add_proxy_check_validate(self, request):
        query = {}

        query['proxy_id'] = request.query.get('proxy_id')
        try:
            query['proxy_id'] = int(query['proxy_id'])
        except ValueError:
            raise APIException('Value of attribute \'proxy_id\' must be intstring, but \'{}\' got'.format(query['proxy_id']))

        query['check_id'] = request.query.get('check_id')
        try:
            query['check_id'] = int(query['check_id'])
        except ValueError:
            raise APIException('Value of attribute \'check_id\' must be intstring, but \'{}\' got'.format(query['check_id']))

        return query

    def remove_proxy_check_validate(self, request):
        query = {}

        query['proxy_id'] = request.query.get('proxy_id')
        try:
            query['proxy_id'] = int(query['proxy_id'])
        except ValueError:
            raise APIException('Value of attribute \'proxy_id\' must be intstring, but \'{}\' got'.format(query['proxy_id']))

        query['check_id'] = request.query.get('check_id')
        try:
            query['check_id'] = int(query['check_id'])
        except ValueError:
            raise APIException('Value of attribute \'check_id\' must be intstring, but \'{}\' got'.format(query['check_id']))

        return query

    async def add(self, request):
        try:
            query = self.add_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))

        proxy = entity.parse_proxy_string(query['proxy'])
        proxy.recheck_every = query['recheck_every']

        self.db.add(proxy)
        self.db.commit()

        return Response(text=json.dumps({'result': 'ok', 'error': False}))

    async def list(self, request):
        try:
            filters = self.list_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))

        if filters.get('alive_only'):
            query = text(sql.GET_ALIVE_PROXIES)
        else:
            query = select([entity.Proxy])
        proxies = self.db.execute(query).fetchall()

        result = []
        banned_at = self._ban_map
        for proxy in proxies:
            b = {}
            b['id'] = proxy['id']
            b['proxy'] = '{}://{}:{}'.format(proxy['protocol'], proxy['host'], proxy['port'])
            b['banned_at'] = banned_at.get(proxy['id'], [])
            result.append(b)

        return Response(text=json.dumps({'result': result, 'error': False}, default=entity.serializer))

    async def remove(self, request):
        try:
            query = self.remove_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))

        self.db.query(entity.Proxy).filter(entity.Proxy.id == query['id']).delete()
        self.db.commit()

        result = {'result': 'ok', 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def add_check(self, request):
        try:
            query = self.add_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))



        result = {'result': 'ok', 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def remove_check(self, request):
        try:
            query = self.remove_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))

        result = {'result': 'ok', 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def add_proxy_check(self, request):
        try:
            query = self.add_proxy_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))

        result = {'result': 'ok', 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def remove_proxy_check(self, request):
        try:
            query = self.remove_proxy_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))

        result = {'result': 'ok', 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))


def main():
    server = Server()
    web.run_app(server, host=settings.SERVER_HOST, port=settings.SERVER_PORT)


if __name__ == '__main__':
    main()
