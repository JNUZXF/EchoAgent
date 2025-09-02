# type: ignore

import os
from dotenv import load_dotenv
import requests
from typing import List, Dict, Optional, Union, Tuple
import time
import json
import hashlib
from pathlib import Path
import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from aiohttp import ClientTimeout
from aiohttp_retry import RetryClient, ExponentialRetry

load_dotenv()

TAVILY_KEY = os.getenv('TAVILY_KEY')

def is_jupyter() -> bool:
    """检查是否在Jupyter环境中运行"""
    try:
        from IPython import get_ipython
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':  # Jupyter notebook or qtconsole
            return True
        elif shell == 'TerminalInteractiveShell':  # Terminal IPython
            return False
        else:
            return False
    except (NameError, ImportError):  # 普通Python解释器或未安装IPython
        return False

def run_async(coro):
    """通用的异步运行函数，兼容Jupyter和命令行环境"""
    try:
        if is_jupyter():
            # 在Jupyter中使用nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coro)
        else:
            # 在普通Python环境中使用asyncio.run
            return asyncio.run(coro)
    except Exception as e:
        print(f"运行异步代码时出错: {str(e)}")
        return None

class TavilySearchAPI:
    """
    文件路径: tavily_api.py
    功能: 使用Tavily API进行网络搜索并格式化结果
    """
    
    def __init__(self, api_key: Optional[str] = None, 
                 cache_dir: str = ".cache",
                 cache_expiry: int = 3600,  # 缓存过期时间（秒）
                 max_retries: int = 3,
                 retry_delay: int = 1,
                 clean_content: bool = True,  # 是否清洗内容
                 max_concurrent_requests: int = 10,  # 最大并发请求数
                 request_timeout: int = 10):  # 请求超时时间（秒）
        self.api_key = api_key or TAVILY_KEY
        if not self.api_key:
            raise ValueError("Tavily API key is required")
        self.base_url = "https://api.tavily.com/search"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_expiry = cache_expiry
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.clean_content = clean_content
        self.max_concurrent_requests = max_concurrent_requests
        self.request_timeout = request_timeout
        self.session = None
        self.retry_options = ExponentialRetry(
            attempts=max_retries,
            start_timeout=retry_delay,
            max_timeout=retry_delay * 4,
            factor=2
        )
        
    async def _init_session(self):
        """初始化异步会话"""
        if self.session is None:
            timeout = ClientTimeout(total=self.request_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def _close_session(self):
        """关闭异步会话"""
        if self.session:
            await self.session.close()
            self.session = None

    async def _fetch_url_content(self, url: str) -> Tuple[str, str, str]:
        """异步获取URL内容"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            await self._init_session()
            retry_client = RetryClient(client_session=self.session, retry_options=self.retry_options)
            
            async with retry_client.get(url, headers=headers) as response:
                if response.status == 200:
                    html_content = await response.text()
                    return await self._process_html_content(html_content)
                return "", "", ""
        except Exception as e:
            print(f"获取URL内容失败 {url}: {str(e)}")
            return "", "", ""

    async def _process_html_content(self, html_content: str) -> Tuple[str, str, str]:
        """异步处理HTML内容"""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # 提取标题
            title = soup.title.text.strip() if soup.title else ""
            
            # 提取日期
            date = await self._extract_date(soup, html_content)
            
            # 提取主要内容
            content = await self._extract_main_content_async(soup)
            
            return title, content, date
        except Exception as e:
            print(f"处理HTML内容失败: {str(e)}")
            return "", "", ""

    async def _extract_date(self, soup: BeautifulSoup, html_content: str) -> str:
        """异步提取日期"""
        date = ""
        date_elements = soup.select('time, .date, .time, .publish-date, .post-date, meta[property="article:published_time"]')
        
        if date_elements:
            for element in date_elements:
                if element.name == 'meta':
                    date = element.get('content', '')
                else:
                    date = element.text.strip()
                if date:
                    date_match = re.search(r'(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})', date)
                    if date_match:
                        return date_match.group(1)
        
        # 在全文中查找日期
        date_pattern = r'(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})'
        date_match = re.search(date_pattern, html_content)
        return date_match.group(1) if date_match else ""

    async def _extract_main_content_async(self, soup: BeautifulSoup) -> str:
        """异步提取主要内容"""
        # 移除脚本和样式
        for script in soup(["script", "style"]):
            script.extract()
        
        # 尝试找到主要内容区域
        content_selectors = [
            'article', '.article', '.post', '.content', '.entry-content', 
            '#content', '#main', 'main', '.main', '.body', '.post-content'
        ]
        
        main_content = None
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                main_content = content_element
                break
        
        if not main_content:
            main_content = soup.body
        
        text = main_content.get_text(separator=' ', strip=True) if main_content else ""
        return self._clean_text(text)

    async def _process_search_results(self, results: List[dict]) -> List[dict]:
        """并发处理搜索结果"""
        if not results:
            return []
            
        tasks = []
        for result in results:
            if self.clean_content and result.get("url") != "无链接":
                task = self._fetch_url_content(result["url"])
                tasks.append(task)
            else:
                tasks.append(None)
        
        # 使用信号量限制并发请求数
        sem = asyncio.Semaphore(self.max_concurrent_requests)
        
        async def process_with_semaphore(task, result):
            if task:
                async with sem:
                    title, content, date = await task
                    if title:
                        result["title"] = title
                    if content:
                        result["content"] = content
                    if date:
                        result["published_date"] = date
            return result
        
        processed_results = await asyncio.gather(
            *[process_with_semaphore(task, result) 
              for task, result in zip(tasks, results)]
        )
        
        return processed_results

    async def async_search(self, query: str, **kwargs) -> Union[str, Dict]:
        """异步搜索方法"""
        try:
            params = {
                "query": query,
                "max_results": kwargs.get('max_results', 5),
                "search_type": kwargs.get('search_type', 'search'),
                "search_depth": kwargs.get('search_depth', 'advanced'),
                "include_answer": kwargs.get('include_answer', True),
                "include_raw_content": kwargs.get('include_raw_content', True),
                "include_images": kwargs.get('include_images', True),
                "language": kwargs.get('language', 'zh')
            }
            
            # 检查缓存
            if kwargs.get('use_cache', True):
                cache_key = self._get_cache_key(query, params)
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    return self._format_results(cached_result)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            await self._init_session()
            retry_client = RetryClient(client_session=self.session, retry_options=self.retry_options)
            
            async with retry_client.post(self.base_url, headers=headers, json=params) as response:
                response.raise_for_status()
                results = await response.json()
                
                # 并发处理搜索结果
                if results.get("results"):
                    results["results"] = await self._process_search_results(results["results"])
                
                # 保存到缓存
                if kwargs.get('use_cache', True):
                    self._save_to_cache(cache_key, results)
                
                return self._format_results(results)
                
        except Exception as e:
            return f"异步搜索出错: {str(e)}"
        finally:
            await self._close_session()

    def search(self, query: str, **kwargs) -> Union[str, Dict]:
        """同步搜索方法（内部使用异步实现）"""
        return run_async(self.async_search(query, **kwargs))

    def _clean_text(self, text: str) -> str:
        """清理文本内容"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符
        text = re.sub(r'[^\w\s\u4e00-\u9fff,.!?，。！？、:：()（）《》【】\-]', '', text)
        return text.strip()
    
    def _extract_main_content(self, url: str, raw_content: str = "") -> Tuple[str, str, str]:
        """
        从URL提取主要内容
        返回: (标题, 内容, 发布日期)
        """
        try:
            # 如果已经有原始内容，直接使用
            if raw_content:
                # 尝试从原始内容中提取标题和日期
                soup = BeautifulSoup(raw_content, 'lxml')
                title = soup.title.text if soup.title else ""
                
                # 尝试提取日期（常见的日期格式）
                date_pattern = r'(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})'
                date_match = re.search(date_pattern, raw_content)
                date = date_match.group(1) if date_match else ""
                
                # 清理内容
                # 移除脚本和样式
                for script in soup(["script", "style"]):
                    script.extract()
                
                # 获取文本
                text = soup.get_text()
                cleaned_text = self._clean_text(text)
                
                return title, cleaned_text, date
            
            # 如果没有原始内容，尝试从URL获取
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            try:
                # 尝试使用requests获取内容
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                html_content = response.text
            except Exception as e:
                # 如果requests失败，尝试使用urllib
                try:
                    req = Request(url, headers=headers)
                    with urlopen(req, timeout=10) as response:
                        html_content = response.read().decode('utf-8', errors='ignore')
                except Exception as e2:
                    print(f"无法获取URL内容 {url}: {str(e2)}")
                    return "", raw_content, ""
            
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'lxml')
            
            # 提取标题
            title = soup.title.text.strip() if soup.title else ""
            
            # 尝试提取日期
            # 方法1: 查找常见的日期元素
            date = ""
            date_elements = soup.select('time, .date, .time, .publish-date, .post-date, meta[property="article:published_time"]')
            if date_elements:
                for element in date_elements:
                    if element.name == 'meta':
                        date = element.get('content', '')
                    else:
                        date = element.text.strip()
                    if date:
                        # 尝试提取日期格式
                        date_match = re.search(r'(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})', date)
                        if date_match:
                            date = date_match.group(1)
                            break
            
            # 方法2: 如果上面方法没找到日期，在全文中查找日期模式
            if not date:
                date_pattern = r'(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})'
                date_match = re.search(date_pattern, html_content)
                date = date_match.group(1) if date_match else ""
            
            # 清理内容
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.extract()
            
            # 尝试找到主要内容区域
            main_content = None
            
            # 常见的内容容器选择器
            content_selectors = [
                'article', '.article', '.post', '.content', '.entry-content', 
                '#content', '#main', 'main', '.main', '.body', '.post-content'
            ]
            
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    main_content = content_element
                    break
            
            # 如果没找到主要内容区域，使用整个body
            if not main_content:
                main_content = soup.body
            
            # 获取文本
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            # 清理文本
            cleaned_text = self._clean_text(text)
            
            return title, cleaned_text, date
            
        except Exception as e:
            print(f"提取内容出错 {url}: {str(e)}")
            return "", raw_content, ""
    
    def _get_cache_key(self, query: str, params: dict) -> str:
        """生成缓存键"""
        cache_data = f"{query}_{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[dict]:
        """获取缓存的搜索结果"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
            
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
            
        # 检查缓存是否过期
        if time.time() - cached_data['timestamp'] > self.cache_expiry:
            cache_file.unlink()  # 删除过期缓存
            return None
            
        return cached_data['results']
    
    def _save_to_cache(self, cache_key: str, results: dict):
        """保存结果到缓存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_data = {
            'timestamp': time.time(),
            'results': results
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False)
    
    def _format_results(self, results: dict) -> str:
        """格式化搜索结果"""
        if not results.get("results"):
            return "未找到相关结果"
        
        formatted_results = []
        
        # 如果有AI生成的答案，添加到结果中
        if results.get("answer"):
            formatted_results.append(f"AI总结:\n{results['answer']}\n---")
        
        for result in results.get("results", []):
            sections = []
            url = result.get("url", "无链接")
            
            # 获取原始内容
            raw_content = result.get("raw_content", "")
            content = result.get("content", "")
            
            if self.clean_content and url != "无链接":
                # 提取和清洗内容
                extracted_title, extracted_content, extracted_date = self._extract_main_content(url, raw_content or content)
                
                # 使用提取的标题（如果有）
                title = extracted_title or result.get("title", "无标题")
                sections.append(f"标题: {title}")
                
                # 使用提取的内容
                if extracted_content:
                    sections.append(f"内容:\n{extracted_content}")
                else:
                    sections.append(f"内容:\n{content}")
                
                # 使用提取的日期（如果有）
                if extracted_date:
                    sections.append(f"发布时间: {extracted_date}")
            else:
                # 使用原始数据
                title = result.get("title", "无标题")
                sections.append(f"标题: {title}")
                sections.append(f"内容:\n{raw_content or content}")
            
            # 添加URL
            sections.append(f"链接: {url}")
            
            # 添加原始发布时间（如果有）
            if "published_date" in result and not self.clean_content:
                sections.append(f"发布时间: {result['published_date']}")
            
            # 添加相关性分数（如果有）
            if "score" in result:
                sections.append(f"相关性分数: {result['score']:.2f}")
            
            # 添加摘要（如果有且没有清洗内容）
            if "snippet" in result and not self.clean_content:
                sections.append(f"摘要: {result['snippet']}")
            
            # 添加图片链接（如果有）
            if "image_url" in result and result["image_url"]:
                sections.append(f"图片链接: {result['image_url']}")
            
            formatted_results.append("\n".join(sections))
        
        return "\n\n---\n\n".join(formatted_results)

# 测试代码
if __name__ == "__main__":
    # 创建API实例时可以配置并发数和超时时间
    search_api = TavilySearchAPI(
        max_concurrent_requests=10,  # 最大并发请求数
        request_timeout=10,  # 请求超时时间（秒）
        clean_content=True  # 是否清理内容
    )

    # 测试函数
    def test_search():
        # 同步方法测试
        print("\n同步搜索测试:")
        results = search_api.search(
            "Agent算法",
            max_results=3,
            search_depth="advanced"
        )
        print(results)

        # 异步方法测试
        print("\n异步搜索测试:")
        async def async_test():
            results = await search_api.async_search(
                "Agent算法",
                max_results=3,
                search_depth="advanced"
            )
            print(results)
        
        run_async(async_test())

    # 运行测试
    test_search()




