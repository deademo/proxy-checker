import asyncio
import entity
import logging
import time

import settings


class Worker:
    def __init__(self, concurent_requests=None, progress_bar=None):
        self.queue = asyncio.Queue()
        self.concurent_requests = concurent_requests or settings.DEFAULT_CONCURENT_REQUESTS
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.setLevel(settings.LOG_LEVEL)
        self._is_running = False
        self._stop_after_queue_processed = False
        self._internal_queue = []
        self._progress_bar = progress_bar
        self._processed_count = 0
        self._started_at = time.time()

    @property
    def queue_size(self):
        return self.queue.qsize()

    @property
    def is_running(self):
        return self._is_running

    def put(self, item):
        self.queue.put_nowait(item)


    @property
    def is_have_item_to_process(self):
        return self.queue.qsize() != 0 or len(self._internal_queue) != 0

    def on_task_finished(self):
        self._processed_count += 1
        self.update_progress_bar()

    def update_progress_bar(self):
        if self._progress_bar is None:
            return False
        self._progress_bar.total = self.queue_size + self._processed_count
        self._progress_bar.update(1)

    @property
    def performance(self):
        delta_time = time.time() - self._started_at
        return int(self._processed_count/delta_time)

    async def start(self):
        self.logger.info('Worker main loop started')
        self._is_running = True

        while self._is_running:
            if self.queue.qsize() != 0:
                item = await self.queue.get()
                check = entity.MultiCheck(*item.check_definitions).check
                self._internal_queue.append(asyncio.ensure_future(check(item)))

            is_continue = True
            while is_continue:
                to_del = [i for i, f in enumerate(self._internal_queue) if f.done()]
                for i in sorted(to_del, reverse=True):
                    self.on_task_finished()
                    del self._internal_queue[i]

                await asyncio.sleep(0.1)

                is_task_queue_full = len(self._internal_queue) >= self.concurent_requests 
                is_task_queue_not_empty = len(self._internal_queue)
                is_process_queue_empty = self.queue.qsize() == 0
                is_continue = is_task_queue_full or (is_process_queue_empty and is_task_queue_not_empty)


            # Waiting for new tasks
            self._is_running = self.is_have_item_to_process
            if not self.is_have_item_to_process and not self._stop_after_queue_processed:
                self._is_running = True
                await asyncio.sleep(0.5)

        self.logger.info('Worker main loop stopped')

    async def stop(self):
        self._stop_after_queue_processed = True

    async def wait_stop(self):
        while self.is_running:
            await asyncio.sleep(0.1)
        if self._progress_bar:
            self._progress_bar.close()
