import asyncio
import random
from asyncio import Queue



POISON_PILL = None



async def producer(queue: Queue[int | None]):
    count = random.randint(5, 10)
    for i in range(count):
        await queue.put(i)
        print(f"Produced {i}")
        await asyncio.sleep(random.random())
    await queue.put(POISON_PILL)
    print("Produced done")


async def consumer(queue: Queue[int | None]):
    while True:
        item = await queue.get()
        queue.task_done()
        
        if item is POISON_PILL:
            break
        
        print(f"Consumed {item}")
        await asyncio.sleep(random.random())
    
    print("Consumer done")
    

async def main():
    queue: Queue[int | None] = Queue(maxsize=3)
    await asyncio.gather(
        producer(queue),
        consumer(queue)
    )


if __name__ == '__main__':
    asyncio.run(main())
