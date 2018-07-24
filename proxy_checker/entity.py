import asyncio
import collections
import concurrent
import datetime
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
                        UniqueConstraint, DateTime)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql.expression import ClauseElement
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

def get_proxy_parts(proxy):
    parsed_proxy = urllib.parse.urlparse(proxy)

    netloc = parsed_proxy.netloc or parsed_proxy.path
    netloc_splitted = netloc.split(':')
    host = netloc_splitted[0]
    if len(netloc_splitted) > 1:
        port = netloc_splitted[1]
    else:
        port = None

    return parsed_proxy.scheme, host, port

def parse_proxy_string(proxy):
    protocol, host, port = get_proxy_parts(proxy)

    return get_or_create(
        Proxy,
        host=host,
        port=port,
        protocol=protocol
    )


class Proxy(Base):
    __tablename__ = 'proxy'
    __table_args__ = (UniqueConstraint('host', 'port', 'protocol', name='proxy_uix'), )

    id = Column(Integer, primary_key=True)
    host = Column(String(1024))
    port = Column(String(1024))
    protocol = Column(String(1024))
    recheck_every = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow())


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
    def last_checks(self):
        return (get_session().query(CheckResult)
                    .join(Proxy)
                    .join(ProxyCheckDefinition)
                    .filter(CheckResult.proxy == self and ProxyCheckDefinition.proxy == self)
                    .order_by(CheckResult.id)
                    .group_by(CheckResult.check_id)
                    .all()
        )

    @property
    def check_definitions(self):
        # TODO: needs to move these logic to separate class "Checker"
        check_definitions = [x.check_definition for x in self._check_definitions]
        for check_definition in check_definitions:
            check_definition.__init__()
        return check_definitions

    def add_check_definition(self, check_definition):
        definition_mapping = get_or_create(ProxyCheckDefinition, check_definition=check_definition, proxy=self)
        if not definition_mapping.id:
            self._check_definitions.append(definition_mapping)

    @property
    def time(self):
        if not self.checks:
            return -1
        return sum([x.time for x in self.checks])/len(self.checks)

    @property
    def is_alive(self):
        return all(self.last_checks)

    @property
    def is_banned_somewhere(self):
        return any([x.is_banned for x in self.last_checks])

    @property
    def banned_on(self):
        return [x.check.netloc for x in self.last_checks if x.is_banned]


class ProxyCheckDefinition(Base):
    __tablename__ = 'proxy_check_definition'
    __table_args__ = (UniqueConstraint('proxy_id', 'check_definition_id', name='proxy_check_definition_uix'), )

    id = Column(Integer, primary_key=True)
    proxy_id = Column(Integer, ForeignKey('proxy.id'))
    proxy = relationship('Proxy', back_populates='_check_definitions')
    check_definition_id = Column(Integer, ForeignKey('check_definition.id'))
    check_definition = relationship('CheckDefinition')


class CheckDefinition(Base):
    __tablename__ = 'check_definition'
    __table_args__ = (UniqueConstraint('definition', name='check_definition_uix'), )
    _decoded_definition = None

    id = Column(Integer, primary_key=True)
    name = Column(String(1024), unique=True, nullable=True)
    definition = Column(String(3072))
    netloc = Column(String(1024))

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
        return [int(x) for x in self.decoded_definition.get('status')]

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
                async with aiohttp.ClientSession(connector=ProxyConnector(verify_ssl=False), request_class=ProxyClientRequest, conn_timeout=self.timeout, read_timeout=self.timeout) as session:
                    async with session.get(self.url, proxy=str(proxy), headers=random_session()['headers']) as response:
                        content = await response.read()
                        # self.logger.debug('Got response [{}]: {} bytes'.format(response.status, len(content))) #DELETE_DEBUG
                        result = response
        except possible_exceptions as e:
            result = e
        delta_time = time.time() - start_time

        is_passed = True
        is_banned = False
        if isinstance(result, aiohttp.client_reqrep.ClientResponse):
            if self.check_xpath:
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
                    # self.logger.debug('No any xpath worked for proxy {} on url {} ({}):'.format(proxy, self.url, ", ".join(self.check_xpath))) #DELETE_DEBUG

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
        check_result.done_at = datetime.datetime.utcnow()
        check_result.status = status
        if isinstance(result, BaseException):
            check_result.error = str(result)
        get_session().add(check_result)

        error = ''
        if isinstance(result, BaseException):
            error = ', error: {}'.format(str(result))
        self.logger.debug('Finished check (is passed: {}) for {} on {} by {:0.3f} s{}'.format(is_passed, proxy, self.url, delta_time, error))
        return check_result


