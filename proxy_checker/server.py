import asyncio
import json
import logging

from aiohttp import web
from aiohttp.web import Response
from sqlalchemy import select, join, text
from sqlalchemy.orm import aliased

import entity
import settings
import sql


class Server(web.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.router.add_get('/list', self.list)
        self.router.add_post('/list', self.list)
        self.db = entity.get_session()

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    def list_validate(self, request):
        true_values = ('1', 'true', 'True', 'on')

        query = {}
        query['is_alive'] = request.query.get('is_alive') in true_values
        query['with_banned_at'] = request.query.get('with_banned_at') in true_values

        return query

    @property
    def _ban_map(self):
        banned_at = {}
        for ban in self.db.execute(sql.GET_BANNED_AT).fetchall():
            ban = dict(ban)
            banned_at.setdefault(ban['id'], [])
            banned_at[ban['id']].append(ban['netloc'])
        return banned_at

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


def main():
    

    server = Server()
    web.run_app(server, host=settings.SERVER_HOST, port=settings.SERVER_PORT)

    import time
    s = time.time()
    result = server.list({'alive_only': True, 'with_banned_at': True})
    print(result)
    print(len(result))
    print('Finished for: {:0.2f}'.format(time.time() - s))


if __name__ == '__main__':
    main()
