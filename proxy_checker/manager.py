import asyncio
import entity
import logging
import time

import settings


class ProcessItem:
    def __init__(self, item):
        self.item = item
        self._process_every = item.recheck_every
        self._last_processed_at = None
        self._next_process_at = None

    def processed(self):
        self._last_processed_at = time.time()
        if self._process_every:
            self._next_process_at = self._last_processed_at + self._next_process_at

    @property
    def is_need_to_process(self):
        is_first_process = not self._last_processed_at and not self._next_process_at
        is_ready_to_process = self._next_process_at and self._next_process_at < time.time()
        return is_ready_to_process or is_first_process


class Manager:
    def __init__(self):
        self.queue = {}
        self._is_running = False
        self._is_need_to_stop = False
        self.workers = []
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)

    def put(self, item):
        self.queue[str(item)] = ProcessItem(item)

    @property
    def is_running(self):
        return self._is_running

    async def start(self):
        self.logger.info('Manager main loop started')

        self._is_running = True
        while self._is_running and not self._is_need_to_stop:
            for key, item in self.queue.items():
                if item.is_need_to_process:
                    self.logger.debug('Trying to process {}'.format(item.item))
                    if self.send_to_worker(item):
                        self.logger.debug('Successfuly processed {}'.format(item.item))
                        item.processed()
            await asyncio.sleep(0.5)
        self._is_running = False

        self.logger.info('Manager main loop stopped')

    def send_to_worker(self, process_item):
        workers = [x for x in self.workers if x.is_running]
        if not workers:
            return False
    
        workers = sorted(workers, key=lambda x: x.queue_size)
        workers[0].put(process_item.item)
        return True

    async def stop(self):
        self._is_need_to_stop = True

    async def wait_stop(self):
        while self.is_running:
            await asyncio.sleep(0.1)
