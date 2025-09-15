
"""

博查搜索，需要异步实现

"""


import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BOCHA_KEY")

async def search(query,count=10):
    url = "https://api.bochaai.com/v1/web-search"
    payload = json.dumps({
    "query": query,
    "summary": True,
    "count": count
    })

    headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    search_result = response.json()["data"]["webPages"]["value"]
    return search_result

async def test_search():
    question = "AI Agent最新进展"

    result = await search(question)
    print(result)
    search_result = result["data"]["webPages"]["value"]
    total_content = ""

    for item in search_result:
        temp_content = ""
        url = item["url"]
        summary = item["summary"]
        temp_content = f"url: {url}\nsummary: {summary}\n--------------------------------\n"
        total_content += temp_content
        print(total_content)
    print(total_content)

