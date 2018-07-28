import json
import logging
import urllib.parse

import treq
from twisted.internet import defer


class ProxyCheckerClient:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self.logger = logging.getLogger('ProxyCheckerClient')
        self.logger.info('Initialized client for proxy checker on {}:{}'.format(self._host, self._port))

    def request(self, method, data):
        self.logger.debug('Doing request "{}" with params: {}'.format(method, data))
        return treq.post('http://{host}:{port}/{method}?{data}'.format(
            host=self._host,
            port=self._port,
            method=method,
            data=urllib.parse.urlencode(data),
        ))

    @defer.inlineCallbacks
    def add(self, ip, port, checks=None):
        defer = self.request(
            method='add',
            data={
                'proxy': '{}:{}'.format(ip, port),
            }
        )
        if checks:
            defer.addCallback(lambda x: self.add_proxy_check_callback(x, checks))
        yield defer

        return True

    @defer.inlineCallbacks
    def add_proxy_check_callback(self, response, checks):
        body = yield response.text()
        data = json.loads(body)
        if data.get('error') == True:
            self.logger.warning('Got error: {}'.format(data))
            return False
        proxy_id = data['result']['id']

        checks = [] or checks
        for check_name in checks:
            yield self.request(
                method='add_proxy_check',
                data={
                    'proxy_id': proxy_id,
                    'check_name': check_name
                }
            )