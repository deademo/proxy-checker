class XPathCheck(str):
    def __init__(self, xpath, *args, **kwargs):
        self.xpath = xpath
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return '{}'.format(self.xpath)

    def __str__(self):
        return '{}'.format(self.xpath)


class BanXPathCheck(XPathCheck):
    pass
