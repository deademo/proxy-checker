from entity import Proxy, get_or_create

import urllib.parse


def parse_proxy_string(proxy):
    parsed_proxy = urllib.parse.urlparse(proxy)

    netloc = parsed_proxy.netloc or parsed_proxy.path
    netloc_splitted = netloc.split(':')
    host = netloc_splitted[0]
    if len(netloc_splitted) > 1:
        port = netloc_splitted[1]
    else:
        port = None

    return get_or_create(
        Proxy,
        host=host,
        port=port,
        protocol=parsed_proxy.scheme
    )