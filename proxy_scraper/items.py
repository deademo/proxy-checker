import scrapy


class ProxyItem(scrapy.Item):
    ip = scrapy.Field()
    port = scrapy.Field()
    checks = scrapy.Field()

    def __str__(self):
        return '<{} {}:{}>'.format(self.__class__.__name__, self['ip'], self['port'])
