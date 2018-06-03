import asyncio
import collections
import concurrent
import json
import logging
import random
import time
import urllib.parse

import aiohttp
import async_timeout
import aiosocksy
from aiosocksy.connector import ProxyConnector, ProxyClientRequest
import lxml.html
from sqlalchemy import create_engine
from sqlalchemy import (Column, Boolean, Integer, String, ForeignKey, 
                        UniqueConstraint)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from tqdm import tqdm

from proxies import proxies
import session_sets
import settings
import xpath_check


Base = declarative_base()

logging.basicConfig(format='%(asctime)s [%(name)s/%(levelname)s] %(msg)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


def random_session():
    return random.choice(session_sets.sessions)


class Proxy(Base):
    __tablename__ = 'proxy'

    id = Column(Integer, primary_key=True)
    host = Column(String)
    port = Column(String)
    protocol = Column(String)
    recheck_every = Column(Integer)

    __table_args__ = (UniqueConstraint('host', 'port', 'protocol', name='proxy_uix'), )

    def __str__(self):
        return self.make_proxy_string()

    def __repr__(self):
        return str(self)

    def make_proxy_string(self, protocol=None):
        protocol = protocol or self.protocol or 'http'
        return '{}://{}:{}'.format(protocol, self.host, self.port)

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


class CheckDefinition(Base):
    __tablename__ = 'check_definition'

    id = Column(Integer, primary_key=True)
    definition = Column(String)

    __table_args__ = (UniqueConstraint('definition', name='check_definition_uix'), )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._decoded_definition = None
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    @property
    def decoded_definition(self):
        if not self._decoded_definition:
            self._decoded_definition = json.loads(self.definition)
        return self._decoded_definition

    @decoded_definition.setter
    def decoded_definition(self, value):
        self._decoded_definition = value
        self.definition = json.dumps(value)
    
    @property
    def timeout(self):
        return self.decoded_definition.get('timeout')

    @timeout.setter
    def timeout(self, value):
        definition = self.decoded_definition
        definition['timeout'] = value
        self.decoded_definition = definition

    @property
    def url(self):
        return self.decoded_definition.get('url')

    @property
    def status(self):
        return self.decoded_definition.get('status')

    @property
    def domain(self):
        return urllib.parse.urlparse(self.url).netloc

    @property
    def check_xpath(self):
        xpath_list = self.decoded_definition.get('check_xpath')
        if not xpath_list:
            return []
        buffer_xpath_list = []
        for xpath in xpath_list:
            if xpath['type'] == 'ban':
                xpath_class = xpath_check.BanXPathCheck
            else:
                xpath_class = xpath_check.XPathCheck
            buffer_xpath_list.append(xpath_class(xpath['xpath']))

        return buffer_xpath_list

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
            async with async_timeout.timeout(self.timeout):
                async with aiohttp.ClientSession(connector=ProxyConnector(), request_class=ProxyClientRequest, conn_timeout=self.timeout, read_timeout=self.timeout) as session:
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

                    # self.logger.debug('No any xpath worked for proxy {} on url {} ({}):\n{}'.format(proxy, self.url, ", ".join(self.check_xpath), content.decode(errors='ignore')))

            if self.status and int(result.status) not in self.status:
                self.logger.debug('{} not passed status code check on {}. {} got, but {} expected'.format(proxy, self.url, result.status, self.status))
                is_passed = False
        else:
            is_passed = False

        if isinstance(result, aiohttp.client_reqrep.ClientResponse):
            status = int(result.status)
        else:
            status = None

        check_result = CheckResult()
        check_result.proxy = proxy
        check_result.is_passed = is_passed
        check_result.is_banned = is_banned
        check_result.check = self
        check_result.time = delta_time
        check_result.status = status
        proxy.add_check(check_result)

        error = ''
        if isinstance(result, BaseException):
            error = ', error: {}'.format(result.__class__.__name__)
        self.logger.debug('Finished check (is passed: {}) for {} on {} by {:0.3f} s{}'.format(is_passed, proxy, self.url, delta_time, error))
        return check_result


def Check(url, status=None, xpath=None, timeout=5):
    check = {}
    check['url'] = url
    check['timeout'] = timeout

    if status is None:
        check['status'] = None
    elif isinstance(status, collections.Iterable) and not isinstance(status, str):
        check['status'] = [int(x) for x in status]
    else:
        check['status'] = [int(status)]

    xpath = [xpath] if isinstance(xpath, str) else xpath
    check['check_xpath'] = []
    for item in xpath:
        buffer_xpath = {}
        buffer_xpath['xpath'] = item
        if isinstance(item, xpath_check.BanXPathCheck):
            buffer_xpath['type'] = 'ban'
        else:
            buffer_xpath['type'] = 'alive'
        check['check_xpath'].append(buffer_xpath)

    return CheckDefinition(definition=json.dumps(check))


class MultiCheck:
    def __init__(self, *args, timeout=5):
        self.checks = args
        for check in self.checks:
            check.timeout = timeout

    async def check(self, proxy):
        return await asyncio.gather(*[check.check(proxy) for check in self.checks])


class CheckResult(Base):
    __tablename__ = 'check_result'

    id = Column(Integer, primary_key=True)
    is_passed = Column(Boolean)
    is_banned = Column(Boolean)
    status = Column(Integer)
    time = Column(Integer)
    proxy_id = Column(Integer, ForeignKey('proxy.id'))
    proxy = relationship('Proxy', back_populates='checks')
    check_id = Column(Integer, ForeignKey('check_definition.id'))
    check = relationship('CheckDefinition')


    def __bool__(self):
        return bool(self.is_passed)

    def __repr__(self):
        return '<{} {} proxy={} time={:0.0f}ms>'.format(__class__.__name__, self.is_passed, self.proxy, self.time*1000)


Proxy.checks = relationship('CheckResult', order_by=CheckResult.id, back_populates='proxy')


def main():
    Base.metadata.create_all(get_engine())


def get_engine():
    if not get_engine.engine:
        import os
        db_dir_path = os.path.abspath(os.path.dirname(__file__))
        db_file_name = 'test4.db'
        db_path = os.path.join(db_dir_path, db_file_name)
        get_engine.engine = create_engine('sqlite:///{}'.format(db_path), echo=True)
    return get_engine.engine
get_engine.engine = None


def get_session():
    return sessionmaker(bind=get_engine())()


if __name__ == '__main__':
    main()
