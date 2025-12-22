import aiohttp
import asyncio


class AsyncHTTPRequest:
    def __init__(self, *args, **kwargs):
        self._session = aiohttp.ClientSession()
    
    async def fetch(self, url, **kwargs):
        async with self._session.get(url, **kwargs) as resp:
            return await resp.text()


async def main():
    async_http_request = AsyncHTTPRequest()
    response = await async_http_request.fetch('https://www.cnfeol.com/xitu/a-96.aspx')
    print(response)




if __name__ == '__main__':
    asyncio.run(main())
        