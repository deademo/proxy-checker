from proxy_scraper.spiders.base import TableSpider


class ProxyListenDeSpider(TableSpider):
    name = 'spys_one'
    start_urls = ['http://spys.one/']
    column_map = {'ip': 0, 'port': 0}
