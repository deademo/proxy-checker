import logging



SERVER_HOST = '0.0.0.0'
SERVER_PORT = 3300

DB = {
    'host': 'postgres',
    'port': 5432,
    'user': 'user',
    'password': 'password',
    'database': 'proxy_checker',
}

DEFAULT_TIMEOUT = 2
DEFAULT_CONCURENT_REQUESTS = 50
POSSIBLE_PROTOCOLS = ['http', 'socks4', 'socks5']

TRUE_VALUES = ('1', 'true', 'True', 'on')

DEBUG_MODE = True
LOG_LEVEL = logging.INFO
PROGRESS_BAR_ENABLED = True


def enable_debug_mode():
    global LOG_LEVEL, PROGRESS_BAR_ENABLED
    LOG_LEVEL = logging.DEBUG
    PROGRESS_BAR_ENABLED = False

if DEBUG_MODE:
    enable_debug_mode()


try:
    from settings_local import *
except ImportError:
    pass
