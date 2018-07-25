import json
import urllib.parse

import treq


class ProxyPipeline:
    def process_item(self, item, spider):
        proxy_string = '{}:{}'.format(item['ip'], item['port'])
        url = 'http://{}:{}/add?proxy={}'.format(
            spider.settings['PROXY_CHECKER_HOST'],
            spider.settings['PROXY_CHECKER_PORT'],
            proxy_string
        )
        
        return item
