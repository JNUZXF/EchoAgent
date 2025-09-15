
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Scholar 论文搜索工具
功能：基于关键词搜索Google学术，获取论文信息并以JSON和文本格式输出

依赖库安装：
pip install scholarly requests beautifulsoup4 lxml

作者：Claude
版本：1.0
"""

import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import re

try:
    from scholarly import scholarly
except ImportError:
    print("请先安装 scholarly 库：pip install scholarly")
    exit(1)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PaperInfo:
    """论文信息数据类，用于结构化存储论文数据"""
    title: str = ""
    authors: List[str] = None
    year: Optional[int] = None
    journal: str = ""
    abstract: str = ""
    citations: int = 0
    url: str = ""
    pdf_url: str = ""
    doi: str = ""
    publisher: str = ""
    
    def __post_init__(self):
        """初始化后处理，确保authors是列表类型"""
        if self.authors is None:
            self.authors = []

class ScholarSearcher:
    """Google Scholar 搜索器类"""
    
    def __init__(self, delay: float = 1.0):
        """
        初始化搜索器
        
        Args:
            delay: 请求间隔时间（秒），用于控制访问频率
        """
        self.delay = delay
        self.results_cache = []
        
        # 设置scholarly的配置
        try:
            # 可选：使用代理（如果需要）
            # scholarly.use_proxy(http="http://proxy.example.com:8080")
            pass
        except Exception as e:
            logger.warning(f"代理设置失败：{e}")
    
    def search_papers(self, 
                     keywords: str, 
                     max_results: int = 10, 
                     year_low: Optional[int] = None,
                     year_high: Optional[int] = None,
                     sort_by: str = "relevance") -> List[PaperInfo]:
        """
        搜索论文并返回结构化数据
        
        Args:
            keywords: 搜索关键词
            max_results: 最大返回结果数
            year_low: 最早年份（可选）
            year_high: 最晚年份（可选）
            sort_by: 排序方式 ("relevance" 或 "date")
            
        Returns:
            List[PaperInfo]: 论文信息列表
        """
        logger.info(f"开始搜索关键词：{keywords}，期望获取{max_results}篇论文")
        
        papers = []
        
        try:
            # 构建搜索查询
            search_query = scholarly.search_pubs(keywords)
            
            count = 0
            for paper in search_query:
                if count >= max_results:
                    break
                
                try:
                    # 解析单篇论文信息
                    paper_info = self._extract_paper_info(paper)
                    
                    # 年份过滤
                    if self._is_year_in_range(paper_info.year, year_low, year_high):
                        papers.append(paper_info)
                        count += 1
                        logger.info(f"成功获取第{count}篇论文：{paper_info.title[:50]}...")
                    
                    # 控制请求频率
                    time.sleep(self.delay)
                    
                except Exception as e:
                    logger.error(f"解析论文信息时出错：{e}")
                    continue
        
        except Exception as e:
            logger.error(f"搜索过程中出错：{e}")
            return papers
        
        logger.info(f"搜索完成，共获取{len(papers)}篇论文")
        self.results_cache = papers
        return papers
    
    def _extract_paper_info(self, paper: Dict[str, Any]) -> PaperInfo:
        """
        从scholarly返回的论文数据中提取关键信息
        
        Args:
            paper: scholarly返回的论文字典
            
        Returns:
            PaperInfo: 结构化的论文信息
        """
        try:
            # 获取详细信息（这会发送额外的请求获取更多数据）
            paper_detail = scholarly.fill(paper)
        except:
            # 如果获取详细信息失败，使用基本信息
            paper_detail = paper
        
        # 安全获取字段值的辅助函数
        def safe_get(data, key, default=""):
            return data.get(key, default) if isinstance(data, dict) else default
        
        # 提取基本信息
        title = safe_get(paper_detail, 'title', '').strip()
        
        # 提取作者信息
        authors = []
        author_info = safe_get(paper_detail, 'author', [])
        if isinstance(author_info, list):
            authors = [author.get('name', '') if isinstance(author, dict) else str(author) 
                      for author in author_info]
        elif isinstance(author_info, str):
            authors = [author_info]
        
        # 提取年份
        year = None
        pub_year = safe_get(paper_detail, 'pub_year')
        if pub_year:
            try:
                year = int(pub_year)
            except (ValueError, TypeError):
                # 尝试从其他字段提取年份
                year_match = re.search(r'\b(19|20)\d{2}\b', str(paper_detail))
                if year_match:
                    year = int(year_match.group())
        
        # 提取其他字段
        journal = safe_get(paper_detail, 'venue', '')
        abstract = safe_get(paper_detail, 'abstract', '')
        citations = safe_get(paper_detail, 'num_citations', 0)
        
        # 尝试获取URL信息
        url = safe_get(paper_detail, 'pub_url', '')
        if not url:
            url = safe_get(paper_detail, 'eprint_url', '')
        
        # 查找PDF链接
        pdf_url = ""
        eprint_url = safe_get(paper_detail, 'eprint_url', '')
        if eprint_url and eprint_url.endswith('.pdf'):
            pdf_url = eprint_url
        
        # 其他字段
        doi = safe_get(paper_detail, 'doi', '')
        publisher = safe_get(paper_detail, 'publisher', '')
        
        return PaperInfo(
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            abstract=abstract,
            citations=citations,
            url=url,
            pdf_url=pdf_url,
            doi=doi,
            publisher=publisher
        )
    
    def _is_year_in_range(self, year: Optional[int], 
                         year_low: Optional[int], 
                         year_high: Optional[int]) -> bool:
        """检查年份是否在指定范围内"""
        if year is None:
            return True  # 如果没有年份信息，默认包含
        
        if year_low and year < year_low:
            return False
        
        if year_high and year > year_high:
            return False
        
        return True
    
    def export_to_json(self, papers: List[PaperInfo], filename: str = None) -> str:
        """
        将论文数据导出为JSON格式
        
        Args:
            papers: 论文信息列表
            filename: 保存文件名（可选）
            
        Returns:
            str: JSON格式的字符串
        """
        # 转换为字典格式
        papers_dict = [asdict(paper) for paper in papers]
        
        # 添加元数据
        export_data = {
            "metadata": {
                "export_time": datetime.now().isoformat(),
                "total_papers": len(papers),
                "tool_version": "1.0"
            },
            "papers": papers_dict
        }
        
        # 生成JSON字符串
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        
        # 保存到文件（如果指定了文件名）
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                logger.info(f"JSON数据已保存到：{filename}")
            except Exception as e:
                logger.error(f"保存JSON文件失败：{e}")
        
        return json_str
    
    def export_to_text(self, papers: List[PaperInfo], filename: str = None) -> str:
        """
        将论文数据导出为可读文本格式
        
        Args:
            papers: 论文信息列表
            filename: 保存文件名（可选）
            
        Returns:
            str: 格式化的文本字符串
        """
        lines = []
        lines.append("="*80)
        lines.append("Google Scholar 搜索结果")
        lines.append(f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"论文总数：{len(papers)}")
        lines.append("="*80)
        lines.append("")
        
        for i, paper in enumerate(papers, 1):
            lines.append(f"[{i}] {paper.title}")
            lines.append("-" * 60)
            
            if paper.authors:
                authors_str = ", ".join(paper.authors[:5])  # 最多显示5个作者
                if len(paper.authors) > 5:
                    authors_str += f" 等 ({len(paper.authors)} 人)"
                lines.append(f"作者：{authors_str}")
            
            if paper.year:
                lines.append(f"年份：{paper.year}")
            
            if paper.journal:
                lines.append(f"期刊/会议：{paper.journal}")
            
            if paper.citations > 0:
                lines.append(f"引用次数：{paper.citations}")
            
            if paper.abstract:
                abstract_preview = paper.abstract[:300] + "..." if len(paper.abstract) > 300 else paper.abstract
                lines.append(f"摘要：{abstract_preview}")
            
            if paper.url:
                lines.append(f"链接：{paper.url}")
            
            if paper.pdf_url:
                lines.append(f"PDF链接：{paper.pdf_url}")
            
            if paper.doi:
                lines.append(f"DOI：{paper.doi}")
            
            lines.append("")
        
        # 生成文本字符串
        text_str = "\n".join(lines)
        
        # 保存到文件（如果指定了文件名）
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text_str)
                logger.info(f"文本数据已保存到：{filename}")
            except Exception as e:
                logger.error(f"保存文本文件失败：{e}")
        
        return text_str

def main():
    """主函数，演示如何使用ScholarSearcher"""
    
    # 创建搜索器实例
    searcher = ScholarSearcher(delay=1.5)  # 1.5秒延迟，避免被封禁
    
    # 搜索参数
    search_config = {
        "keywords": "AI Agent",  # 修改这里的关键词
        "max_results": 5,  # 修改这里的搜索数量
        "year_low": 2024,  # 最早年份（可选）
        "year_high": 2025   # 最晚年份（可选）
    }
    
    print(f"开始搜索：{search_config['keywords']}")
    print(f"预期获取：{search_config['max_results']} 篇论文")
    print("-" * 50)
    
    # 执行搜索
    papers = searcher.search_papers(**search_config)
    
    if not papers:
        print("未找到符合条件的论文")
        return
    
    print(f"成功获取 {len(papers)} 篇论文")
    print("-" * 50)
    
    # 导出为JSON格式
    json_output = searcher.export_to_json(papers, "papers.json")
    print("JSON格式预览（前500字符）：")
    print(json_output[:500] + "..." if len(json_output) > 500 else json_output)
    print("-" * 50)
    
    # 导出为文本格式
    text_output = searcher.export_to_text(papers, "papers.txt")
    print("文本格式预览（前800字符）：")
    print(text_output[:800] + "..." if len(text_output) > 800 else text_output)
    
    print("\n导出完成！文件已保存为 papers.json 和 papers.txt")

if __name__ == "__main__":
    main()


