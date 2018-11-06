import asyncio
import argparse
import logging
import os
import time
import warnings

from sqlalchemy import exc as sa_exc
import tqdm
import entity
import settings
from worker import Worker
from manager import Manager
from entity import parse_proxy_string
from xpath_check import XPathCheck, BanXPathCheck



arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--debug', action='store_true', required=False)
arg_parser.add_argument('-q', '--quiet', action='store_true', default=True, required=False)
arg_parser.add_argument('-pb', '--progress_bar', action='store_true', default=False, required=False)
arg_parser.add_argument('--default_file_path',  default='proxy_checker/proxies.list', required=False)


def main():
    concurent_requests = 50
    workers_count = 5
    timeout = 3


    warnings.simplefilter("ignore", category=sa_exc.SAWarning)

    args, opts = arg_parser.parse_known_args()
    if not len(opts):
        opts.append(args.default_file_path)
    if args.debug:
        settings.enable_debug_mode()
        args.quiet = False

    tmp_database_file_name = 'tmp_database.db'
    tmp_database_file_path = entity.get_sqlite_database_path(db_file_name=tmp_database_file_name)
    database_url = entity.get_sqlite_database_url(db_path=tmp_database_file_path)
    session = entity.get_session(database_url=database_url, force=True)
    entity.create_models()

    manager = Manager()
    manager.logger.disabled = args.quiet
    logging.getLogger('asyncio').disabled = args.quiet

    try:
        if not len(opts):
            raise FileNotFoundError
        file_path = opts[0]
        with open(file_path, 'r') as f:
            proxies = [x.strip() for x in f.readlines()]
            proxies = [x for x in proxies if x]
    except FileNotFoundError:
        manager.logger.warning('File not exist by path: {}'.format(file_path))
        manager.logger.info('Trying to use opts as proxies input')
        proxies = opts

    if not proxies:
        manager.logger.critical('No any proxies found')
        return False

    manager.logger.debug('Trying to check these proxies: {}'.format(', '.join(proxies)))

    start_time = time.time()
    checks = []
    checks.append(entity.Check(
        'http://google.com',
        status=[200, 301],
        xpath_list=(XPathCheck('.//input[contains(@name, "btn") and @type="submit"]'), )
    ))
    checks.append(entity.Check(
        'https://www.amazon.com/s/ref=nb_sb_noss_2?url=search-alias%3Daps&field-keywords=Xiaomi+MI+A1+(64GB%2C+4GB+RAM)&rh=i%3Aaps%2Ck%3AXiaomi+MI+A1+(64GB%5Cc+4GB+RAM)',
        status=200,
        xpath_list=(
            XPathCheck('.//span[contains(text(), "Xiaomi MI A1 (64GB, 4GB RAM")]'),
            BanXPathCheck('.//*[contains(text(), "To discuss automated access to Amazon data please contact")]'),
            BanXPathCheck('.//*[contains(@alt, "Something went wrong on our end. Please go back and")]'),
            BanXPathCheck('.//*[contains(text(), "Type the characters you see in this image")]'),
        )
    ))
    checks.append(entity.Check(
        'https://www.olx.ua', 
        status=200, 
        xpath_list=(
            XPathCheck('.//input[@id="headerSearch"]'),
            BanXPathCheck('.//img[contains(@src, "failover")]'),
        )
    ))

    for check in checks:
        check.logger.disabled = args.quiet

    progress_bar_list = []
    for i in range(workers_count):
        if settings.PROGRESS_BAR_ENABLED or args.progress_bar:
            progress_bar = tqdm.tqdm(position=i)
            progress_bar_list.append(progress_bar)
        else:
            progress_bar = None
        worker = Worker(
            concurent_requests=concurent_requests,
            progress_bar=progress_bar
        )
        manager.workers.append(worker)

        worker.logger.disabled = args.quiet
        
    proxies = [parse_proxy_string(proxy) for proxy in proxies]
    for proxy in proxies[:]:
        if not proxy.protocol:
            for protocol in settings.POSSIBLE_PROTOCOLS:
                if protocol == 'http':
                    continue
                buffer_proxy = proxy.make_proxy_string(protocol=protocol)
                buffer_proxy = parse_proxy_string(buffer_proxy)

                proxies.append(buffer_proxy)

    for proxy in proxies:
        for check in checks:
            proxy.add_check_definition(check)
    session.commit()

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

    for proxy in proxies:
        session.add(proxy)
    session.commit()

    if args.progress_bar:
        for x in progress_bar_list:
            x.close()
            print('')

    alive = sorted(filter(lambda x: x.is_alive, proxies), key=lambda x: x.time)
    for proxy in alive:
        banned_on = proxy.banned_on
        banned_on = ', banned on: '+(', '.join([x for x in banned_on])) if banned_on else ''

        if not args.quiet:
            manager.logger.info('{:0.3f} s, {}{}'.format(proxy.time, proxy, banned_on))
        else:
            print(proxy, flush=True)

    delta_time = time.time() - start_time
    manager.logger.info('{}/{} proxies alive. Checked {} proxies for {:0.2f} s. {:0.0f} proxies per second with {} concurent requests.'.format(len(alive), len(proxies), len(proxies), delta_time, len(proxies)/delta_time, concurent_requests))

    os.remove(tmp_database_file_path)



if __name__ == '__main__':
    main()
