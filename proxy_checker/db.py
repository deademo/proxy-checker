import collections
import datetime
import json
import urllib.parse

from sqlalchemy_aio import ASYNCIO_STRATEGY
from sqlalchemy import (Column, Boolean, Integer, String, ForeignKey, 
                        UniqueConstraint, DateTime, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql.expression import ClauseElement

from checker import Checker
import settings
import xpath_check


def get_engine(strategy=None):
    if get_engine.engine is None:
        kwargs = {}
        if strategy:
            kwargs['strategy'] = strategy
        get_engine.engine = create_engine(
                'postgresql://{user}:{password}@{host}/{database}'.format(**settings.DB),
                **kwargs
        )
    return get_engine.engine
get_engine.engine = None


async def get_session(engine=None):
    if not engine:
        engine = get_engine()

    if get_session.session is None:
        get_session.session = sessionmaker(bind=engine)()
    return get_session.session
get_session.session = None


Base = declarative_base()


class Proxy(Base):
    __tablename__ = 'proxy'
    __table_args__ = (UniqueConstraint('host', 'port', 'protocol', name='proxy_uix'), )

    id = Column(Integer, primary_key=True)
    host = Column(String)
    port = Column(String)
    protocol = Column(String)
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

    async def last_checks(self):
        session = await get_session()
        return (session.session.query(CheckResult)
                    .join(Proxy)
                    .join(ProxyCheckDefinition)
                    .filter(CheckResult.proxy == self and ProxyCheckDefinition.proxy == self)
                    .order_by(CheckResult.id)
                    .group_by(CheckResult.check_id)
                    .all()
        )

    @property
    def check_definitions(self):
        return [x.check_definition for x in self._check_definitions]

    async def add_check_definition(self, check_definition):
        definition_mapping = await get_or_create(ProxyCheckDefinition, check_definition=check_definition, proxy=self)
        if not definition_mapping.id:
            self._check_definitions.append(definition_mapping)

    @property
    def time(self):
        if not self.checks:
            return -1
        return sum([x.time for x in self.checks])/len(self.checks)

    async def is_alive(self):
        return all((await self.last_checks))

    async def is_banned_somewhere(self):
        return any([x.is_banned for x in (await self.last_checks)])

    async def banned_on(self):
        return [x.check.netloc for x in (await self.last_checks) if x.is_banned]


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
    definition = Column(String)
    netloc = Column(String)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._decoded_definition = None
        self._checker = Checker(check=self, check_result_cls=CheckResult)

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

    async def check(self, *args, **kwargs):
        return (await self._checker.check(*args, **kwargs))


async def Check(*args, **kwargs):
    check_definition = make_check_definition(*args, **kwargs)
    netloc = urllib.parse.urlparse(check_definition['url']).netloc
    return (await get_or_create(
        CheckDefinition, 
        definition=json.dumps(check_definition),

        netloc=netloc,

    ))


class CheckResult(Base):
    __tablename__ = 'check_result'

    id = Column(Integer, primary_key=True)
    is_passed = Column(Boolean)
    is_banned = Column(Boolean)
    status = Column(Integer)
    time = Column(Integer)
    error = Column(String)
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


async def get_or_create(model, session=None, defaults=None, **kwargs):
    if not session:
        session = await get_session()

    instance = session.query(model).filter_by(**kwargs).first()

    if instance:
        instance.__init__()
        return instance
    else:
        params = dict((k, v) for k, v in kwargs.items() if not isinstance(v, ClauseElement))
        params.update(defaults or {})
        instance = model(**params)
        return instance


async def parse_proxy_string(proxy):
    protocol, host, port = get_proxy_parts(proxy)

    return (await get_or_create(
        Proxy,
        host=host,
        port=port,
        protocol=protocol
    ))


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


def init_db(engine=None):
    if not engine:
        engine = get_engine()
    Base.metadata.create_all(get_engine())
