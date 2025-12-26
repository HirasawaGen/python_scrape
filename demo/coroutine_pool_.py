import random
import asyncio
from typing import Awaitable


class CoroutinePool:
    def __init__(self, max_coroutine: int):
        self._max_coroutine = max_coroutine
        self._semaphore = asyncio.Semaphore(max_coroutine)
        self._event_loop = asyncio.get_event_loop()
    
    def __len__(self) -> int:
        return (self._max_coroutine - self._semaphore._value)
    
    async def done(self) -> None:
        while not self._event_loop.is_closed():
            await asyncio.sleep(1)
    
    def add(self, coro: Awaitable) -> None:
        async def wrapper() -> None:
            await self._semaphore.acquire()
            res = await coro
            await self._semaphore.release()
            return res
        self._event_loop.create_task(wrapper())


async def foo(arg: int) -> None:
    sleep_time = random.uniform(0.5, 3.0)
    print(f'Starting task {arg}')
    await asyncio.sleep(3)
    print(f'Finished task {arg}')


async def main():
    pool = CoroutinePool(3)
    print(len(pool))
    for i in range(12):
        print(len(pool))
        pool.add(foo(i))
    await pool.done()

if __name__ == '__main__':
    asyncio.run(main())
