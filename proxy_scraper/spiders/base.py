import re

import scrapy

from proxy_scraper.items import ProxyItem


class WrongResult(BaseException):
    pass


class BaseSpider(scrapy.Spider):
    pass


class TableSpider(BaseSpider):
    row_xpath = './/table//tr[not(.//th)]'
    column_xpath = './/td//text()'
    column_map = {'ip': 0, 'port': 1}
    _ip_regrexp = '^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$'
    checks = []

    def check_is_ip_ok(self, ip):
        return re.match(self._ip_regrexp, ip)

    def check_is_port_ok(self, port):
        try:
            port = int(port)
        except:
            return False
        return port > 0 and port <= 65535

    def parse(self, response):
        rows = response.xpath(self.row_xpath)
        for row in rows:
            try:
                columns = row.xpath(self.column_xpath)
                if self.column_map['ip'] == self.column_map['port']:
                    data = columns[self.column_map['ip']].extract()
                    try:
                        ip, port = data.split(':')
                    except ValueError:
                        raise WrongResult('Can not split by ":": {}'.format(data))
                else:
                    ip = columns[self.column_map['ip']].extract()
                    port = columns[self.column_map['port']].extract()
                ip, port = ip.strip(), port.strip()

                if not self.check_is_ip_ok(ip):
                    raise WrongResult('Wrong ip: {}'.format(ip))
                if not self.check_is_port_ok(port):
                    raise WrongResult('Wrong port: {}'.format(port))
            except (WrongResult, IndexError) as e:
                print(e)
                continue
            yield ProxyItem(
                ip=ip,
                port=port,
                checks=self.checks,
            )
