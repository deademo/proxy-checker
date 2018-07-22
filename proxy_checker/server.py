import asyncio
import argparse
import json
import logging
import urllib.parse

from aiohttp import web
from aiohttp.web import Response
from sqlalchemy import select, join, text
from sqlalchemy.orm import aliased

import settings
settings.DB_MODE = 'gino'

import entity
from manager import Manager
import sql
from worker import Worker




class APIException(BaseException):
    pass


class Server(web.Application):
    def __init__(self, *args, db=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.router.add_get('/list', self.list)
        self.router.add_get('/add', self.add)
        self.router.add_get('/remove', self.remove)
        self.router.add_get('/add_check', self.add_check)
        self.router.add_get('/list_check', self.list_check)
        self.router.add_get('/remove_check', self.remove_check)
        self.router.add_get('/add_proxy_check', self.add_proxy_check)
        self.router.add_get('/remove_proxy_check', self.remove_proxy_check)
        if not db:
            self.db = entity.get_session()
        else:
            self.db = db

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    async def close(self):
        self.db.close()

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

    def _response(self, data):
        return Response(text=json.dumps(data, default=entity.serializer))

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
            raise APIException('Value of attribute \'proxy\' should be containt host and port of proxy, but \'{}\' got'.format(query['proxy']))

        # Recheck every checks
        query['recheck_every'] = request.query.get('recheck_every')
        if query['recheck_every'] is not None:
            try:
                query['recheck_every'] = int(query['recheck_every'])
            except ValueError:
                raise APIException('Value of attribute \'recheck_every\' should be int or number as string, but \'{}\' got'.format(query['recheck_every']))

        return query

    def list_validate(self, request):
        query = {}

        for key in request.query.keys():
            if key not in ('is_alive', ):
                raise APIException('Attribute \'{}\' is not allowed in \'list\' method'.format(key))

        query['is_alive'] = self._get_bool(request.query.get('is_alive'))

        return query

    def remove_validate(self, request):
        query = {}
        
        for key in request.query.keys():
            if key not in ('id', ):
                raise APIException('Attribute \'{}\' is not allowed in \'remove\' method'.format(key))

        query['id'] = request.query.get('id')
        try:
            query['id'] = int(query['id'])
        except ValueError:
            raise APIException('Value of attribute \'id\' should be int or number as string, but \'{}\' got'.format(query['id']))

        return query

    def add_check_validate(self, request):
        query = {}

        for key in request.query.keys():
            if key not in ('definition', ):
                raise APIException('Attribute \'{}\' is not allowed in \'add_check\' method'.format(key))

        definition = request.query.get('definition')

        error = False
        if isinstance(definition, str):
            try:
                definition = json.loads(definition)
            except:
                error = True
        if not isinstance(definition, dict):
            error = True
        if error:
            raise APIException('Value of attribute \'definition\' should be dict or JSON string with dict of check definition. Got: \'{}\''.format(definition))

        for key in query.keys():
            if key not in ('url', 'status', 'xpath', 'timeout'):
                raise APIException('Attribute \'{}\' is not allowed in check definition'.format(key))

        query['url'] = definition.get('url')
        if query['url'] is None:
            raise APIException('Value of attribute \'url\' is not set'.format(query['url']))
        if not isinstance(query['url'], str):
            raise APIException('Value of attribute \'url\' should be string, but \'{}\' got'.format(query['url']))

        query['status'] = definition.get('status')
        if query['status'] is not None:
            if not isinstance(query['status'], list):
                raise APIException('Value of attribute \'status\' should be list of int, but \'{}\' got'.format(query['status']))
        else:
            del query['status']

        query['xpath'] = definition.get('xpath')
        if query['xpath'] is not None:
            if not isinstance(query['xpath'], list):
                raise APIException('Value of attribute \'xpath\' should be list, but \'{}\' got'.format(query['xpath']))
            for xpath_item in query['xpath']:
                if not isinstance(xpath_item, str):
                    raise APIException('Value of attribute list \'xpath\' should be str, but \'{}\' got'.format(xpath_item))
                xpath_item['type'] = 'ban' if xpath_item.get('type') == 'ban' else 'alive'
        else:
            del query['xpath']

        query['timeout'] = definition.get('timeout')
        if query['timeout'] is not None:
            try:
                query['timeout'] = int(query['timeout'])
            except ValueError:
                raise APIException('Value of attribute \'timeout\' should be int, but \'{}\' got'.format(query['timeout']))
        else:
            del query['timeout']

        return {'definition': query}

    def list_check_validate(self, request):
        query = {}

        for key in request.query.keys():
            if key not in ('id', ):
                raise APIException('Attribute \'{}\' is not allowed in \'list_check\' method'.format(key))

        query['id'] = request.query.get('id')
        try:
            query['id'] = int(query['id'])
        except ValueError:
            raise APIException('Value of attribute \'id\' should be intstring, but \'{}\' got'.format(query['id']))

        return query

    def remove_check_validate(self, request):
        query = {}

        for key in request.query.keys():
            if key not in ('id', ):
                raise APIException('Attribute \'{}\' is not allowed in \'remove_check\' method'.format(key))

        query['id'] = request.query.get('id')
        try:
            query['id'] = int(query['id'])
        except ValueError:
            raise APIException('Value of attribute \'id\' should be intstring, but \'{}\' got'.format(query['id']))

        return query


    def add_proxy_check_validate(self, request):
        query = {}

        query['proxy_id'] = request.query.get('proxy_id')
        try:
            query['proxy_id'] = int(query['proxy_id'])
        except ValueError:
            raise APIException('Value of attribute \'proxy_id\' should be intstring, but \'{}\' got'.format(query['proxy_id']))

        query['check_id'] = request.query.get('check_id')
        try:
            query['check_id'] = int(query['check_id'])
        except ValueError:
            raise APIException('Value of attribute \'check_id\' should be intstring, but \'{}\' got'.format(query['check_id']))

        return query

    def remove_proxy_check_validate(self, request):
        query = {}

        query['proxy_id'] = request.query.get('proxy_id')
        try:
            query['proxy_id'] = int(query['proxy_id'])
        except ValueError:
            raise APIException('Value of attribute \'proxy_id\' should be intstring, but \'{}\' got'.format(query['proxy_id']))

        query['check_id'] = request.query.get('check_id')
        try:
            query['check_id'] = int(query['check_id'])
        except ValueError:
            raise APIException('Value of attribute \'check_id\' should be intstring, but \'{}\' got'.format(query['check_id']))

        return query

    async def add(self, request):
        try:
            query = self.add_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': str(e), 'error': True}))

        proxy = entity.parse_proxy_string(query['proxy'])
        proxy.recheck_every = query['recheck_every']

        self.db.add(proxy)
        self.db.commit()

        return Response(text=json.dumps({'result': {'id': proxy.id}, 'error': False}))

    async def list(self, request):
        try:
            filters = self.list_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': str(e), 'error': True}))

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
            return Response(text=json.dumps({'result': str(e), 'error': True}))

        is_really_removed = self.db.query(entity.Proxy).filter(entity.Proxy.id == query['id']).delete()
        self.db.commit()

        result = {'result': 'ok' if is_really_removed else 'not_exists', 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def add_check(self, request):
        try:
            query = self.add_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': str(e), 'error': True}))

        check = entity.Check(**query['definition'])
        self.db.commit()

        result = {'result': {'id': check.id}, 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def list_check(self, request):
        try:
            query = self.list_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': str(e), 'error': True}))

        check = self.db.query(entity.CheckDefinition).filter(entity.CheckDefinition.id == query['id']).first()
        if not check:
            return self._response({'result': 'not_exists', 'error': True})

        result = {'result': {'id': check.id, 'definition': check.decoded_definition}, 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def remove_check(self, request):
        try:
            query = self.remove_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': str(e), 'error': True}))

        is_really_removed = self.db.query(entity.CheckDefinition).filter(entity.CheckDefinition.id == query['id']).delete()
        self.db.commit()

        result = {'result': 'ok' if is_really_removed else 'not_exists', 'error': False}

        return Response(text=json.dumps(result, default=entity.serializer))

    async def add_proxy_check(self, request):
        try:
            query = self.add_proxy_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': str(e), 'error': True}))

        check = self.db.query(entity.CheckDefinition).filter(entity.CheckDefinition.id == query['check_id']).first()
        if not check:
            return self._response({'result': 'check_not_exists', 'error': True})

        proxy = self.db.query(entity.Proxy).filter(entity.Proxy.id == query['proxy_id']).first()
        if not proxy:
            return self._response({'result': 'proxy_not_exists', 'error': True})

        entity.get_or_create(entity.ProxyCheckDefinition, proxy=proxy, check_definition=check)
        self.db.commit()

        return self._response({'result': 'ok', 'error': False})

    async def remove_proxy_check(self, request):
        try:
            query = self.remove_proxy_check_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': str(e), 'error': True}))

        is_really_removed = self.db.query(entity.ProxyCheckDefinition).filter_by(proxy_id=query['proxy_id'], check_definition_id=query['check_id']).delete()

        return self._response({'result': 'ok' if is_really_removed else 'not_exists', 'error': False})


async def get_server(host, port):
    server = Server()
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    return runner, site, server


async def get_manager():
    manager = Manager()
    return manager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--host', required=False, default=settings.SERVER_HOST)
    parser.add_argument('-p', '--port', required=False, type=int, default=settings.SERVER_PORT)
    args = parser.parse_args()

    worker_count = 1
    concurent_requests = 50

    loop = asyncio.get_event_loop()
    try:
        # Running server
        runner, site, server = loop.run_until_complete(get_server(args.host, args.port))
        asyncio.ensure_future(site.start())
        server.logger.info('Started server on {}:{}'.format(args.host, args.port))

        # Running manager
        manager = loop.run_until_complete(get_manager())
        asyncio.ensure_future(manager.start())

        # Runnning worker(s)
        for i in range(worker_count):
            worker = Worker(
                concurent_requests=concurent_requests
            )
            manager.workers.append(worker)
            asyncio.ensure_future(worker.start())

        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Stopping API server
        loop.run_until_complete(runner.cleanup())
        server.logger.info('Server successfully stopped')

        # Stopping manager
        loop.run_until_complete(manager.stop())
        loop.run_until_complete(manager.wait_stop())


if __name__ == '__main__':
    main()

