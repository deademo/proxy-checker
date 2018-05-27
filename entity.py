import asyncio
import collections
import concurrent
import logging
import time

import aiohttp
import async_timeout
from tqdm import tqdm

from proxies import proxies
import settings



logging.basicConfig(format='%(asctime)s [%(name)s/%(levelname)s] %(msg)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


class CheckResult:
    def __init__(self, response, proxy, time=None):
        self._response = response
        self.proxy = proxy
        self.time = time
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    @property
    def status_code(self):
        if isinstance(self._response, aiohttp.client_reqrep.ClientResponse):
            return int(self._response.status)
        else:
            return -1

    @property
    def is_expected(self):
        raise NotImlemented()

    def __bool__(self):
        return bool(self.is_expected)

    def __repr__(self):
        return '<CheckResult {} proxy={} time={:0.0f}ms>'.format(self.is_expected, self.proxy, self.time*1000)


class HttpCheckResult(CheckResult):
    def __init__(self, *args, expected_status_code=[200], **kwargs):
        super().__init__(*args, **kwargs)
        if expected_status_code == None:
            self.expected_status_code = None
        elif isinstance(expected_status_code, collections.Iterable):
            self.expected_status_code = [int(x) for x in expected_status_code]
        else:
            self.expected_status_code = int(expected_status_code)

    @property
    def is_expected(self):
        if self.status_code not in self.expected_status_code:
            return False
        return True


class Check:
    def __init__(self, url, timeout=5, expected_result=HttpCheckResult):
        self.url = url
        self.expected_result = expected_result
        self.timeout = timeout
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    async def check(self, proxy):
        possible_exceptions = (
            aiohttp.client_exceptions.ClientProxyConnectionError, 
            concurrent.futures._base.TimeoutError, 
            aiohttp.client_exceptions.ClientOSError,
            aiohttp.client_exceptions.ClientHttpProxyError,
            aiohttp.client_exceptions.ServerDisconnectedError,
            aiohttp.client_exceptions.ClientResponseError
        )

        start_time = time.time()
        self.logger.debug('Started check for {} on {}'.format(proxy, self.url))
        try:
            async with async_timeout.timeout(self.timeout):
                async with aiohttp.ClientSession(conn_timeout=self.timeout, read_timeout=self.timeout) as session:
                    async with session.get(self.url, proxy=str(proxy)) as response:
                        await response.read()
                        result = response
        except possible_exceptions as e:
            result = self.expected_result(e.__class__, proxy)

        delta_time = time.time() - start_time
        self.logger.info('Finished check (is alive: {}) for {} on {} by {:0.3f} s'.format(bool(result), proxy, self.url, delta_time))

        check_result = self.expected_result(result, proxy, time=delta_time)
        proxy.add_check(check_result)

        return check_result


class MultiCheck:
    def __init__(self, *args, timeout=5):
        self.checks = args

        for check in self.checks:
            check.timeout = timeout

    async def check(self, proxy):
        return await asyncio.gather(*[check.check(proxy) for check in self.checks])


class Proxy:
    def __init__(self, host, port, protocol='http', tags={}, recheck_every=None):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.recheck_every = recheck_every
        self.tags = tags
        self.checks = []

    def __str__(self):
        return '{}://{}:{}'.format(self.protocol, self.host, self.port)

    def add_check(self, check):
        self.checks.append(check)

    @property
    def time(self):
        if not self.checks:
            return -1
        return sum([x.time for x in self.checks])/len(self.checks)

    @property
    def alive(self):
        return all(self.checks)