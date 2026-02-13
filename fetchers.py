from abc import ABC, abstractmethod
from asyncio import Queue
from typing import AsyncIterable
import random
import asyncio
from logging import getLogger
import logging

from playwright.async_api import Page
from bs4 import BeautifulSoup
from database import ZenianData, ZenianTable


logger = getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class BasePageFetcher(ABC):
    def __init__(
        self,
        url_pattern: str,
        page_queue: Queue[Page],
        min_sleep_time: float = 1.5,
        max_sleep_time: float = 3.0,
        min_page_idx: int = 1,
        max_page_idx: int = 100,
        num_workers: int = 1,
        source: str | None = None,
        catg: str | None = None,
        section: str | None = None,
    ):
        self._url_pattern = url_pattern
        self._page_queue = page_queue
        self._min_sleep_time = min_sleep_time
        self._max_sleep_time = max_sleep_time
        self._min_page_idx = min_page_idx
        self._max_page_idx = max_page_idx
        self._num_workers = num_workers
        self._source = source
        self._catg = catg
        self._section = section
        self._table = ZenianTable()
        self._sem = asyncio.Semaphore(self._num_workers)
    
    async def _init_page(self, page: Page):
        return
    
    async def _to_soup(self, page_idx: int):
        page = await self._page_queue.get()
        try:
            url = self._url_pattern.format(page_idx)
        except:
            url = self._url_pattern
        sleep_time = random.uniform(self._min_sleep_time, self._max_sleep_time) * self._num_workers
        await asyncio.sleep(sleep_time)
        logger.info(f'Fetching page {page_idx}')
        await page.goto(url, wait_until='domcontentloaded')
        await self._init_page(page)
        html_content = await page.content()
        logger.info(f'Got html content for page {page_idx}')
        await self._page_queue.put(page)
        return BeautifulSoup(html_content, 'lxml')
    
    @abstractmethod
    async def parse_soup(self, soup: BeautifulSoup) -> list[ZenianData]:
        pass
    
    async def __call__(self):
        async with self._sem:
            for page_idx in range(self._min_page_idx, self._max_page_idx + 1):
                soup = await self._to_soup(page_idx)
                data = await self.parse_soup(soup)
                for i in range(len(data)):
                    data[i]['source'] = self._source  # type: ignore
                    data[i]['catg'] = self._catg  # type: ignore
                    data[i]['section'] = self._section  # type: ignore
                async with self._table as table:
                    modify_count = await table.save(data)
                logger.info(f'Saved {modify_count} data for page {page_idx}')


class BaseArticleFetcher(ABC):
    def __init__(
        self,
        page_queue: Queue[Page],
        source: str,
        catg: str,
        section: str,
        min_sleep_time: float = 1.5,
        max_sleep_time: float = 3.0,
        min_page_idx: int = 1,
        max_page_idx: int = 100,
        num_workers: int = 1,
    ):
        self._page_queue = page_queue
        self._min_sleep_time = min_sleep_time
        self._max_sleep_time = max_sleep_time
        self._min_page_idx = min_page_idx
        self._max_page_idx = max_page_idx
        self._num_workers = num_workers
        self._source = source
        self._catg = catg
        self._section = section
        self._table = ZenianTable()
        self._sem = asyncio.Semaphore(self._num_workers)
    
    async def _generate_soup(self) -> AsyncIterable[tuple[str, BeautifulSoup]]:
        async with self._table as table:
            data = await table.load(self._source, self._catg, self._section)
        for datum in data:
            if datum.get('content') != 'None':
                logger.info(f'Skipping url {datum["url"]} because it has content')
                continue
            url = datum['url']
            page = await self._page_queue.get()
            sleep_time = random.uniform(self._min_sleep_time, self._max_sleep_time) * self._num_workers
            await asyncio.sleep(sleep_time)
            logger.info(f'Fetching page of url {url}')
            await page.goto(url, wait_until='domcontentloaded', timeout=1000000)
            html_content = await page.content()
            await self._page_queue.put(page)
            yield url, BeautifulSoup(html_content, 'lxml')
            
    @abstractmethod
    async def parse_soup(self, soup: BeautifulSoup) -> str:
        '''
        Parse the soup and select the content of the article.
        :param soup: BeautifulSoup object of the article page.
        :return: The content of the article.
        '''
        pass
    
    async def __call__(self):
        async with self._sem:
            async for url, soup in self._generate_soup():
                content = await self.parse_soup(soup)
                logger.info(f'Got content: {content[:20].replace("\n", r"\n")}')
                async with self._table as table:
                    await table.fill_content(url, content)
                logger.info(f'Filled content for url {url}')

