import json
import urllib.parse

import treq

from proxy_scraper.client import ProxyCheckerClient


class ProxyPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        obj = cls()
        obj.client = ProxyCheckerClient(
            host=settings.get('PROXY_CHECKER_HOST'),
            port=settings.get('PROXY_CHECKER_PORT'),
        )
        return obj

    def process_item(self, item, spider):
        return self.client.add(
            ip=item['ip'],
            port=item['port'],
        )
