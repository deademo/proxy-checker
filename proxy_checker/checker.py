import asyncio
import concurrent
import datetime
import logging
import time

import aiohttp
import aiosocksy
from aiosocksy.connector import ProxyConnector, ProxyClientRequest
import async_timeout
import lxml.html

import xpath_check
import settings
from utils import random_session



class Checker:
    def __init__(self, check, check_result_cls):
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)
        self._check = check
        self._check_result_cls = check_result_cls

    async def check(self, proxy):
        possible_exceptions = (
            aiohttp.client_exceptions.ClientProxyConnectionError, 
            concurrent.futures._base.TimeoutError, 
            aiohttp.client_exceptions.ClientOSError,
            aiohttp.client_exceptions.ClientHttpProxyError,
            aiohttp.client_exceptions.ServerDisconnectedError,
            aiohttp.client_exceptions.ClientResponseError,
            aiosocksy.errors.SocksError,
            aiohttp.client_exceptions.InvalidURL,
            aiohttp.client_exceptions.ClientPayloadError
        )

        start_time = time.time()

        try:
            async with async_timeout.timeout(self._check.timeout):
                async with aiohttp.ClientSession(connector=ProxyConnector(verify_ssl=False), request_class=ProxyClientRequest, conn_timeout=self._check.timeout, read_timeout=self._check.timeout) as session:
                    async with session.get(self._check.url, proxy=str(proxy), headers=random_session()['headers']) as response:
                        content = await response.read()
                        result = response
        except possible_exceptions as e:
            result = e
        delta_time = time.time() - start_time

        is_passed = True
        is_banned = False
        if isinstance(result, aiohttp.client_reqrep.ClientResponse):
            if self._check.check_xpath is not None:
                any_xpath_worked = False
                try:
                    doc = lxml.html.fromstring(content)
                    for xpath in self._check.check_xpath:
                        xpath_result = doc.xpath(xpath)
                        if xpath_result:
                            any_xpath_worked = True
                        if xpath_result and isinstance(xpath, xpath_check.BanXPathCheck):
                            is_banned = True
                except (lxml.etree.ParserError, lxml.etree.XMLSyntaxError):
                    pass
                if not any_xpath_worked:
                    is_passed = False

                    # self.logger.debug('No any xpath worked for proxy {} on url {} ({}):\n{}'.format(proxy, self._check.url, ", ".join(self.check_xpath), content.decode(errors='ignore')))

            if self._check.status and int(result.status) not in self._check.status:
                self.logger.debug('{} not passed status code check on {}. {} got, but {} expected'.format(proxy, self._check.url, result.status, self._check.status))
                is_passed = False
        else:
            is_passed = False

        if isinstance(result, aiohttp.client_reqrep.ClientResponse):
            status = int(result.status)
        else:
            status = None

        check_result = self._check_result_cls()
        check_result.proxy = proxy
        check_result.is_passed = is_passed
        check_result.is_banned = is_banned
        check_result.check = self
        check_result.time = delta_time
        check_result.done_at = datetime.datetime.utcnow()
        check_result.status = status
        if isinstance(result, BaseException):
            check_result.error = str(result)
        proxy.add_check(check_result)

        error = ''
        if isinstance(result, BaseException):
            error = ', error: {}'.format(str(result))
        self.logger.debug('Finished check (is passed: {}) for {} on {} by {:0.3f} s{}'.format(is_passed, proxy, self._check.url, delta_time, error))
        return check_result


class MultiCheck:
    def __init__(self, *args):
        self.checks = args

    async def check(self, proxy):
        return await asyncio.gather(*[check.check(proxy) for check in self.checks])
