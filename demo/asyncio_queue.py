from asyncio import Queue, Event
import asyncio

queue: Queue[str] = Queue(maxsize=3)
done = Event()


async def producer():
    for i in range(10):
        print(f'Producing item {i}')
        await asyncio.sleep(0.5)
        print(f'Produced item {i}')
        await queue.put(f'item {i}')
    done.set()

async def consumer():
    await asyncio.sleep(3)
    while True:
        item = await queue.get()
        print(f'Consuming {item}')
        await asyncio.sleep(3)
        print(f'Consumed {item}')
        queue.task_done()
        if done.is_set() and queue.empty():
            break

async def main():
    await asyncio.gather(producer(), consumer(), consumer())
    
if __name__ == '__main__':
    asyncio.run(main())