from datetime import datetime
import asyncio

from aiolimiter import AsyncLimiter


class AsyncBlock:
    def __init__(self, interval: int):
        '''
        :param interval: time interval in seconds between each block of code to execute.
        '''
        self._interval = interval
        self._last_run = datetime.fromtimestamp(0.0)
        
    @property
    def interval(self):
        return self._interval
    
    def __await__(self):
        async def coro():
            diff = datetime.now() - self._last_run
            diff_seconds = diff.total_seconds()
            if diff_seconds <= self._interval:
                await asyncio.sleep(self._interval - diff_seconds)
            self._last_run = datetime.now()
        return coro().__await__()


async def coro(limiter: AsyncLimiter):
    await limiter.acquire()
    print(f'Start at {datetime.now()}')
        

async def demo():
    limiter = AsyncLimiter(20, 60)
    for i in range(20 - 1):
        await limiter.acquire()
    tasks = [coro(limiter) for _ in range(10)]
    await asyncio.gather(*tasks)

    
    
if __name__ == '__main__':
    asyncio.run(demo())
    