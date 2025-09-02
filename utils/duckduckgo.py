import requests
from bs4 import BeautifulSoup
import time
import json
import urllib.parse
from fake_useragent import UserAgent
import logging
from typing import List, Dict, Optional
import concurrent.futures
from urllib.robotparser import RobotFileParser

class DuckDuckGoSearcher:
    def __init__(self, delay: float = 1.0, max_workers: int = 5):
        """
        初始化DuckDuckGo搜索器
        
        Args:
            delay: 请求间隔时间（秒）
            max_workers: 并发抓取线程数
        """
        self.delay = delay
        self.max_workers = max_workers
        self.ua = UserAgent()
        self.session = requests.Session()
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 通用请求头
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def search(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        在DuckDuckGo上搜索关键词
        
        Args:
            query: 搜索关键词
            num_results: 期望获取的结果数量
            
        Returns:
            包含搜索结果的字典列表
        """
        self.logger.info(f"开始搜索关键词: {query}")
        
        # DuckDuckGo搜索URL
        search_url = "https://duckduckgo.com/html/"
        
        # 搜索参数
        params = {
            'q': query,
            'b': '',  # 结果偏移量
            'kl': 'wt-wt',  # 语言设置
            'df': '',  # 时间过滤
        }
        
        results = []
        page = 0
        
        while len(results) < num_results:
            try:
                # 设置分页参数
                if page > 0:
                    params['s'] = page * 30   # type: ignore
                
                # 更新User-Agent
                self.headers['User-Agent'] = self.ua.random
                
                # 发送请求
                response = self.session.get(
                    search_url, 
                    params=params, 
                    headers=self.headers,
                    timeout=10
                )
                response.raise_for_status()
                
                # 解析HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 查找搜索结果
                search_results = soup.find_all('div', class_='web-result')
                
                if not search_results:
                    self.logger.warning(f"第{page+1}页未找到搜索结果")
                    break
                
                # 提取结果信息
                for result in search_results:
                    if len(results) >= num_results:
                        break
                        
                    try:
                        # 标题和链接
                        title_elem = result.find('a', class_='result__a')
                        if not title_elem:
                            continue
                            
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href')
                        
                        # 处理DuckDuckGo的重定向链接
                        url = self._parse_duckduckgo_url(url)
                        
                        # 描述
                        desc_elem = result.find('a', class_='result__snippet')
                        description = desc_elem.get_text(strip=True) if desc_elem else ""
                        
                        # 域名
                        domain_elem = result.find('span', class_='result__url')
                        domain = domain_elem.get_text(strip=True) if domain_elem else ""
                        
                        if url and title and self._is_valid_url(url):
                            # 跳过重复的URL
                            if not any(r['url'] == url for r in results):
                                results.append({
                                    'title': title,
                                    'url': url,
                                    'description': description,
                                    'domain': domain,
                                    'rank': len(results) + 1
                                })
                            
                    except Exception as e:
                        self.logger.error(f"解析单个结果时出错: {e}")
                        continue
                
                page += 1
                
                # 延迟避免被封
                if page > 0:
                    time.sleep(self.delay)
                    
            except requests.RequestException as e:
                self.logger.error(f"搜索请求失败: {e}")
                break
            except Exception as e:
                self.logger.error(f"搜索过程中出现未知错误: {e}")
                break
        
        self.logger.info(f"搜索完成，获得 {len(results)} 个结果")
        return results[:num_results]

    def _parse_duckduckgo_url(self, url: str) -> str:
        """
        解析DuckDuckGo的重定向URL，提取真实的目标URL
        
        Args:
            url: DuckDuckGo的重定向URL
            
        Returns:
            真实的目标URL
        """
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
        """
        验证URL是否有效
        
        Args:
            url: 要验证的URL
            
        Returns:
            URL是否有效
        """
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

    def check_robots_txt(self, url: str) -> bool:
        """
        检查robots.txt是否允许抓取
        
        Args:
            url: 网页URL
            
        Returns:
            是否允许抓取
        """
        try:
            from urllib.parse import urljoin, urlparse
            
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            return rp.can_fetch(self.ua.random, url)
        except:
            return True  # 如果检查失败，默认允许抓取

    def get_page_content(self, url: str) -> Optional[Dict]:
        """
        获取单个网页的内容
        
        Args:
            url: 网页URL
            
        Returns:
            包含网页内容的字典，如果失败则返回None
        """
        try:
            # 验证URL格式
            if not self._is_valid_url(url):
                return {
                    'url': url,
                    'error': 'Invalid URL format',
                    'status': 'invalid_url'
                }
            
            # 检查robots.txt
            if not self.check_robots_txt(url):
                self.logger.warning(f"robots.txt禁止抓取: {url}")
                return {
                    'url': url,
                    'error': 'Robots.txt disallows crawling',
                    'status': 'robots_blocked'
                }
            
            # 设置请求头
            headers = self.headers.copy()
            headers['User-Agent'] = self.ua.random
            
            # 发送请求
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # 检测编码
            response.encoding = response.apparent_encoding
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除脚本和样式标签
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # 提取基本信息
            title = ""
            if soup.title:
                title = soup.title.string.strip() if soup.title.string else ""
            
            # 提取meta描述
            meta_desc = ""
            meta_desc_tag = soup.find("meta", attrs={"name": "description"})
            if meta_desc_tag:
                meta_desc = meta_desc_tag.get("content", "")  # type: ignore
            
            # 提取主要内容
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
            
            content = '\n'.join(cleaned_lines)
            
            # 提取链接
            links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                link_text = link.get_text(strip=True)
                if href and link_text and len(link_text) > 2:
                    # 转换相对链接为绝对链接
                    if href.startswith('/'):
                        from urllib.parse import urljoin
                        href = urljoin(url, href)
                    elif href.startswith('http'):
                        pass  # 已经是绝对链接
                    else:
                        continue
                    
                    links.append({
                        'text': link_text[:100],  # 限制长度
                        'url': href
                    })
            
            return {
                'url': url,
                'title': title,
                'meta_description': meta_desc,
                'content': content[:10000],  # 限制内容长度
                'content_length': len(content),
                'links': links[:20],  # 限制链接数量
                'status': 'success'
            }
            
        except requests.RequestException as e:
            self.logger.error(f"请求失败 {url}: {e}")
            return {
                'url': url,
                'error': str(e),
                'status': 'request_failed'
            }
        except Exception as e:
            self.logger.error(f"解析失败 {url}: {e}")
            return {
                'url': url,
                'error': str(e),
                'status': 'parse_failed'
            }

    def get_multiple_pages_content(self, urls: List[str]) -> List[Dict]:
        """
        并发获取多个网页的内容
        
        Args:
            urls: URL列表
            
        Returns:
            包含网页内容的字典列表
        """
        self.logger.info(f"开始抓取 {len(urls)} 个网页内容")
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_url = {
                executor.submit(self.get_page_content, url): url 
                for url in urls
            }
            
            # 获取结果
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                    
                    # 添加延迟避免过于频繁的请求
                    time.sleep(self.delay / self.max_workers)
                    
                except Exception as e:
                    self.logger.error(f"获取 {url} 内容时出错: {e}")
                    results.append({
                        'url': url,
                        'error': str(e),
                        'status': 'failed'
                    })
        
        self.logger.info(f"内容抓取完成，成功获取 {len([r for r in results if r.get('status') == 'success'])} 个页面")
        return results

    def search_and_get_content(self, query: str, num_results: int = 10) -> Dict:
        """
        搜索并获取所有结果页面的内容
        
        Args:
            query: 搜索关键词
            num_results: 期望获取的结果数量
            
        Returns:
            包含搜索结果和页面内容的完整数据
        """
        # 执行搜索
        search_results = self.search(query, num_results)
        
        if not search_results:
            return {
                'query': query,
                'search_results': [],
                'pages_content': [],
                'summary': {
                    'total_results': 0,
                    'successful_fetches': 0,
                    'failed_fetches': 0
                }
            }
        
        # 提取URL列表
        urls = [result['url'] for result in search_results]
        
        # 获取页面内容
        pages_content = self.get_multiple_pages_content(urls)
        
        # 合并搜索结果和页面内容
        for i, search_result in enumerate(search_results):
            # 找到对应的页面内容
            page_content = None
            for content in pages_content:
                if content['url'] == search_result['url']:
                    page_content = content
                    break
            
            search_result['page_content'] = page_content
        
        # 生成摘要
        successful_fetches = len([p for p in pages_content if p.get('status') == 'success'])
        failed_fetches = len(pages_content) - successful_fetches
        
        return {
            'query': query,
            'search_results': search_results,
            'pages_content': pages_content,
            'summary': {
                'total_results': len(search_results),
                'successful_fetches': successful_fetches,
                'failed_fetches': failed_fetches
            }
        }

    def save_results(self, results: Dict, filename: Optional[str] = None):
        """
        保存搜索结果到JSON文件
        
        Args:
            results: 搜索结果数据
            filename: 保存的文件名
        """
        if not filename:
            query = results.get('query', 'search')
            safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"duckduckgo_search_{safe_query}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            self.logger.info(f"结果已保存到: {filename}")
        except Exception as e:
            self.logger.error(f"保存文件失败: {e}")

def main():
    """
    主函数 - 演示如何使用DuckDuckGo搜索工具
    """
    # 创建搜索器实例
    searcher = DuckDuckGoSearcher(delay=2.0, max_workers=3)
    
    # 搜索关键词
    query = "三七互娱 公司介绍"
    num_results = 10
    
    # 执行搜索并获取内容
    results = searcher.search_and_get_content(query, num_results)
    
    # 显示搜索摘要
    print(f"\n搜索摘要:")
    print(f"搜索关键词: {results['query']}")
    print(f"找到结果: {results['summary']['total_results']}")
    print(f"成功获取内容: {results['summary']['successful_fetches']}")
    print(f"获取失败: {results['summary']['failed_fetches']}")
    
    # 显示搜索结果
    print(f"\n搜索结果:")
    print("=" * 80)
    
    for i, result in enumerate(results['search_results'], 1):
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
                print(f"   包含链接: {len(page_content.get('links', []))} 个")
            else:
                print(f"   内容获取失败: {page_content.get('error', '未知错误')}")
        
        print("-" * 80)
    
    # 保存结果
    save_option = input("\n是否保存结果到文件? (y/n): ").strip().lower()
    if save_option == 'y':
        searcher.save_results(results)
    
    print("\n搜索完成!")

if __name__ == "__main__":
    main()