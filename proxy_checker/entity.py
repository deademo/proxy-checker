import asyncio
import collections
import concurrent
import logging
import random
import time
import urllib.parse

import aiohttp
import async_timeout
import lxml.html
from tqdm import tqdm

from proxies import proxies
import session_sets
import settings
import xpath_check



logging.basicConfig(format='%(asctime)s [%(name)s/%(levelname)s] %(msg)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


def random_session():
    return random.choice(session_sets.sessions)


class CheckResult:
    def __init__(self, proxy, is_passed, is_banned, check=None, status=None, time=None):
        self.proxy = proxy
        self.is_passed = is_passed
        self.is_banned = is_banned
        self.check = check
        self.status = status
        self.time = time
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    @property
    def status_code(self):
        if isinstance(self._response, aiohttp.client_reqrep.ClientResponse):
            return int(self._response.status)
        else:
            return -1

    def __bool__(self):
        return bool(self.is_passed)

    def __repr__(self):
        return '<{} {} proxy={} time={:0.0f}ms>'.format(__class__.__name__, self.is_passed, self.proxy, self.time*1000)


class Check:
    def __init__(self, url, status=None, xpath=None, timeout=5):
        self.url = url
        self.timeout = timeout
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

        if status is None:
            self.expected_status_code = None
        elif isinstance(status, collections.Iterable) and not isinstance(status, str):
            self.expected_status_code = [int(x) for x in status]
        else:
            self.expected_status_code = [int(status)]

        self.check_xpath = [xpath] if isinstance(xpath, str) else xpath

    @property
    def domain(self):
        return urllib.parse.urlparse(self.url).netloc

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
        try:
            async with async_timeout.timeout(self.timeout):
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False), conn_timeout=self.timeout, read_timeout=self.timeout) as session:
                    async with session.get(self.url, proxy=str(proxy), headers=random_session()['headers']) as response:
                        content = await response.read()
                        result = response
        except possible_exceptions as e:
            result = e
        delta_time = time.time() - start_time

        is_passed = True
        is_banned = False
        if isinstance(result, aiohttp.client_reqrep.ClientResponse):
            if self.check_xpath is not None:
                any_xpath_worked = False
                try:
                    doc = lxml.html.fromstring(content)
                    for xpath in self.check_xpath:
                        xpath_result = doc.xpath(xpath)
                        if xpath_result:
                            any_xpath_worked = True
                        if xpath_result and isinstance(xpath, xpath_check.BanXPathCheck):
                            is_banned = True
                except (lxml.etree.ParserError, lxml.etree.XMLSyntaxError):
                    pass
                if not any_xpath_worked:
                    is_passed = False

            if self.expected_status_code and int(result.status) not in self.expected_status_code:
                self.logger.debug('{} not passed status code check on {}. {} got, but {} expected'.format(proxy, self.url, result.status, self.expected_status_code))
                is_passed = False
        else:
            self.logger.debug('{} got {} error on {}'.format(proxy, type(result), self.url))
            is_passed = False

        if isinstance(result, aiohttp.client_reqrep.ClientResponse):
            status = int(result.status)
        else:
            status = None

        check_result = CheckResult(proxy, is_passed, is_banned, check=self, time=delta_time, status=status)
        proxy.add_check(check_result)

        self.logger.debug('Finished check (is passed: {}) for {} on {} by {:0.3f} s'.format(is_passed, proxy, self.url, delta_time))
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
    def is_alive(self):
        return all(self.checks)

    @property
    def is_banned_somewhere(self):
        return any([x.is_banned for x in self.checks])

    @property
    def banned_on(self):
        return [x.check.domain for x in self.checks if x.is_banned]
