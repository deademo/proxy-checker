from proxy_scraper.spiders.base import TableSpider


class FreeProxyListNetSpider(TableSpider):
    name = 'proxynova'
    start_urls = ['https://www.proxynova.com/proxy-server-list/']
