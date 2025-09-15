
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web of Science 论文搜索工具
支持基于关键词搜索论文，获取标题、摘要、作者、下载链接等信息
输出格式支持JSON和拼接文本两种形式
"""

import requests
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, asdict
from urllib.parse import quote, urlencode
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PaperInfo:
    """论文信息数据类"""
    title: str = ""
    abstract: str = ""
    authors: List[str] = None
    publication_date: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    download_link: str = ""
    citations: int = 0
    keywords: List[str] = None
    
    def __post_init__(self):
        """初始化后处理，确保列表字段不为None"""
        if self.authors is None:
            self.authors = []
        if self.keywords is None:
            self.keywords = []

class WebOfScienceSearcher:
    """Web of Science 搜索器主类"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化搜索器
        
        Args:
            api_key: Web of Science API密钥（可选，用于官方API访问）
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.base_url = "https://www.webofknowledge.com"
        self.api_base_url = "https://wos-api.clarivate.com/api/wos"
        
        # 设置请求头，模拟浏览器访问
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def search_papers_api(self, keyword: str, max_results: int = 10) -> List[PaperInfo]:
        """
        使用官方API搜索论文（需要API密钥）
        
        Args:
            keyword: 搜索关键词
            max_results: 最大返回结果数
            
        Returns:
            论文信息列表
        """
        if not self.api_key:
            logger.warning("未提供API密钥，无法使用官方API")
            return []
        
        papers = []
        try:
            # 构建API请求参数
            params = {
                'databaseId': 'WOS',
                'usrQuery': f'TS=({keyword})',
                'count': min(max_results, 100),  # API单次最多返回100条
                'firstRecord': 1
            }
            
            # 设置认证头
            headers = {
                'X-ApiKey': self.api_key,
                'Accept': 'application/json'
            }
            
            # 发送API请求
            response = self.session.get(
                f"{self.api_base_url}/query",
                params=params,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('Data', {}).get('Records', {}).get('records', {}).get('REC', [])
                
                for record in records:
                    paper = self._parse_api_record(record)
                    if paper:
                        papers.append(paper)
                        
            else:
                logger.error(f"API请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            logger.error(f"API搜索过程中发生错误: {e}")
        
        return papers[:max_results]
    
    def search_papers_web(self, keyword: str, max_results: int = 10) -> List[PaperInfo]:
        """
        通过网页爬虫搜索论文（备用方法）
        注意：需要遵守Web of Science的服务条款
        
        Args:
            keyword: 搜索关键词
            max_results: 最大返回结果数
            
        Returns:
            论文信息列表
        """
        papers = []
        try:
            logger.info(f"开始网页搜索，关键词: {keyword}, 最大结果数: {max_results}")
            
            # 模拟搜索请求
            search_url = f"{self.base_url}/wos/woscc/basic-search"
            search_data = {
                'search-mode': 'basic',
                'input[0][field]': 'AllField',
                'input[0][data]': keyword
            }
            
            # 这里需要实现具体的网页解析逻辑
            # 由于Web of Science的反爬虫机制，实际实现会比较复杂
            logger.warning("网页爬虫方法需要根据具体的Web of Science页面结构进行实现")
            
        except Exception as e:
            logger.error(f"网页搜索过程中发生错误: {e}")
        
        return papers
    
    def search_papers_mock(self, keyword: str, max_results: int = 10) -> List[PaperInfo]:
        """
        模拟搜索结果（用于演示和测试）
        
        Args:
            keyword: 搜索关键词
            max_results: 最大返回结果数
            
        Returns:
            模拟的论文信息列表
        """
        papers = []
        
        for i in range(min(max_results, 5)):  # 生成最多5条模拟数据
            paper = PaperInfo(
                title=f"Research on {keyword}: A Comprehensive Study {i+1}",
                abstract=f"This paper presents a comprehensive study on {keyword}. We investigate the latest developments and applications in this field. Our research methodology includes both theoretical analysis and experimental validation. The results show significant improvements in various aspects of {keyword} research. This work contributes to the advancement of knowledge in the field and provides valuable insights for future research directions.",
                authors=[f"Author {i+1}", f"Co-Author {i+1}", "Senior Researcher"],
                publication_date=f"202{i+1}-0{(i+1)%12+1}-15",
                journal=f"Journal of {keyword} Research",
                volume=f"{30+i}",
                issue=f"{i+1}",
                pages=f"{100+i*10}-{110+i*10}",
                doi=f"10.1000/journal.{keyword.lower()}.202{i+1}.00{i+1}",
                download_link=f"https://example.com/papers/{keyword.lower()}-{i+1}.pdf",
                citations=50 - i*5,
                keywords=[keyword, f"{keyword} applications", "research methodology"]
            )
            papers.append(paper)
        
        logger.info(f"生成了 {len(papers)} 条模拟论文数据")
        return papers
    
    def _parse_api_record(self, record: Dict) -> Optional[PaperInfo]:
        """
        解析API返回的论文记录
        
        Args:
            record: API返回的单个论文记录
            
        Returns:
            解析后的论文信息
        """
        try:
            # 提取基本信息
            static_data = record.get('static_data', {})
            summary = static_data.get('summary', {})
            fullrecord_metadata = static_data.get('fullrecord_metadata', {})
            
            # 标题
            title = ""
            titles = summary.get('titles', {}).get('title', [])
            for title_obj in titles:
                if title_obj.get('@type') == 'item':
                    title = title_obj.get('#text', '')
                    break
            
            # 作者
            authors = []
            names = summary.get('names', {}).get('name', [])
            for name in names:
                if name.get('@role') == 'author':
                    full_name = name.get('full_name', '')
                    if full_name:
                        authors.append(full_name)
            
            # 摘要
            abstract = ""
            abstracts = fullrecord_metadata.get('abstracts', {}).get('abstract', [])
            for abs_obj in abstracts:
                abstract_paragraphs = abs_obj.get('abstract_text', {}).get('p', [])
                if abstract_paragraphs:
                    abstract = ' '.join([p.get('#text', '') for p in abstract_paragraphs if isinstance(p, dict)])
                    break
            
            # 其他信息
            pub_info = summary.get('pub_info', {})
            journal = pub_info.get('@sortname', '')
            volume = pub_info.get('@vol', '')
            issue = pub_info.get('@issue', '')
            pages = pub_info.get('page', {}).get('@content', '')
            pub_date = pub_info.get('@pubyear', '')
            
            # DOI
            doi = ""
            identifiers = static_data.get('item', {}).get('identifiers', {}).get('identifier', [])
            for identifier in identifiers:
                if identifier.get('@type') == 'doi':
                    doi = identifier.get('@value', '')
                    break
            
            return PaperInfo(
                title=title,
                abstract=abstract,
                authors=authors,
                publication_date=pub_date,
                journal=journal,
                volume=volume,
                issue=issue,
                pages=pages,
                doi=doi,
                download_link=f"https://doi.org/{doi}" if doi else "",
                keywords=[]
            )
            
        except Exception as e:
            logger.error(f"解析API记录时发生错误: {e}")
            return None
    
    def search_papers(self, keyword: str, max_results: int = 10, use_api: bool = True) -> List[PaperInfo]:
        """
        统一的论文搜索接口
        
        Args:
            keyword: 搜索关键词
            max_results: 最大返回结果数
            use_api: 是否优先使用API（如果有API密钥）
            
        Returns:
            论文信息列表
        """
        logger.info(f"开始搜索论文，关键词: '{keyword}', 最大结果数: {max_results}")
        
        papers = []
        
        # 首先尝试使用API
        if use_api and self.api_key:
            papers = self.search_papers_api(keyword, max_results)
            if papers:
                logger.info(f"通过API获取到 {len(papers)} 篇论文")
                return papers
        
        # 如果API不可用，尝试网页爬虫
        papers = self.search_papers_web(keyword, max_results)
        if papers:
            logger.info(f"通过网页爬虫获取到 {len(papers)} 篇论文")
            return papers
        
        # 如果都不可用，使用模拟数据
        logger.info("使用模拟数据进行演示")
        papers = self.search_papers_mock(keyword, max_results)
        
        return papers

class OutputFormatter:
    """输出格式化器"""
    
    @staticmethod
    def to_json(papers: List[PaperInfo], indent: int = 2) -> str:
        """
        将论文信息转换为JSON格式
        
        Args:
            papers: 论文信息列表
            indent: JSON缩进级别
            
        Returns:
            JSON格式字符串
        """
        papers_dict = [asdict(paper) for paper in papers]
        
        # 添加元数据
        output = {
            "search_metadata": {
                "total_results": len(papers),
                "timestamp": datetime.now().isoformat(),
                "format": "json"
            },
            "papers": papers_dict
        }
        
        return json.dumps(output, ensure_ascii=False, indent=indent)
    
    @staticmethod
    def to_text(papers: List[PaperInfo]) -> str:
        """
        将论文信息转换为拼接文本格式
        
        Args:
            papers: 论文信息列表
            
        Returns:
            格式化的文本字符串
        """
        if not papers:
            return "未找到相关论文。"
        
        text_parts = []
        text_parts.append("=" * 80)
        text_parts.append(f"Web of Science 搜索结果")
        text_parts.append(f"共找到 {len(papers)} 篇相关论文")
        text_parts.append(f"搜索时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        text_parts.append("=" * 80)
        text_parts.append("")
        
        for i, paper in enumerate(papers, 1):
            text_parts.append(f"【论文 {i}】")
            text_parts.append(f"标题: {paper.title}")
            text_parts.append(f"作者: {', '.join(paper.authors) if paper.authors else '未提供'}")
            text_parts.append(f"期刊: {paper.journal}")
            text_parts.append(f"发表日期: {paper.publication_date}")
            
            if paper.volume or paper.issue or paper.pages:
                pub_info = []
                if paper.volume:
                    pub_info.append(f"第{paper.volume}卷")
                if paper.issue:
                    pub_info.append(f"第{paper.issue}期")
                if paper.pages:
                    pub_info.append(f"页码: {paper.pages}")
                text_parts.append(f"出版信息: {', '.join(pub_info)}")
            
            if paper.doi:
                text_parts.append(f"DOI: {paper.doi}")
            
            if paper.citations:
                text_parts.append(f"被引次数: {paper.citations}")
            
            if paper.keywords:
                text_parts.append(f"关键词: {', '.join(paper.keywords)}")
            
            if paper.download_link:
                text_parts.append(f"下载链接: {paper.download_link}")
            
            if paper.abstract:
                text_parts.append("摘要:")
                # 格式化摘要，每行不超过80字符
                abstract_lines = []
                words = paper.abstract.split()
                current_line = ""
                for word in words:
                    if len(current_line + word + " ") <= 76:  # 留出缩进空间
                        current_line += word + " "
                    else:
                        if current_line:
                            abstract_lines.append(f"    {current_line.strip()}")
                        current_line = word + " "
                if current_line:
                    abstract_lines.append(f"    {current_line.strip()}")
                text_parts.extend(abstract_lines)
            
            text_parts.append("-" * 40)
            text_parts.append("")
        
        return "\n".join(text_parts)

def main():
    """主函数，演示搜索器的使用方法"""
    
    # 创建搜索器实例
    # 如果有API密钥，可以传入: searcher = WebOfScienceSearcher(api_key="your_api_key_here")
    searcher = WebOfScienceSearcher()
    
    # 搜索参数
    keyword = "artificial intelligence"  # 可以修改为任何关键词
    max_results = 5  # 可以修改搜索结果数量
    
    print(f"正在搜索关键词: '{keyword}' 的相关论文...")
    print(f"最大搜索结果数: {max_results}")
    print("-" * 50)
    
    # 执行搜索
    papers = searcher.search_papers(keyword, max_results)
    
    if not papers:
        print("未找到相关论文，请检查关键词或网络连接。")
        return
    
    # 输出JSON格式
    formatter = OutputFormatter()
    
    print("\n" + "=" * 50)
    print("JSON格式输出:")
    print("=" * 50)
    json_output = formatter.to_json(papers)
    print(json_output)
    
    # 输出文本格式
    print("\n" + "=" * 50)
    print("文本格式输出:")
    print("=" * 50)
    text_output = formatter.to_text(papers)
    print(text_output)
    
    # 保存到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 保存JSON文件
    json_filename = f"wos_search_{keyword.replace(' ', '_')}_{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        f.write(json_output)
    print(f"JSON结果已保存到: {json_filename}")
    
    # 保存文本文件
    text_filename = f"wos_search_{keyword.replace(' ', '_')}_{timestamp}.txt"
    with open(text_filename, 'w', encoding='utf-8') as f:
        f.write(text_output)
    print(f"文本结果已保存到: {text_filename}")

if __name__ == "__main__":
    main()

    