import asyncio
import logging
import time

import entity
from xpath_check import XPathCheck, BanXPathCheck
import settings


class Manager:
    def __init__(self, concurent_requests=None, timeout=None):
        self.queue = asyncio.Queue()
        self.concurent_requests = concurent_requests or settings.DEFAULT_CONCURENT_REQUESTS
        self.timeout = timeout or settings.DEFAULT_TIMEOUT
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)
        self.checks = []


    async def start(self):
        c = entity.MultiCheck(
            *self.checks,
            timeout=self.timeout
        )

        futures = []
        while self.queue.qsize() != 0 or len(futures) != 0:

            if self.queue.qsize() != 0:
                item = await self.queue.get()
                futures.append(asyncio.ensure_future(c.check(item)))

            while True:
                is_task_queue_full = len(futures) >= self.concurent_requests 
                is_task_queue_not_empty = len(futures)
                is_process_queue_empty = self.queue.qsize() == 0
                is_continue = is_task_queue_full or (is_process_queue_empty and is_task_queue_not_empty)
                if not is_continue:
                    break

                to_del = [i for i, f in enumerate(futures) if f.done()]
                for i in sorted(to_del, reverse=True):
                    del futures[i]

                await asyncio.sleep(0.1)


def main():
    from proxies import proxies
    global proxies

    concurent_requests = 50

    start_time = time.time()
    m = Manager(concurent_requests=concurent_requests, timeout=3)
    m.checks.append(entity.Check(
        'http://google.com',
        status=[200, 301],
        xpath='.//input[contains(@name, "btn") and @type="submit"]'
    ))
    m.checks.append(entity.Check(
        'https://www.amazon.com/s/ref=nb_sb_noss_2?url=search-alias%3Daps&field-keywords=Xiaomi+MI+A1+(64GB%2C+4GB+RAM)&rh=i%3Aaps%2Ck%3AXiaomi+MI+A1+(64GB%5Cc+4GB+RAM)',
        status=200,
        xpath=(
            XPathCheck('.//span[contains(text(), "Xiaomi MI A1 (64GB, 4GB RAM")]'),
            BanXPathCheck('.//*[contains(text(), "To discuss automated access to Amazon data please contact")]'),
            BanXPathCheck('.//*[contains(@alt, "Something went wrong on our end. Please go back and")]'),
            BanXPathCheck('.//*[contains(text(), "Type the characters you see in this image")]'),
        )
    ))
    m.checks.append(entity.Check(
        'https://www.olx.ua', 
        status=200, 
        xpath=(
            XPathCheck('.//input[@id="headerSearch"]'),
            BanXPathCheck('.//img[contains(@src, "failover")]'),
        )
    ))
    # m.checks.append(entity.Check('http://yandex.ru', status=[200, 302], xpath='.//body'))
    # m.checks.append(entity.Check('http://ifconfig.so', status=[200, 302], xpath='.//body'))

    proxies = [entity.Proxy(*x.split(':')) for x in proxies]
    for proxy in proxies:
        m.queue.put_nowait(proxy)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(m.start())
    loop.close()

    alive = sorted(filter(lambda x: x.is_alive and not x.is_banned_somewhere, proxies), key=lambda x: x.time)
    for proxy in alive:
        banned_on = proxy.banned_on
        banned_on = ', banned on: '+(', '.join([x for x in banned_on])) if banned_on else ''
        m.logger.info('{:0.3f} s, {}{}'.format(proxy.time, proxy, banned_on))

    delta_time = time.time() - start_time
    m.logger.info('{}/{} proxies alive. Checked {} proxies for {:0.2f} s. {:0.0f} proxies per second with {} concurent requests.'.format(len(alive), len(proxies), len(proxies), delta_time, len(proxies)/delta_time, concurent_requests))


if __name__ == '__main__':
    main()
