from typing import Callable, Awaitable
from asyncio import Semaphore
import asyncio
import time
import random


def concurrent_limit[**P, R](
    max_coroutine: int
) -> Callable[
    [Callable[P, Awaitable[R]]],
    Callable[P, Awaitable[R]]
]:
    def deco(
        func: Callable[P, Awaitable[R]]
    ) -> Callable[P, Awaitable[R]]:
        if not hasattr(func, '__semaphore__'):
            setattr(
                func,
                '__semaphore__',
                Semaphore(max_coroutine)
            )
        async def wrapper(
            *args: P.args,
            **kwargs: P.kwargs
        ) -> R:
            sem = getattr(func, '__semaphore__')
            async with sem:
                return await func(
                    *args,
                    **kwargs
                )
        return wrapper
    return deco



@concurrent_limit(3)
async def foo(arg: int) -> None:
    sleep_time = random.uniform(0.5, 3.0)
    print(f'Starting task {arg}')
    await asyncio.sleep(sleep_time)
    print(f'Finished task {arg}')
    

async def main():
    tasks = [foo(i) for i in range(12)]
    await asyncio.gather(*tasks)

async def main1():
    tasks1 = [foo(i) for i in range(1, 3)]
    tasks2 = [foo(i) for i in range(3, 6)]
    tasks3 = [foo(i) for i in range(6, 9)]
    tasks4 = [foo(i) for i in range(9, 12)]
    await asyncio.gather(*tasks1)
    await asyncio.gather(*tasks2)
    await asyncio.gather(*tasks3)
    await asyncio.gather(*tasks4)
    
    
if __name__ == '__main__':
    start_time = time.time_ns()
    asyncio.run(main1())
    end_time = time.time_ns()
    print(f'Execution time: {(end_time - start_time) / 1e9} seconds')
    
        