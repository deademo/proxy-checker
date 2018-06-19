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

        self._host = '127.0.0.1'
        self._port = 7766
        await web.TCPSite(self.runner, self._host, self._port).start()

        self.session = aiohttp.ClientSession()

    async def tearDown(self):
        entity.get_session(db_file_name=self.db_file_path).close()
        try:
            os.remove(self.db_file_path)
        except:
            pass
        await self.app.close()
        await self.runner.cleanup()
        await self.session.close()

    async def request(self, method, params={}):
        url = 'http://{}:{}/{}?{}'.format(self._host, self._port, method, urllib.parse.urlencode(params))
        async with self.session.get(url) as request:
            content = await request.text()
            return json.loads(content)

    async def test_server_works(self):
        result = await self.request('list')
        self.assertEqual(isinstance(result, dict), True)

    async def test_list_empty(self):
        result = await self.request('list')
        self.assertEqual(result, {'result': [], 'error': False})
 
    async def test_list_wrong_parameter(self):
        result = await self.request('list', {'some_one_else': 123})
        self.assertEqual(result['error'], True)

    async def test_add_proxy(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'})
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

    async def test_add_proxy_and_list(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'})
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'proxy': 'http://google.com:3333'}], 'error': False})   

    async def test_add_proxy_wrong_parameter(self):
        result = await self.request('add', {'asfd': 'http://google.com:3333'})
        self.assertEqual(result['error'], True)

    async def test_remove_proxy(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'})
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'proxy': 'http://google.com:3333'}], 'error': False})

        result = await self.request('remove', {'id': 1})
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('list')
        self.assertEqual(result, {'result': [], 'error': False})

    async def test_remove_not_exists_proxy(self):
        result = await self.request('remove', {'id': 123})
        self.assertEqual(result, {'result': 'not_exists', 'error': False})

    async def test_remove_proxy_wrong_parameter(self):
        result = await self.request('remove', {'1': 'http://google.com:3333'})
        self.assertEqual(result['error'], True)

    async def test_add_check_definition(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {'definition': json.dumps(definition)})
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})
