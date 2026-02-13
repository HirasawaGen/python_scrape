import asyncio
from asyncio import Queue, Lock
from typing import Callable, Awaitable, AsyncGenerator, Any
from contextlib import asynccontextmanager

from playwright.async_api import Page, BrowserContext
from aiolimiter import AsyncLimiter


class PagePool:
    '''
    A pool of playwright pages that can be used to scrape pages concurrently.

    :param context: The playwright browser context to use for creating pages.
    :param max_pages: The maximum number of pages to keep in the pool.
    :param time_period: The time period (in seconds) to wait before creating a new page.
    :param page_processor: An optional function that takes a page and returns a modified page.
    :return: An async context manager that returns a page from the pool.
    '''
    _lock = Lock()


    async def _initialize(
        self,
    ):
        if self._initialized:
            return
        async with self._lock:
            self._initialized = True
            self._queue = Queue()
            self._limiter = AsyncLimiter(1, self._time_period)
            pages = await asyncio.gather(*[
                self._context.new_page()
                for _ in range(self._max_pages)
            ])
            if self._page_processor is not None:
                pages = await asyncio.gather(*[
                    self._page_processor(page)
                    for page in pages
                ])
            await asyncio.gather(*[
                self._queue.put(page)
                for page in pages
            ])
            


    def __init__(
        self,
        context: BrowserContext,
        max_pages: int,
        time_period: float = 1.0,
        page_processor: Callable[[Page], Awaitable[Page]] | None = None,
    ):
        
        self._context = context
        self._max_pages = max_pages
        self._time_period = time_period
        self._page_processor = page_processor
        self._initialized = False
        self._queue: Queue[Page]
        self._limiter: AsyncLimiter


    @asynccontextmanager
    async def __call__(self, *args, **kwargs) -> AsyncGenerator[Page, None]:
        '''
        NOTE: *args and **kwargs is temporarily ignored. Maybe used in the future. ignore them for now.
        '''
        if not self._initialized:
            await self._initialize()
        async with self._limiter:
            page = await self._queue.get()
            try:
                yield page
            finally:
                if page.is_closed():
                    page = await self._context.new_page()
                    await self._queue.put(page)
                else:
                    await asyncio.gather(
                        self._queue.put(page),
                        page.evaluate("() => window.stop()"),
                    )
