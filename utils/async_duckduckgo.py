# agent/utils/async_duckduckgo.py
# 功能：异步版本的DuckDuckGo搜索器，提供高性能并发抓取功能
# 路径：agent/utils/async_duckduckgo.py
# type: ignore
import asyncio
import aiohttp
import time
import json
import urllib.parse
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import logging
from typing import List, Dict, Optional, AsyncGenerator
from urllib.robotparser import RobotFileParser
import aiofiles
from dataclasses import dataclass, field
from datetime import datetime
import weakref

@dataclass
class SearchConfig:
    """搜索配置类"""
    delay: float = 0.5  # 请求间隔时间（秒）
    max_concurrent: int = 20  # 最大并发数
    timeout: int = 15  # 请求超时时间
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 1.0  # 重试延迟
    max_content_length: int = 10000  # 最大内容长度
    max_links_per_page: int = 20  # 每页最大链接数
    
@dataclass
class SearchResult:
    """搜索结果数据类"""
    title: str
    url: str
    description: str
    domain: str
    rank: int
    page_content: Optional[Dict] = None

@dataclass
class PageContent:
    """页面内容数据类"""
    url: str
    title: str = ""
    meta_description: str = ""
    content: str = ""
    content_length: int = 0
    links: List[Dict] = field(default_factory=list)
    status: str = "pending"
    error: Optional[str] = None
    fetch_time: float = 0.0

