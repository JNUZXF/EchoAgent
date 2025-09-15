
import arxiv
import requests
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from urllib.parse import urlparse
import threading
from pathlib import Path
from enum import Enum

class SearchField(Enum):
    """搜索字段枚举"""
    ALL = "all"                    # 全文搜索
    TITLE = "ti"                   # 标题
    AUTHOR = "au"                  # 作者
    ABSTRACT = "abs"               # 摘要
    COMMENT = "co"                 # 评论
    JOURNAL_REFERENCE = "jr"       # 期刊引用
    CATEGORY = "cat"               # 类别
    REPORT_NUMBER = "rn"           # 报告编号

@dataclass
class ArxivPaper:
    """ArXiv论文数据结构"""
    title: str
    authors: List[str]
    abstract: str
    pdf_url: str
    arxiv_id: str
    published: str
    categories: List[str]

class ArxivSearcher:
    """ArXiv论文检索和下载器"""
    
    def __init__(self, download_dir: str = "./arxiv_papers", max_workers: int = 5):
        """
        初始化ArXiv检索器
        
        Args:
            download_dir: 论文下载目录
            max_workers: 最大并发下载数
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.max_workers = max_workers
        self.papers: List[ArxivPaper] = []
        self.lock = threading.Lock()
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 设置arxiv客户端
        self.client = arxiv.Client(
            page_size=100,
            delay_seconds=1.0,
            num_retries=3
        )
    
    def _build_query(self, 
                     query: str, 
                     search_field: SearchField = SearchField.ALL,
                     categories: Optional[List[str]] = None,
                     authors: Optional[List[str]] = None,
                     date_range: Optional[Tuple[str, str]] = None) -> str:
        """
        构建搜索查询字符串
        
        Args:
            query: 搜索关键词
            search_field: 搜索字段
            categories: 限制搜索的类别
            authors: 作者限制
            date_range: 日期范围 (start_date, end_date) 格式: "YYYY-MM-DD"
            
        Returns:
            构建的查询字符串
        """
        # 基础查询
        if search_field == SearchField.ALL:
            base_query = f'"{query}"' if ' ' in query else query
        else:
            base_query = f'{search_field.value}:"{query}"' if ' ' in query else f'{search_field.value}:{query}'
        
        query_parts = [base_query]
        
        # 添加类别限制
        if categories:
            category_query = " OR ".join([f"cat:{cat}" for cat in categories])
            query_parts.append(f"({category_query})")
        
        # 添加作者限制
        if authors:
            author_query = " OR ".join([f'au:"{author}"' for author in authors])
            query_parts.append(f"({author_query})")
        
        # 添加日期范围（ArXiv的日期查询比较复杂，这里提供基础实现）
        if date_range:
            start_date, end_date = date_range
            # 注意：ArXiv的日期查询格式可能需要调整
            query_parts.append(f"submittedDate:[{start_date} TO {end_date}]")
        
        return " AND ".join(query_parts)
    
    def search_by_title(self, 
                       title_keywords: Union[str, List[str]], 
                       search_num: int = 10,
                       exact_match: bool = False,
                       sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
                       sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending,
                       categories: Optional[List[str]] = None) -> List[ArxivPaper]:
        """
        按标题搜索论文
        
        Args:
            title_keywords: 标题关键词，可以是字符串或关键词列表
            search_num: 检索论文数量
            exact_match: 是否精确匹配（使用引号包围）
            sort_by: 排序方式
            sort_order: 排序顺序
            categories: 限制搜索的类别
            
        Returns:
            论文列表
        """
        if isinstance(title_keywords, list):
            if exact_match:
                query = f'ti:"{" ".join(title_keywords)}"'
            else:
                query = " AND ".join([f'ti:{keyword}' for keyword in title_keywords])
        else:
            if exact_match:
                query = f'ti:"{title_keywords}"'
            else:
                query = f'ti:{title_keywords}'
        
        return self._execute_search(query, search_num, sort_by, sort_order, categories)
    
    def search_by_author(self, 
                        author_name: str, 
                        search_num: int = 10,
                        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.LastUpdatedDate,
                        sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending,
                        categories: Optional[List[str]] = None) -> List[ArxivPaper]:
        """
        按作者搜索论文
        
        Args:
            author_name: 作者姓名
            search_num: 检索论文数量
            sort_by: 排序方式
            sort_order: 排序顺序
            categories: 限制搜索的类别
            
        Returns:
            论文列表
        """
        query = f'au:"{author_name}"'
        return self._execute_search(query, search_num, sort_by, sort_order, categories)
    
    def search_by_abstract(self, 
                          abstract_keywords: Union[str, List[str]], 
                          search_num: int = 10,
                          sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
                          sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending,
                          categories: Optional[List[str]] = None) -> List[ArxivPaper]:
        """
        按摘要搜索论文
        
        Args:
            abstract_keywords: 摘要关键词
            search_num: 检索论文数量
            sort_by: 排序方式
            sort_order: 排序顺序
            categories: 限制搜索的类别
            
        Returns:
            论文列表
        """
        if isinstance(abstract_keywords, list):
            query = " AND ".join([f'abs:{keyword}' for keyword in abstract_keywords])
        else:
            query = f'abs:{abstract_keywords}'
        
        return self._execute_search(query, search_num, sort_by, sort_order, categories)
    
    def advanced_search(self,
                       title: Optional[str] = None,
                       author: Optional[str] = None,
                       abstract: Optional[str] = None,
                       categories: Optional[List[str]] = None,
                       search_num: int = 10,
                       sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
                       sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending) -> List[ArxivPaper]:
        """
        高级组合搜索
        
        Args:
            title: 标题关键词
            author: 作者姓名
            abstract: 摘要关键词
            categories: 类别限制
            search_num: 检索论文数量
            sort_by: 排序方式
            sort_order: 排序顺序
            
        Returns:
            论文列表
        """
        query_parts = []
        
        if title:
            query_parts.append(f'ti:"{title}"' if ' ' in title else f'ti:{title}')
        
        if author:
            query_parts.append(f'au:"{author}"')
        
        if abstract:
            query_parts.append(f'abs:"{abstract}"' if ' ' in abstract else f'abs:{abstract}')
        
        if not query_parts:
            raise ValueError("至少需要指定一个搜索条件")
        
        query = " AND ".join(query_parts)
        return self._execute_search(query, search_num, sort_by, sort_order, categories)
    
    def search_papers(self, 
                     query: str, 
                     search_num: int = 10,
                     search_field: SearchField = SearchField.ALL,
                     sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
                     sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending,
                     categories: Optional[List[str]] = None) -> List[ArxivPaper]:
        """
        通用搜索论文（保持向后兼容）
        
        Args:
            query: 搜索关键词/主题
            search_num: 检索论文数量
            search_field: 搜索字段
            sort_by: 排序方式
            sort_order: 排序顺序
            categories: 限制搜索的类别
        
        Returns:
            论文列表
        """
        search_query = self._build_query(query, search_field, categories)
        return self._execute_search(search_query, search_num, sort_by, sort_order)
    
    def _execute_search(self, 
                       query: str, 
                       search_num: int,
                       sort_by: arxiv.SortCriterion,
                       sort_order: arxiv.SortOrder,
                       categories: Optional[List[str]] = None) -> List[ArxivPaper]:
        """
        执行搜索的内部方法
        """
        try:
            # 如果有类别限制且查询中没有包含，则添加
            if categories and "cat:" not in query:
                category_query = " OR ".join([f"cat:{cat}" for cat in categories])
                query = f"({query}) AND ({category_query})"
            
            self.logger.info(f"开始检索论文，查询: {query}, 数量: {search_num}")
            
            # 创建搜索对象
            search = arxiv.Search(
                query=query,
                max_results=search_num,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            # 执行搜索
            papers = []
            for result in self.client.results(search):
                paper = ArxivPaper(
                    title=result.title.strip(),
                    authors=[author.name for author in result.authors],
                    abstract=result.summary.strip().replace('\n', ' '),
                    pdf_url=result.pdf_url,
                    arxiv_id=result.entry_id.split('/')[-1],
                    published=result.published.strftime('%Y-%m-%d'),
                    categories=result.categories
                )
                papers.append(paper)
            
            self.papers = papers
            self.logger.info(f"成功检索到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            self.logger.error(f"检索论文时出错: {str(e)}")
            return []
    
    def get_papers_info(self) -> List[Dict]:
        """
        获取论文信息列表
        
        Returns:
            包含标题、作者、摘要、论文链接的字典列表
        """
        papers_info = []
        for paper in self.papers:
            info = {
                'title': paper.title,
                'authors': ', '.join(paper.authors),
                'abstract': paper.abstract,
                'pdf_url': paper.pdf_url,
                'arxiv_id': paper.arxiv_id,
                'published': paper.published,
                'categories': ', '.join(paper.categories)
            }
            papers_info.append(info)
        return papers_info
    
    def print_papers_summary(self):
        """打印论文摘要信息"""
        if not self.papers:
            print("没有找到论文")
            return
        
        print(f"\n找到 {len(self.papers)} 篇论文:")
        print("=" * 80)
        
        for i, paper in enumerate(self.papers, 1):
            print(f"\n{i}. 标题: {paper.title}")
            print(f"   作者: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}")
            print(f"   发布日期: {paper.published}")
            print(f"   类别: {', '.join(paper.categories)}")
            print(f"   ArXiv ID: {paper.arxiv_id}")
            print(f"   摘要: {paper.abstract[:200]}...")
            print(f"   PDF链接: {paper.pdf_url}")

    def get_formatted_papers_info(self, query: str, search_num: int) -> str:
        """
        获取格式化的论文信息
        
        Returns:
            str: 格式化的论文信息
        """
        self._execute_search(
            query, 
            search_num,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending,
            categories=None
        )
        
        formatted_info = ""
        for i, paper in enumerate(self.papers, 1):
            formatted_info += f"""
{i}. 标题: {paper.title}\n
作者: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}\n
发布日期: {paper.published}\n
类别: {', '.join(paper.categories)}\n
ArXiv ID: {paper.arxiv_id}\n
摘要: {paper.abstract}\n
"""
        return formatted_info
    

    def _download_single_paper(self, paper: ArxivPaper, timeout: int = 30) -> Tuple[bool, str]:
        """
        下载单篇论文
        
        Args:
            paper: 论文对象
            timeout: 下载超时时间
            
        Returns:
            (是否成功, 消息)
        """
        try:
            # 生成文件名
            safe_title = "".join(c for c in paper.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:100]  # 限制文件名长度
            filename = f"{paper.arxiv_id}_{safe_title}.pdf"
            filepath = self.download_dir / filename
            
            # 检查文件是否已存在
            if filepath.exists():
                return True, f"文件已存在: {filename}"
            
            # 下载PDF
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(paper.pdf_url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # 保存文件
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = filepath.stat().st_size / (1024 * 1024)  # MB
            return True, f"下载成功: {filename} ({file_size:.2f} MB)"
            
        except requests.exceptions.RequestException as e:
            return False, f"下载失败 {paper.arxiv_id}: 网络错误 - {str(e)}"
        except Exception as e:
            return False, f"下载失败 {paper.arxiv_id}: {str(e)}"
    
    def download_papers(self, 
                       papers: Optional[List[ArxivPaper]] = None,
                       timeout: int = 30,
                       retry_failed: bool = True) -> Dict[str, int]:
        """
        批量多进程下载论文
        
        Args:
            papers: 要下载的论文列表，默认为搜索结果
            timeout: 单个文件下载超时时间
            retry_failed: 是否重试失败的下载
            
        Returns:
            下载统计信息
        """
        if papers is None:
            papers = self.papers
        
        if not papers:
            self.logger.warning("没有论文需要下载")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        self.logger.info(f"开始下载 {len(papers)} 篇论文到 {self.download_dir}")
        
        stats = {'success': 0, 'failed': 0, 'skipped': 0}
        failed_papers = []
        
        # 使用线程池进行并发下载
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_paper = {
                executor.submit(self._download_single_paper, paper, timeout): paper 
                for paper in papers
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    success, message = future.result()
                    
                    with self.lock:
                        if success:
                            if "已存在" in message:
                                stats['skipped'] += 1
                            else:
                                stats['success'] += 1
                            self.logger.info(message)
                        else:
                            stats['failed'] += 1
                            failed_papers.append(paper)
                            self.logger.error(message)
                            
                except Exception as e:
                    with self.lock:
                        stats['failed'] += 1
                        failed_papers.append(paper)
                        self.logger.error(f"下载任务异常 {paper.arxiv_id}: {str(e)}")
        
        # 重试失败的下载
        if retry_failed and failed_papers:
            self.logger.info(f"重试下载 {len(failed_papers)} 篇失败的论文")
            time.sleep(2)  # 等待一段时间再重试
            
            retry_stats = self.download_papers(failed_papers, timeout, retry_failed=False)
            stats['success'] += retry_stats['success']
            stats['failed'] = retry_stats['failed']
            stats['skipped'] += retry_stats['skipped']
        
        # 输出统计信息
        self.logger.info(f"下载完成 - 成功: {stats['success']}, "
                        f"失败: {stats['failed']}, 跳过: {stats['skipped']}")
        
        return stats
    
    def search_and_download(self,
                           query: str,
                           search_num: int = 10,
                           search_field: SearchField = SearchField.ALL,
                           download: bool = True,
                           **search_kwargs) -> Tuple[List[ArxivPaper], Dict[str, int]]:
        """
        一键搜索并下载论文
        
        Args:
            query: 搜索查询
            search_num: 搜索数量
            search_field: 搜索字段
            download: 是否下载
            **search_kwargs: 搜索的其他参数
            
        Returns:
            (论文列表, 下载统计)
        """
        # 搜索论文
        papers = self.search_papers(query, search_num, search_field, **search_kwargs)
        
        download_stats = {'success': 0, 'failed': 0, 'skipped': 0}
        
        if download and papers:
            # 下载论文
            download_stats = self.download_papers(papers)
        
        return papers, download_stats
    
    def export_papers_info(self, filename: str = "papers_info.txt"):
        """
        导出论文信息到文件
        
        Args:
            filename: 导出文件名
        """
        if not self.papers:
            self.logger.warning("没有论文信息可导出")
            return
        
        filepath = self.download_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"ArXiv论文检索结果 - 共 {len(self.papers)} 篇\n")
            f.write("=" * 80 + "\n\n")
            
            for i, paper in enumerate(self.papers, 1):
                f.write(f"{i}. 标题: {paper.title}\n")
                f.write(f"   作者: {', '.join(paper.authors)}\n")
                f.write(f"   发布日期: {paper.published}\n")
                f.write(f"   类别: {', '.join(paper.categories)}\n")
                f.write(f"   ArXiv ID: {paper.arxiv_id}\n")
                f.write(f"   PDF链接: {paper.pdf_url}\n")
                f.write(f"   摘要: {paper.abstract}\n")
                f.write("-" * 80 + "\n\n")
        
        self.logger.info(f"论文信息已导出到: {filepath}")

if __name__ == "__main__":
    searcher = ArxivSearcher()
    formatted_info = searcher.get_formatted_papers_info(query="Agent", search_num=5)
    print(formatted_info)

