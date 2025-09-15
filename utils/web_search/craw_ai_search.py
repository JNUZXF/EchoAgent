

"""

pip install --upgrade crawl4ai --user

"""


import asyncio
from crawl4ai import AsyncWebCrawler

url = "https://quote.eastmoney.com/sz000670.html"

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)
        print(result.markdown[:300])  # Print first 300 chars

if __name__ == "__main__":
    asyncio.run(main())

