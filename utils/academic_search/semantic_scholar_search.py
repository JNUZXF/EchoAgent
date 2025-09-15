
import requests
import json
from datetime import datetime

def search_latest_papers(keyword, year_filter=None, limit=10):
    """
    使用 Semantic Scholar API 检索与特定关键词相关的最新论文。

    Args:
        keyword (str): 要搜索的关键词。
        year_filter (str, optional): 用于筛选的年份范围，格式为 "YYYY" 或 "YYYY-YYYY"。
                                     例如 "2025" 或 "2024-2025"。默认为 None。
        limit (int): 希望返回的论文数量。

    Returns:
        list: 包含论文信息的字典列表，如果出错则返回 None。
    """
    print(f"正在检索关键词为 '{keyword}' 的论文...")
    if year_filter:
        print(f"年份筛选范围: {year_filter}")

    base_url = "https://api.semanticscholar.org/graph/v1"
    search_url = f"{base_url}/paper/search"

    params = {
        'query': keyword,
        'fields': 'title,abstract,authors,year,url',
        'sort': 'publicationDate:desc',
        'limit': limit
    }

    # 【核心改动】如果提供了年份过滤器，就将其添加到请求参数中
    if year_filter:
        params['year'] = year_filter

    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        search_results = response.json()
        
        papers = search_results.get('data', [])
        
        if not papers:
            print("未能找到符合条件的论文。请尝试调整关键词或年份范围。")
            return None
            
        return papers

    except requests.exceptions.RequestException as e:
        print(f"请求 API 时发生错误: {e}")
        return None
    except json.JSONDecodeError:
        print("解析返回的 JSON 数据时出错。")
        return None

def display_papers(papers):
    """
    清晰地打印和展示论文信息。
    """
    if not papers:
        return

    print(f"\n成功检索到 {len(papers)} 篇相关论文：")
    print("=" * 50)

    for i, paper in enumerate(papers, 1):
        title = paper.get('title', 'N/A')
        authors = ', '.join([author['name'] for author in paper.get('authors', [])])
        year = paper.get('year', 'N/A')
        abstract = paper.get('abstract', 'N/A')
        url = paper.get('url', 'N/A')

        print(f"--- {i} ---")
        print(f"标题 (Title): {title}")
        print(f"作者 (Authors): {authors}")
        print(f"年份 (Year): {year}")
        print(f"链接 (URL): {url}")
        print(f"摘要 (Abstract):\n{abstract}\n")
        print("-" * 50)


# --- 主程序入口 ---
if __name__ == "__main__":
    # 1. 优化关键词，使其更具体
    # 坏例子: "agent" (太宽泛)
    # 好例子: '"AI agent"' (使用引号进行精确匹配)
    # 更好的例子: '"large language model agent"'
    search_keyword = '"large language model agent"'
    
    # 2. 【推荐】设置年份过滤器，获取今年和去年的论文
    # 获取当前年份
    current_year = datetime.now().year
    previous_year = current_year - 1
    # 格式化为 "YYYY-YYYY" 字符串，例如 "2024-2025"
    year_range = f"{previous_year}-{current_year}"

    # 3. 设置希望获取的论文数量
    number_of_papers = 5

    # 调用函数进行搜索，这次传入了年份过滤器
    latest_papers = search_latest_papers(
        keyword=search_keyword,
        year_filter=year_range,
        limit=number_of_papers
    )

    if latest_papers:
        display_papers(latest_papers)


