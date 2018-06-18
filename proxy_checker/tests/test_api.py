import asyncio
import json
import os
import time
import urllib.parse

import aiohttp
from aiohttp import web
import asynctest

import entity
import server


class TestAPI(asynctest.TestCase):
    async def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.db_file_path = 'test{}.db'.format(int(time.time()))
        self.db_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.db_file_path)
        entity.create_models(engine=entity.get_engine(db_file_name=self.db_file_path))
        self.app = server.Server(db=entity.get_session(db_file_name=self.db_file_path))

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self._host = 'localhost'
        self._port = 7766
        await web.TCPSite(self.runner, self._host, self._port).start()

        self.session = aiohttp.ClientSession()

    async def tearDown(self):
        await self.runner.cleanup()
        await self.session.close()
        entity.get_session(db_file_name=self.db_file_path).close()
        os.remove(self.db_file_path)


    async def request(self, method, params={}):
        url = 'http://{}:{}/{}?{}'.format(self._host, self._port, method, urllib.parse.urlencode(params))
        async with self.session.get(url) as request:
            content = await request.text()
            return json.loads(content)

    async def test_server_works(self):
        result = await self.request('list')
        self.assertEqual(isinstance(result, dict), True)
