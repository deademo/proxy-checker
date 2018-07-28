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

    @defer.inlineCallbacks
    def request(self, method, data):
        self.logger.debug('Doing request "{}" with params: {}'.format(method, data))
        yield treq.post('http://{host}:{port}/{method}?{data}'.format(
            host=self._host,
            port=self._port,
            method=method,
            data=urllib.parse.urlencode(data),
        ))

    @defer.inlineCallbacks
    def add(self, ip, port):
        yield self.request(
            method='add',
            data={
                'proxy': '{}:{}'.format(ip, port)
            },
        )
