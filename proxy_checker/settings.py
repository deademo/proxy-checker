import logging

DEBUG_MODE = False
SQL_LOG_ENABLED = False

LOG_LEVEL = logging.DEBUG
PROGRESS_BAR_ENABLED = False
DEFAULT_TIMEOUT = 2
DEFAULT_CONCURENT_REQUESTS = 50
POSSIBLE_PROTOCOLS = ['http', 'socks4', 'socks5']

def enable_debug_mode():
    LOG_LEVEL = logging.INFO
    PROGRESS_BAR_ENABLED = True

if DEBUG_MODE:
    enable_debug_mode()
