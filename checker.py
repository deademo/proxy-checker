import asyncio
import logging

import entity
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

    m = Manager()
    m.checks.append(entity.Check('http://google.com'))
    m.checks.append(entity.Check('http://yandex.ru'))
    m.checks.append(entity.Check('http://amazon.com'))
    m.checks.append(entity.Check('http://ifconfig.so'))

    proxies = [entity.Proxy(*x.split(':')) for x in proxies]
    for proxy in proxies:
        m.queue.put_nowait(proxy)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(m.start())
    loop.close()

    for proxy in sorted(filter(lambda x: x.alive, proxies), key=lambda x: x.time):
        m.logger.info('{:0.3f} s, {}'.format(proxy.time, proxy))


if __name__ == '__main__':
    main()
