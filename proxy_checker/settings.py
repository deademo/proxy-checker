import logging

DEBUG_MODE = True
SQL_LOG_ENABLED = False

LOG_LEVEL = logging.INFO
PROGRESS_BAR_ENABLED = True
DEFAULT_TIMEOUT = 2
DEFAULT_CONCURENT_REQUESTS = 50
POSSIBLE_PROTOCOLS = ['http', 'socks4', 'socks5']

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 3300

def enable_debug_mode():
    global LOG_LEVEL, PROGRESS_BAR_ENABLED
    LOG_LEVEL = logging.DEBUG
    PROGRESS_BAR_ENABLED = False

if DEBUG_MODE:
    enable_debug_mode()
