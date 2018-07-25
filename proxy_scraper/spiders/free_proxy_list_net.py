from proxy_scraper.spiders.base import BaseSpider
from proxy_scraper.items import ProxyItem


class FreeProxyListNetSpider(BaseSpider):
    name = 'free_proxy_list_net'
    start_urls = ['https://free-proxy-list.net/']

    def parse(self, response):
        rows = response.xpath('.//*[contains(@id, "proxylisttable")]//tr[not(.//th)]')
        for row in rows:
            columns = row.xpath('.//td/text()')
            yield ProxyItem(
                ip=columns[0].extract(),
                port=columns[1].extract()
            )
