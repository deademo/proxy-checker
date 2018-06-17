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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.router.add_get('/list', self.list)
        self.router.add_get('/add', self.add)
        self.router.add_post('/add', self.add)
        self.db = entity.get_session()

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

    def list_validate(self, request):
        query = {}

        query['is_alive'] = self._get_bool(request.query.get('is_alive'))
        query['with_banned_at'] = self._get_bool(request.query.get('with_banned_at'))

        return query

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


    def list(self, request):
        filters = self.list_validate(request)

        if filters.get('alive_only'):
            query = text(sql.GET_ALIVE_PROXIES)
        else:
            query = select([entity.Proxy])
        proxies = self.db.execute(query).fetchall()

        result = []
        banned_at = self._ban_map
        for proxy in proxies:
            b = {}
            b['proxy'] = '{}://{}:{}'.format(proxy['protocol'], proxy['host'], proxy['port'])
            b['banned_at'] = banned_at.get(proxy['id'], [])
            result.append(b)

        return Response(text=json.dumps(result, default=entity.serializer))

    def add(self, request):
        try:
            query = self.add_validate(request)
        except APIException as e:
            return Response(text=json.dumps({'result': 'error', 'error': str(e)}))

        proxy = entity.parse_proxy_string(query['proxy'])
        proxy.recheck_every = query['recheck_every']

        session = entity.get_session()
        session.add(proxy)
        session.commit()

        return Response(text=json.dumps({'result': 'ok', 'error': False}))


def main():
    server = Server()
    web.run_app(server, host=settings.SERVER_HOST, port=settings.SERVER_PORT)


if __name__ == '__main__':
    main()
