import asyncio
import logging
import time

import entity
import settings
from worker import Worker
from manager import Manager
from xpath_check import XPathCheck, BanXPathCheck


def main():
    from proxies import proxies
    global proxies

    concurent_requests = 50

    start_time = time.time()
    checks = []
    checks.append(entity.Check(
        'http://google.com',
        status=[200, 301],
        xpath='.//input[contains(@name, "btn") and @type="submit"]'
    ))
    checks.append(entity.Check(
        'https://www.amazon.com/s/ref=nb_sb_noss_2?url=search-alias%3Daps&field-keywords=Xiaomi+MI+A1+(64GB%2C+4GB+RAM)&rh=i%3Aaps%2Ck%3AXiaomi+MI+A1+(64GB%5Cc+4GB+RAM)',
        status=200,
        xpath=(
            XPathCheck('.//span[contains(text(), "Xiaomi MI A1 (64GB, 4GB RAM")]'),
            BanXPathCheck('.//*[contains(text(), "To discuss automated access to Amazon data please contact")]'),
            BanXPathCheck('.//*[contains(@alt, "Something went wrong on our end. Please go back and")]'),
            BanXPathCheck('.//*[contains(text(), "Type the characters you see in this image")]'),
        )
    ))
    checks.append(entity.Check(
        'https://www.olx.ua', 
        status=200, 
        xpath=(
            XPathCheck('.//input[@id="headerSearch"]'),
            BanXPathCheck('.//img[contains(@src, "failover")]'),
        )
    ))

    manager = Manager()
    for x in range(2):
        worker = Worker()
        worker.checks += checks
        manager.workers.append(worker)
        
    proxies = [entity.Proxy(*proxy.split(':')) for proxy in proxies]
    for proxy in proxies:
        manager.put(proxy)

    loop = asyncio.get_event_loop()

    asyncio.ensure_future(asyncio.gather(*[x.start() for x in manager.workers]))
    asyncio.ensure_future(manager.start())

    loop.run_until_complete(asyncio.gather(*[x.stop() for x in manager.workers]))
    loop.run_until_complete(asyncio.gather(*[x.wait_stop() for x in manager.workers]))
    loop.run_until_complete(manager.stop())
    loop.run_until_complete(manager.wait_stop())

    loop.close()

    alive = sorted(filter(lambda x: x.is_alive and not x.is_banned_somewhere, proxies), key=lambda x: x.time)
    for proxy in alive:
        banned_on = proxy.banned_on
        banned_on = ', banned on: '+(', '.join([x for x in banned_on])) if banned_on else ''
        manager.logger.info('{:0.3f} s, {}{}'.format(proxy.time, proxy, banned_on))

    delta_time = time.time() - start_time
    manager.logger.info('{}/{} proxies alive. Checked {} proxies for {:0.2f} s. {:0.0f} proxies per second with {} concurent requests.'.format(len(alive), len(proxies), len(proxies), delta_time, len(proxies)/delta_time, concurent_requests))


if __name__ == '__main__':
    main()
