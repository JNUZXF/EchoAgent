# type: ignore
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()


class BochaSearch:
    def execute(self, **kwargs):
        keyword = kwargs.get("keyword")
        count = kwargs.get("count", 10)
        
        url = "https://api.bochaai.com/v1/web-search"
        payload = json.dumps({
            "query": keyword,
            "summary": True,
            "count": count
        })

        BOCHA_KEY = os.getenv("BOCHA_KEY")
        headers = {
        'Authorization': f'Bearer {BOCHA_KEY}',
        'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        search_result = response.json()["data"]["webPages"]["value"]
        return search_result


if __name__ == "__main__":
    bocha_search = BochaSearch()
    kwargs = {
        "keyword": "歌尔股份",
        "count": 10
    }
    search_result = bocha_search.execute(**kwargs)
    print(search_result)