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
    db_file_counter = 0

    async def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.db_file_counter += 1
        self.db_file_path = 'test{}.db'.format(self.db_file_counter)
        self.db_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.db_file_path)
        self.database_url = entity.get_sqlite_database_url(self.db_file_path)
        entity.create_models(engine=entity.get_engine(database_url=self.database_url))
        self.app = server.Server(db=entity.get_session(database_url=self.database_url))
        self.app.logger.propagate = False

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self._host = '127.0.0.1'
        self._port = 7766
        await web.TCPSite(self.runner, self._host, self._port).start()

        self.session = aiohttp.ClientSession()

    async def tearDown(self):
        entity.get_session(database_url=self.database_url).close()
        try:
            os.remove(self.db_file_path)
        except:
            pass
        await self.app.close()
        await self.runner.cleanup()
        await self.session.close()

    async def request(self, method, params={}, http_method='get'):
        url = 'http://{}:{}/{}?{}'.format(self._host, self._port, method, urllib.parse.urlencode(params))
        request_method = getattr(self.session, http_method)
        async with request_method(url) as request:
            content = await request.text()
            try:
                return json.loads(content)
            except:
                print('Got error with deserializing response json. Response:\n{}'.format(content))

    async def test_server_works(self):
        result = await self.request('list', http_method='post')
        self.assertEqual(isinstance(result, dict), True)

    async def test_list_empty(self):
        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [], 'error': False})
 
    async def test_list_wrong_parameter(self):
        result = await self.request('list', {'some_one_else': 123}, http_method='post')
        self.assertEqual(result['error'], True)

    async def test_add_proxy(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

    async def test_list(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'checks': [], 'is_passed': False, 'recheck_every': self.app.recheck_every, 'proxy': 'http://google.com:3333'}], 'error': False})   

    async def test_list_recheck_every(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333', 'recheck_every': 123}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'checks': [], 'is_passed': False, 'recheck_every': 123, 'proxy': 'http://google.com:3333'}], 'error': False})

    async def test_list_recheck_every_default(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'checks': [], 'is_passed': False, 'recheck_every': self.app.recheck_every, 'proxy': 'http://google.com:3333'}], 'error': False})

    async def test_list_recheck_every_disable(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333', 'recheck_every': False}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'checks': [], 'is_passed': False, 'recheck_every': None, 'proxy': 'http://google.com:3333'}], 'error': False})

    async def test_add_proxy_wrong_parameter(self):
        result = await self.request('add', {'asfd': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result['error'], True)

    async def test_remove_proxy(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('remove', {'id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [], 'error': False})

    async def test_remove_not_exists_proxy(self):
        result = await self.request('remove', {'id': 123}, http_method='post')
        self.assertEqual(result, {'result': 'not_exists', 'error': False})

    async def test_remove_proxy_wrong_parameter(self):
        result = await self.request('remove', {'1': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result['error'], True)

    async def test_add_check_definition(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {'definition': json.dumps(definition)}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})


    async def test_add_check_definition_by_name(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {
                'definition': json.dumps(definition),
                'name': 'test123'
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

    async def test_add_check_definition_dublicate(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {'definition': json.dumps(definition)}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add_check', {'definition': json.dumps(definition)}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

    async def test_add_check_definition_dublicate_by_name(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {
                'definition': json.dumps(definition),
                'name': 'test123',
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

        definition = {'url': 'http://google123.com'}
        result = await self.request('add_check', {
                'definition': json.dumps(definition),
                'name': 'test123',
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': 'Check already exists with same definition or name', 'error': True})

    async def test_list_check_definition(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {'definition': json.dumps(definition)}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list_check', {'id': 1}, http_method='post')
        self.assertEqual(result, {'result': {
                'definition': {
                    'check_xpath': [],
                    'status': [200],
                    'timeout': 2,
                    'url': 'http://google.com'
                },
                'id': 1
            }, 'error': False})

    async def test_list_check_definition_by_name(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {
                'definition': json.dumps(definition),
                'name': 'test123'
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

        result = await self.request('list_check', {'name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': {
                'definition': {
                    'check_xpath': [],
                    'status': [200],
                    'timeout': 2,
                    'url': 'http://google.com'
                },
                'id': 1
            }, 'error': False})

    async def test_list_check_definition_by_name_and_id(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {
                'definition': json.dumps(definition),
                'name': 'test123'
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

        result = await self.request('list_check', {'name': 'test123', 'id': 1}, http_method='post')
        self.assertEqual(result, {
            'result': '"id" and "name" provided. To identify check should be only one of these keys.', 
            'error': True
        })

    async def test_list_check_definition_not_exists(self):
        result = await self.request('list_check', {'id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'not_exists', 'error': True})

    async def test_list_check_definition_not_exists_by_name(self):
        result = await self.request('list_check', {'name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'not_exists', 'error': True})

    async def test_list_check_definition_no_identifier(self):
        result = await self.request('list_check', {}, http_method='post')
        self.assertEqual(result, {
            'error': True,
            'result': 'No "id" and "name" provided. To identify check should be one of these keys.'
        })

    async def test_remove_check_definition(self):
        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {
                'definition': json.dumps(definition),
                'name': 'test123',
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

        result = await self.request('remove_check', {'name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

    async def test_remove_check_definition_not_exists(self):
        result = await self.request('remove_check', {'id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'not_exists', 'error': False})

    async def test_remove_check_definition_not_exists_by_name(self):
        result = await self.request('remove_check', {'name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'not_exists', 'error': False})

    async def test_remove_check_definition_by_name_and_id(self):
        result = await self.request('remove_check', {'name': 'test123', 'id': 123}, http_method='post')
        self.assertEqual(result, {
            'error': True,
            'result': '"id" and "name" provided. To identify check should be only one of these keys.'
        })

    async def test_remove_check_definition_no_identifier(self):
        result = await self.request('remove_check', {}, http_method='post')
        self.assertEqual(result, {
            'error': True,
            'result': 'No "id" and "name" provided. To identify check should be one of these keys.'
        })

    async def test_add_proxy_check(self):
        result = await self.request('add_check', {'definition': json.dumps({'url': 'http://google.com'})}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'checks': [{'id': 1, 'name': None}], 'is_passed': False, 'recheck_every': self.app.recheck_every, 'proxy': 'http://google.com:3333'}], 'error': False})

    async def test_add_proxy_check_proxy_no_identifier(self):
        result = await self.request('add_proxy_check', {'check_id': 1}, http_method='post')
        self.assertEqual(result, {
            'error': True,
            'result': "Value of attribute 'proxy_id' should be int, but 'None' got"
        })

    async def test_add_proxy_check_check_no_identifier(self):
        result = await self.request('add_proxy_check', {'proxy_id': 1}, http_method='post')
        self.assertEqual(result, {
            'error': True,
            'result': 'No "check_id" and "check_name" provided. To identify check should be one of these keys.'
        })

    async def test_add_proxy_check_by_name(self):
        result = await self.request('add_check', {
                'definition': json.dumps({'url': 'http://google.com'}),
                'name': 'test123'
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [{'banned_at': [], 'id': 1, 'checks': [{'id': 1, 'name': 'test123'}], 'is_passed': False, 'recheck_every': self.app.recheck_every, 'proxy': 'http://google.com:3333'}], 'error': False})

    async def test_add_proxy_check_by_name_and_id(self):
        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_id': 1, 'check_name': 'test123'}, http_method='post')
        self.assertEqual(result, {
            'error': True,
            'result': '"check_id" and "check_name" provided. To identify check should be only one of these keys.'
        })

    async def test_add_proxy_check_dublicate(self):
        result = await self.request('add_check', {'definition': json.dumps({'url': 'http://google.com'})}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

    async def test_add_proxy_check_dublicate_by_name(self):
        result = await self.request('add_check', {
                'definition': json.dumps({'url': 'http://google.com'}),
                'name': 'test123'
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

    async def test_remove_proxy_check_by_id(self):
        result = await self.request('add_check', {'definition': json.dumps({'url': 'http://google.com'})}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('remove_proxy_check', {'proxy_id': 1, 'check_id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})        

    async def test_remove_proxy_check_by_name(self):
        result = await self.request('add_check', {
                'definition': json.dumps({'url': 'http://google.com'}),
                'name': 'test123'
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1, 'name': 'test123'}, 'error': False})

        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('remove_proxy_check', {'proxy_id': 1, 'check_name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

    async def test_remove_proxy_check_not_exists(self):
        result = await self.request('remove_proxy_check', {'proxy_id': 1, 'check_name': 'test123'}, http_method='post')
        self.assertEqual(result, {'result': 'not_exists', 'error': False})        

    async def test_remove_proxy_check_proxy_no_identifier(self):
        result = await self.request('remove_proxy_check', {'check_id': 1}, http_method='post')
        self.assertEqual(result, {
            'error': True,
            'result': "Value of attribute 'proxy_id' should be int, but 'None' got"
        })

    async def test_remove_proxy_check_by_name_and_id(self):
        result = await self.request('remove_proxy_check', {'proxy_id': 1, 'check_name': 'test123', 'check_id': 1}, http_method='post')
        self.assertEqual(result, {
            'error': True, 
            'result': '"check_id" and "check_name" provided. To identify check should be only one of these keys.'
        })

    async def test_remove_proxy_check_check_no_identifier(self):
        result = await self.request('remove_proxy_check', {'proxy_id': 1}, http_method='post')
        self.assertEqual(result, {
            'error': True, 
            'result': 'No "check_id" and "check_name" provided. To identify check should be one of these keys.'
        })

    async def test_remove_proxy_with_checks(self):
        result = await self.request('add', {'proxy': 'http://google.com:3333'}, http_method='post')
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        definition = {'url': 'http://google.com'}
        result = await self.request('add_check', {
                'definition': json.dumps(definition)
            }, 
            http_method='post'
        )
        self.assertEqual(result, {'result': {'id': 1}, 'error': False})

        result = await self.request('list_check', {'id': 1}, http_method='post')
        self.assertEqual(result, {'result': {
                'definition': {
                    'check_xpath': [],
                    'status': [200],
                    'timeout': 2,
                    'url': 'http://google.com'
                },
                'id': 1
            }, 'error': False})

        result = await self.request('add_proxy_check', {'proxy_id': 1, 'check_id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {
            'result': [{
                'banned_at': [],
                'checks': [{'id': 1, 'name': None}],
                'id': 1,
                'is_passed': False,
                'proxy': 'http://google.com:3333',
                'recheck_every': self.app.recheck_every
            }],
            'error': False})

        result = await self.request('remove', {'id': 1}, http_method='post')
        self.assertEqual(result, {'result': 'ok', 'error': False})

        result = await self.request('list', http_method='post')
        self.assertEqual(result, {'result': [], 'error': False})

    async def test_async_request(self):
        result = await asyncio.gather(*[
            self.request('list_check', {'id': 1}),
            self.request('list_check', {'id': 1}),
            self.request('list_check', {'id': 1}),
        ])
        self.assertEqual(result, [
            {'result': 'not_exists', 'error': True},
            {'result': 'not_exists', 'error': True},
            {'result': 'not_exists', 'error': True},
        ])