def make_check_definition(url, status=200, xpath=[], timeout=None):
    check = {}
    check['url'] = url
    check['timeout'] = timeout or settings.DEFAULT_TIMEOUT

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
    return check


def Check(*args, name=None, **kwargs):
    check_definition = make_check_definition(*args, **kwargs)
    netloc = urllib.parse.urlparse(check_definition['url']).netloc
    return get_or_create(
        CheckDefinition, 
        definition=json.dumps(check_definition),
        name=name,
        netloc=netloc,
    )


class MultiCheck:
    def __init__(self, *args):
        self.checks = args

    async def check(self, proxy):
        return await asyncio.gather(*[check.check(proxy) for check in self.checks])


class CheckResult(Base):
    __tablename__ = 'check_result'

    id = Column(Integer, primary_key=True)
    is_passed = Column(Boolean)
    is_banned = Column(Boolean)
    status = Column(Integer)
    time = Column(Integer)
    error = Column(String(1024))
    proxy_id = Column(Integer, ForeignKey('proxy.id'))
    proxy = relationship('Proxy', back_populates='checks')
    check_id = Column(Integer, ForeignKey('check_definition.id'))
    check = relationship('CheckDefinition')
    done_at = Column(DateTime)


    def __bool__(self):
        return bool(self.is_passed)

    def __repr__(self):
        return '<{} {} proxy={} time={:0.0f}ms>'.format(__class__.__name__, self.is_passed, self.proxy, self.time*1000)


Proxy.checks = relationship('CheckResult', order_by=CheckResult.id, back_populates='proxy')
Proxy._check_definitions = relationship('ProxyCheckDefinition', order_by=ProxyCheckDefinition.id, back_populates='proxy')


def create_models(engine=None):
    if not engine:
        engine = get_engine()
    for i in range(5):
        try:
            Base.metadata.create_all(engine)
            error = None
        except Exception as e:
            error = e
            time.sleep(i*3)
            continue
        break
    if error:
        raise error


def main():
    create_models()    


def get_database_url():
    return 'mysql://{user}:{password}@{host}/{database}'.format(**settings.DB)


def get_sqlite_database_url(db_file_name=None):
    import os
    db_dir_path = os.path.abspath(os.path.dirname(__file__))
    db_file_name = db_file_name or 'default.db'
    db_path = os.path.join(db_dir_path, db_file_name)
    return 'sqlite:///{}'.format(db_path)


def get_engine(database_url=None, force=False):
    if not database_url:
        database_url = get_database_url()
    if not get_engine.engine or force:
        get_engine.engine = create_engine(database_url, echo=settings.SQL_LOG_ENABLED)
    return get_engine.engine
get_engine.engine = None


def get_session(database_url=None, force=False):
    if not get_session.session or force:
        get_session.session = sessionmaker(bind=get_engine(database_url=database_url), autoflush=False)()
    return get_session.session
get_session.session = None


def get_or_create(model, session=None, defaults=None, **kwargs):
    if not session:
        session = get_session()
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        instance.__init__()
        return instance
    else:
        params = dict((k, v) for k, v in kwargs.items() if not isinstance(v, ClauseElement))
        params.update(defaults or {})
        instance = model(**params)
        session.add(instance)
        return instance


def serializer(obj):
    """JSON encoder function for SQLAlchemy special classes."""
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)


if __name__ == '__main__':
    main()