class AsyncDuckDuckGoSearcher:
    """异步DuckDuckGo搜索器"""
    
    def __init__(self, config: SearchConfig = None):
        """
        初始化异步DuckDuckGo搜索器
        
        Args:
            config: 搜索配置
        """
        self.config = config or SearchConfig()
        self.ua = UserAgent()
        self.session = None
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 通用请求头
        self.headers_template = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 性能统计
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_time': 0.0,
            'average_time': 0.0
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_session()

    async def create_session(self):
        """创建HTTP会话"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(
                limit=self.config.max_concurrent,
                limit_per_host=self.config.max_concurrent // 2,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self.headers_template
            )
            self.logger.info("HTTP会话已创建")

    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
            self.logger.info("HTTP会话已关闭")

    def _get_headers(self) -> Dict[str, str]:
        """获取随机请求头"""
        headers = self.headers_template.copy()
        headers['User-Agent'] = self.ua.random
        return headers

    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """
        异步搜索DuckDuckGo
        
        Args:
            query: 搜索关键词
            num_results: 期望获取的结果数量
            
        Returns:
            搜索结果列表
        """
        self.logger.info(f"开始异步搜索关键词: {query}")
        start_time = time.time()
        
        if not self.session:
            await self.create_session()
        
        search_url = "https://duckduckgo.com/html/"
        results = []
        page = 0
        
        while len(results) < num_results:
            try:
                # 构建搜索参数
                params = {
                    'q': query,
                    'kl': 'wt-wt',
                    'df': '',
                }
                
                if page > 0:
                    params['s'] = page * 30
                
                # 执行搜索请求
                async with self.semaphore:
                    async with self.session.get(
                        search_url,
                        params=params,
                        headers=self._get_headers()
                    ) as response:
                        response.raise_for_status()
                        html_content = await response.text()
                
                # 解析搜索结果
                soup = BeautifulSoup(html_content, 'html.parser')
                search_results = soup.find_all('div', class_='web-result')
                
                if not search_results:
                    self.logger.warning(f"第{page+1}页未找到搜索结果")
                    break
                
                # 提取结果信息
                for result in search_results:
                    if len(results) >= num_results:
                        break
                    
                    try:
                        # 提取标题和链接
                        title_elem = result.find('a', class_='result__a')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href')
                        
                        # 处理DuckDuckGo的重定向链接
                        url = self._parse_duckduckgo_url(url)
                        
                        # 提取描述
                        desc_elem = result.find('a', class_='result__snippet')
                        description = desc_elem.get_text(strip=True) if desc_elem else ""
                        
                        # 提取域名
                        domain_elem = result.find('span', class_='result__url')
                        domain = domain_elem.get_text(strip=True) if domain_elem else ""
                        
                        if url and title and self._is_valid_url(url):
                            # 跳过重复的URL
                            if not any(r.url == url for r in results):
                                results.append(SearchResult(
                                    title=title,
                                    url=url,
                                    description=description,
                                    domain=domain,
                                    rank=len(results) + 1
                                ))
                    
                    except Exception as e:
                        self.logger.error(f"解析单个结果时出错: {e}")
                        continue
                
                page += 1
                
                # 延迟避免被封
                if page > 0:
                    await asyncio.sleep(self.config.delay)
                
            except Exception as e:
                self.logger.error(f"搜索请求失败: {e}")
                break
        
        search_time = time.time() - start_time
        self.logger.info(f"搜索完成，获得 {len(results)} 个结果，耗时 {search_time:.2f}秒")
        
        return results[:num_results]

    def _parse_duckduckgo_url(self, url: str) -> str:
        """解析DuckDuckGo的重定向URL"""
        if not url:
            return ""
        
        # 处理相对URL
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = 'https://duckduckgo.com' + url
        
        # 如果是DuckDuckGo的重定向链接
        if 'duckduckgo.com/l/' in url:
            try:
                from urllib.parse import urlparse, parse_qs, unquote
                
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                
                # 从uddg参数中提取真实URL
                if 'uddg' in query_params:
                    real_url = unquote(query_params['uddg'][0])
                    return real_url
                
            except Exception as e:
                self.logger.warning(f"解析DuckDuckGo重定向URL失败: {e}")
                return url
        
        # 验证URL格式
        if not url.startswith(('http://', 'https://')):
            return ""
        
        return url

    def _is_valid_url(self, url: str) -> bool:
        """验证URL是否有效"""
        if not url:
            return False
        
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            
            # 检查基本格式
            if not parsed.scheme in ('http', 'https'):
                return False
            
            if not parsed.netloc:
                return False
            
            # 过滤掉一些无用的URL
            blacklist_patterns = [
                'javascript:',
                'mailto:',
                'tel:',
                'ftp:',
                '#',
                'about:blank'
            ]
            
            for pattern in blacklist_patterns:
                if pattern in url.lower():
                    return False
            
            return True
            
        except Exception:
            return False

    async def get_page_content(self, url: str) -> PageContent:
        """
        异步获取单个网页的内容
        
        Args:
            url: 网页URL
            
        Returns:
            页面内容对象
        """
        page_content = PageContent(url=url)
        start_time = time.time()
        
        try:
            # 验证URL格式
            if not self._is_valid_url(url):
                page_content.status = 'invalid_url'
                page_content.error = 'Invalid URL format'
                return page_content
            
            # 使用信号量限制并发
            async with self.semaphore:
                # 执行请求
                async with self.session.get(
                    url,
                    headers=self._get_headers()
                ) as response:
                    response.raise_for_status()
                    
                    # 检测编码
                    content_type = response.headers.get('content-type', '')
                    if 'text/html' not in content_type.lower():
                        page_content.status = 'not_html'
                        page_content.error = 'Content is not HTML'
                        return page_content
                    
                    html_content = await response.text()
            
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 移除脚本和样式标签
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # 提取基本信息
            if soup.title:
                page_content.title = soup.title.string.strip() if soup.title.string else ""
            
            # 提取meta描述
            meta_desc_tag = soup.find("meta", attrs={"name": "description"})
            if meta_desc_tag:
                page_content.meta_description = meta_desc_tag.get("content", "")
            
            # 提取主要内容
            content = self._extract_main_content(soup)
            page_content.content = content[:self.config.max_content_length]
            page_content.content_length = len(content)
            
            # 提取链接
            page_content.links = self._extract_links(soup, url)[:self.config.max_links_per_page]
            
            page_content.status = 'success'
            
        except asyncio.TimeoutError:
            page_content.status = 'timeout'
            page_content.error = 'Request timeout'
            self.logger.error(f"请求超时: {url}")
            
        except aiohttp.ClientError as e:
            page_content.status = 'client_error'
            page_content.error = str(e)
            self.logger.error(f"请求失败 {url}: {e}")
            
        except Exception as e:
            page_content.status = 'parse_error'
            page_content.error = str(e)
            self.logger.error(f"解析失败 {url}: {e}")
        
        finally:
            page_content.fetch_time = time.time() - start_time
            self._update_stats(page_content.status == 'success', page_content.fetch_time)
        
        return page_content

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """提取页面主要内容"""
        content = ""
        
        # 尝试多种内容提取策略
        content_selectors = [
            'article',
            'main',
            '.content',
            '.post',
            '.entry',
            '#content',
            '#main',
            'div[role="main"]'
        ]
        
        content_found = False
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = content_elem.get_text(separator='\n', strip=True)
                content_found = True
                break
        
        # 如果没找到主要内容区域，使用body
        if not content_found:
            body = soup.find('body')
            if body:
                content = body.get_text(separator='\n', strip=True)
        
        # 清理内容
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:  # 过滤掉太短的行
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """提取页面链接"""
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            link_text = link.get_text(strip=True)
            
            if href and link_text and len(link_text) > 2:
                # 转换相对链接为绝对链接
                if href.startswith('/'):
                    href = urllib.parse.urljoin(base_url, href)
                elif href.startswith('http'):
                    pass  # 已经是绝对链接
                else:
                    continue
                
                links.append({
                    'text': link_text[:100],  # 限制长度
                    'url': href
                })
        
        return links

    async def get_multiple_pages_content(self, urls: List[str]) -> List[PageContent]:
        """
        异步并发获取多个网页的内容
        
        Args:
            urls: URL列表
            
        Returns:
            页面内容列表
        """
        if not urls:
            return []
        
        self.logger.info(f"开始异步抓取 {len(urls)} 个网页内容")
        start_time = time.time()
        
        if not self.session:
            await self.create_session()
        
        # 创建任务列表
        tasks = []
        for url in urls:
            task = asyncio.create_task(self.get_page_content(url))
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        page_contents = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"获取 {urls[i]} 内容时出错: {result}")
                page_contents.append(PageContent(
                    url=urls[i],
                    status='error',
                    error=str(result)
                ))
            else:
                page_contents.append(result)
        
        total_time = time.time() - start_time
        successful_count = len([p for p in page_contents if p.status == 'success'])
        
        self.logger.info(f"内容抓取完成，成功获取 {successful_count}/{len(urls)} 个页面，总耗时 {total_time:.2f}秒")
        
        return page_contents

    async def search_and_get_content(self, query: str, num_results: int = 10) -> Dict:
        """
        异步搜索并获取所有结果页面的内容
        
        Args:
            query: 搜索关键词
            num_results: 期望获取的结果数量
            
        Returns:
            包含搜索结果和页面内容的完整数据
        """
        start_time = time.time()
        
        # 执行搜索
        search_results = await self.search(query, num_results)
        
        if not search_results:
            return {
                'query': query,
                'search_results': [],
                'pages_content': [],
                'summary': {
                    'total_results': 0,
                    'successful_fetches': 0,
                    'failed_fetches': 0,
                    'total_time': 0.0
                }
            }
        
        # 提取URL列表
        urls = [result.url for result in search_results]
        
        # 并发获取页面内容
        pages_content = await self.get_multiple_pages_content(urls)
        
        # 合并搜索结果和页面内容
        for i, search_result in enumerate(search_results):
            # 找到对应的页面内容
            page_content = None
            for content in pages_content:
                if content.url == search_result.url:
                    page_content = content
                    break
            
            search_result.page_content = page_content.__dict__ if page_content else None
        
        # 生成摘要
        successful_fetches = len([p for p in pages_content if p.status == 'success'])
        failed_fetches = len(pages_content) - successful_fetches
        total_time = time.time() - start_time
        
        return {
            'query': query,
            'search_results': [r.__dict__ for r in search_results],
            'pages_content': [p.__dict__ for p in pages_content],
            'summary': {
                'total_results': len(search_results),
                'successful_fetches': successful_fetches,
                'failed_fetches': failed_fetches,
                'total_time': total_time
            },
            'performance_stats': self.stats.copy()
        }

    def _update_stats(self, success: bool, request_time: float):
        """更新性能统计"""
        self.stats['total_requests'] += 1
        self.stats['total_time'] += request_time
        
        if success:
            self.stats['successful_requests'] += 1
        else:
            self.stats['failed_requests'] += 1
        
        self.stats['average_time'] = self.stats['total_time'] / self.stats['total_requests']

    async def save_results(self, results: Dict, filename: Optional[str] = None):
        """
        异步保存搜索结果到JSON文件
        
        Args:
            results: 搜索结果数据
            filename: 保存的文件名
        """
        if not filename:
            query = results.get('query', 'search')
            safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"async_duckduckgo_search_{safe_query}_{timestamp}.json"
        
        try:
            async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(results, ensure_ascii=False, indent=2))
            self.logger.info(f"结果已保存到: {filename}")
        except Exception as e:
            self.logger.error(f"保存文件失败: {e}")

    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        return {
            'config': self.config.__dict__,
            'stats': self.stats,
            'efficiency_metrics': {
                'success_rate': self.stats['successful_requests'] / max(1, self.stats['total_requests']),
                'average_time_per_request': self.stats['average_time'],
                'requests_per_second': self.stats['total_requests'] / max(0.1, self.stats['total_time'])
            }
        }

# 便捷函数
async def async_search_duckduckgo(query: str, num_results: int = 10, config: SearchConfig = None) -> Dict:
    """
    便捷的异步搜索函数
    
    Args:
        query: 搜索关键词
        num_results: 期望获取的结果数量
        config: 搜索配置
        
    Returns:
        搜索结果数据
    """
    async with AsyncDuckDuckGoSearcher(config) as searcher:
        return await searcher.search_and_get_content(query, num_results)

if __name__ == "__main__":
    async def main():
        """主函数 - 演示如何使用异步DuckDuckGo搜索工具"""
        # 创建搜索配置
        config = SearchConfig(
            delay=0.5,  # 减少延迟
            max_concurrent=30,  # 增加并发数
            timeout=10,
            max_retries=3
        )
        
        # 搜索关键词
        query = "贵州茅台 主营业务"
        num_results = 10
        
        start_time = time.time()
        
        # 使用异步搜索器
        async with AsyncDuckDuckGoSearcher(config) as searcher:
            results = await searcher.search_and_get_content(query, num_results)
            
            # 显示搜索摘要
            print(f"\n搜索摘要:")
            print(f"搜索关键词: {results['query']}")
            print(f"找到结果: {results['summary']['total_results']}")
            print(f"成功获取内容: {results['summary']['successful_fetches']}")
            print(f"获取失败: {results['summary']['failed_fetches']}")
            print(f"总耗时: {results['summary']['total_time']:.2f}秒")
            
            # 显示性能报告
            perf_report = searcher.get_performance_report()
            print(f"\n性能报告:")
            print(f"总请求数: {perf_report['stats']['total_requests']}")
            print(f"成功率: {perf_report['efficiency_metrics']['success_rate']:.2%}")
            print(f"平均请求时间: {perf_report['efficiency_metrics']['average_time_per_request']:.2f}秒")
            print(f"请求速率: {perf_report['efficiency_metrics']['requests_per_second']:.2f}次/秒")
            
            # 显示前5个搜索结果
            print(f"\n前5个搜索结果:")
            print("=" * 80)
            
            for i, result in enumerate(results['search_results'][:5], 1):
                print(f"\n{i}. {result['title']}")
                print(f"   URL: {result['url']}")
                print(f"   描述: {result['description'][:100]}...")
                
                # 显示页面内容摘要
                page_content = result.get('page_content')
                if page_content:
                    if page_content.get('status') == 'success':
                        content_preview = page_content.get('content', '')[:200]
                        print(f"   内容预览: {content_preview}...")
                        print(f"   内容长度: {page_content.get('content_length', 0)} 字符")
                        print(f"   获取时间: {page_content.get('fetch_time', 0):.2f}秒")
                    else:
                        print(f"   内容获取失败: {page_content.get('error', '未知错误')}")
                
                print("-" * 80)
            
            # 保存结果
            await searcher.save_results(results)
        
        total_time = time.time() - start_time
        print(f"\n异步搜索完成！总耗时: {total_time:.2f}秒")
    
    # 运行异步主函数
    asyncio.run(main()) 