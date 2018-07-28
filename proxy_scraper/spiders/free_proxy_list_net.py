from proxy_scraper.spiders.base import TableSpider


class FreeProxyListNetSpider(TableSpider):
    name = 'free_proxy_list_net'
    start_urls = ['https://free-proxy-list.net/']
    checks = ['default_olx']
