

import os
import shutil
import asyncio
import aiofiles
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from textwrap import dedent
import time
from functools import wraps
import fitz  # PyMuPDF
import aiohttp

from tools_agent.tavily_api import *
from tools_agent.json_tool import *
from tools_agent.llm_manager import *
from tools_agent.system_operations import SystemOperations as so

from utils.cninfo_advanced_crawler import CninfoAdvancedCrawler
from utils.duckduckgo import DuckDuckGoSearcher
from utils.agent_tool_stock_data import *
from utils.embedding_doubao import *
from utils.agent_tool_split_paras import *
from utils.agent_tool_vlm_img2txt_doubao import *
from utils.agent_tool_pdf2image import *

from prompts.fin_agent_prompts import FILE_LOCATE_PROMPT, FIND_LATEST_ANNUAL_REPORT_PROMPT

# 配置日志（支持日志轮转与上下文字段）
class _ContextFilter(logging.Filter):
    """为日志记录补充上下文字段，避免缺失字段导致格式化错误。
    字段包含：user_id、session_id。
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = getattr(record, 'user_id', os.environ.get('CURRENT_USER_ID', 'n/a'))
        record.session_id = getattr(record, 'session_id', os.environ.get('CURRENT_SESSION_ID', 'n/a'))
        return True


def setup_logging() -> None:
    """统一初始化日志，强制覆盖其他模块的默认配置，确保文件落盘并支持轮转。"""
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file_path = logs_dir / "data_prep.log"

    log_format = (
        "%(asctime)s - %(levelname)s - %(name)s - user=%(user_id)s - session=%(session_id)s - %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    console_handler = logging.StreamHandler()

    formatter = logging.Formatter(log_format)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    context_filter = _ContextFilter()
    file_handler.addFilter(context_filter)
    console_handler.addFilter(context_filter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler],
        force=True  # 覆盖可能已存在的全局日志配置
    )


setup_logging()
logger = logging.getLogger(__name__)

load_dotenv()

@dataclass
class Config:
    """配置类"""
    tavily_api_key: str = os.getenv("TAVILY_API_KEY")
    bocha_key: str = os.getenv("BOCHA_KEY")
    max_concurrent_downloads: int = 3  # 降低并发数
    max_concurrent_pdf_processing: int = 5  # 降低PDF处理并发数
    crawler_timeout: int = 300  # 爬虫超时时间
    max_retries: int = 3  # 最大重试次数
    retry_delay: int = 5  # 重试延迟
    chunk_size: int = 1000  # 分块大小
    embedding_batch_size: int = 4
    pdf_dpi: int = 150  # PDF转图像的DPI，适度提高识别稳定性

def retry_async(max_retries: int = 3, delay: int = 5):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"第{attempt + 1}次尝试失败: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"所有尝试失败，最后错误: {e}")
            raise last_exception
        return wrapper
    return decorator

def retry_sync(max_retries: int = 3, delay: int = 5):
    """同步重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"第{attempt + 1}次尝试失败: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        logger.error(f"所有尝试失败，最后错误: {e}")
            raise last_exception
        return wrapper
    return decorator

class PathManager:
    """路径管理器"""
    def __init__(self, user_id: str, stock_name: str):
        self.user_id = user_id
        self.stock_name = stock_name
        self.base_path = Path(f"files/{user_id}/{stock_name}")
        self.announcement_path = self.base_path / "announcements"
        self.vectors_path = self.base_path / "vectors"
        self.data_path = self.base_path / "data"
        
    def ensure_directories(self):
        """确保所有目录存在"""
        for path in [self.base_path, self.announcement_path, self.vectors_path, self.data_path]:
            path.mkdir(parents=True, exist_ok=True)
            
    def clean_filename(self, filename: str) -> str:
        """清理文件名"""
        return filename.replace(" ", "").lower()

class EnhancedCrawler:
    """增强的爬虫类，添加错误处理和超时机制"""
    
    def __init__(self, config: Config, download_dir: str):
        self.config = config
        self.download_dir = download_dir
        self.crawler = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        try:
            self.crawler = CninfoAdvancedCrawler(
                headless=True, 
                download_dir=self.download_dir
            )
            return self
        except Exception as e:
            logger.error(f"初始化爬虫失败: {e}")
            raise
            
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.crawler:
            try:
                # 清理资源
                await asyncio.get_event_loop().run_in_executor(
                    None, self.crawler.close
                ) if hasattr(self.crawler, 'close') else None
            except Exception as e:
                logger.warning(f"关闭爬虫时出错: {e}")
    
    @retry_async(max_retries=3, delay=10)
    async def search_with_timeout(self, keyword: str, max_results: int = 10) -> List:
        """带超时的搜索"""
        try:
            # 使用asyncio.wait_for添加超时
            return await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, 
                    self.crawler.search_announcements, 
                    keyword, 
                    max_results
                ),
                timeout=self.config.crawler_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"搜索超时: {keyword}")
            return []
        except Exception as e:
            logger.error(f"搜索失败: {keyword}, 错误: {e}")
            raise

    async def download_announcements(self, announcements: List, filter_keywords: List = None) -> Dict:
        """异步下载公告"""
        if not announcements:
            return {}
            
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None,
                self.crawler.batch_download_announcements,
                announcements,
                filter_keywords or []
            )
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return {}

class OptimizedDataProcessor:
    """优化的数据处理器"""
    
    def __init__(self, config: Config, path_manager: PathManager):
        self.config = config
        self.path_manager = path_manager
        
    @retry_sync()
    def find_latest_annual_report(self, selected_file_paths: List[str]) -> Optional[str]:
        """找到最新的年度报告"""
        if not selected_file_paths:
            return None
            
        try:
            prompt = FIND_LATEST_ANNUAL_REPORT_PROMPT.format(files=selected_file_paths)
            llm = LLMManager(model="doubao-seed-1-6-flash-250615")
            
            ans = ""
            for char in llm.generate_char_stream(prompt, temperature=0.0):
                ans += char
                
            file_path = get_json(ans)["file_path"]
            return file_path
        except Exception as e:
            logger.error(f"查找最新年报失败: {e}")
            return selected_file_paths[0] if selected_file_paths else None

    async def process_pdf_to_md_batch(self, pdf_files: List[str]) -> Dict[str, str]:
        """批量处理PDF转MD"""
        results = {}
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(self.config.max_concurrent_pdf_processing)
        
        async def process_single_pdf(pdf_path: str) -> Tuple[str, str]:
            async with semaphore:
                try:
                    pdf_name = Path(pdf_path).stem
                    image_folder_path = self.path_manager.announcement_path / f"{pdf_name}_images"
                    md_file_path = self.path_manager.announcement_path / f"{pdf_name}.md"
                    
                    # 如果MD文件已存在且非空，直接返回；若为空则触发重处理
                    if md_file_path.exists():
                        async with aiofiles.open(md_file_path, 'r', encoding='utf-8') as f:
                            existing = await f.read()
                        if existing and len(existing.strip()) >= 200:
                            logger.info(f"MD文件已存在且有效，跳过: {md_file_path}")
                            return pdf_path, existing
                        else:
                            logger.warning(f"MD文件为空或过短，重新处理: {md_file_path}")
                    
                    # 转换PDF到MD
                    md_content = await self.pdf_to_md_async(
                        pdf_path, 
                        str(image_folder_path), 
                        str(md_file_path)
                    )
                    
                    return pdf_path, md_content
                    
                except Exception as e:
                    logger.error(f"处理PDF失败 {pdf_path}: {e}")
                    return pdf_path, ""
        
        # 并发处理所有PDF文件
        tasks = [process_single_pdf(pdf) for pdf in pdf_files]
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed_tasks:
            if isinstance(result, Exception):
                logger.error(f"PDF处理异常: {result}")
            else:
                pdf_path, content = result
                results[pdf_path] = content
                
        return results

    async def pdf_to_md_async(self, pdf_path: str, image_folder_path: str, output_md_file_path: str) -> str:
        """异步PDF转MD"""
        try:
            # 确保图片文件夹存在
            Path(image_folder_path).mkdir(parents=True, exist_ok=True)
            
            # PDF转图片（在线程池中执行）
            stats = await asyncio.get_event_loop().run_in_executor(
                None,
                self.convert_pdf_to_images_sync,
                pdf_path,
                image_folder_path
            )
            # 若无图片成功生成，走文本抽取兜底
            try:
                generated_images = list(Path(image_folder_path).glob("*.jpg")) + list(Path(image_folder_path).glob("*.png"))
            except Exception:
                generated_images = []
            if not generated_images or (isinstance(stats, dict) and stats.get('successful_pages', 0) == 0):
                logger.warning(f"PDF转图片无结果，启用文本抽取兜底: {pdf_path}")
                text_fallback = self.extract_pdf_text_sync(pdf_path)
                async with aiofiles.open(output_md_file_path, 'w', encoding='utf-8') as f:
                    await f.write(text_fallback)
                # 清理临时图片文件夹（若存在）
                if Path(image_folder_path).exists():
                    await asyncio.get_event_loop().run_in_executor(None, shutil.rmtree, image_folder_path)
                return text_fallback
            
            # VLM处理
            md_content = await self.process_images_with_vlm(image_folder_path)
            
            # 若VLM产出为空或过短，启用文本抽取兜底
            if not md_content or len(md_content.strip()) < 200:
                logger.warning(f"VLM抽取内容为空或过短，启用文本抽取兜底: {pdf_path}")
                md_content = self.extract_pdf_text_sync(pdf_path)

            # 保存MD文件
            async with aiofiles.open(output_md_file_path, 'w', encoding='utf-8') as f:
                await f.write(md_content)
                
            # 清理临时图片文件夹
            await asyncio.get_event_loop().run_in_executor(
                None,
                shutil.rmtree,
                image_folder_path
            )
            
            return md_content
            
        except Exception as e:
            logger.error(f"PDF转MD失败: {e}")
            # 兜底：尝试直接文本抽取
            try:
                md_content = self.extract_pdf_text_sync(pdf_path)
                async with aiofiles.open(output_md_file_path, 'w', encoding='utf-8') as f:
                    await f.write(md_content)
                return md_content
            except Exception:
                return ""

    def convert_pdf_to_images_sync(self, pdf_path: str, image_folder_path: str):
        """同步PDF转图片，返回统计信息"""
        return convert_pdf_to_images(
            pdf_path,
            image_folder_path,
            dpi=self.config.pdf_dpi,
            format='jpg',
            max_workers=self.config.max_concurrent_pdf_processing
        )

    def extract_pdf_text_sync(self, pdf_path: str) -> str:
        """同步文本抽取兜底：优先用于图片/VLM失败或产出过短时"""
        text = ""
        try:
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
        except Exception as e:
            logger.error(f"文本抽取失败: {e}")
        return text

    async def process_images_with_vlm(self, image_folder_path: str) -> str:
        """使用VLM处理图片"""
        try:
            async with FastImageProcessor(
                max_concurrent_requests=self.config.max_concurrent_pdf_processing,
                max_retries=2
            ) as processor:
                
                results = await processor.process_images_batch(
                    image_folder_path=image_folder_path,
                    batch_size=50
                )
                
                processor.print_summary(results)
                await save_processing_report(results)
                
                # 收集所有MD内容
                md_content = ""
                image_path = Path(image_folder_path)
                md_files = sorted(image_path.glob("*.md"))
                for md_file in md_files:
                    async with aiofiles.open(md_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        md_content += content + "\n"
                        
                return md_content
                
        except Exception as e:
            logger.error(f"VLM处理失败: {e}")
            return ""

class OptimizedWorkflow:
    """优化的工作流"""
    
    def __init__(self, config: Config):
        self.config = config
        
    async def execute(self, user_id: str, stock_name: str, **kwargs) -> str:
        """执行数据准备工作流"""
        
        # 初始化路径管理器
        path_manager = PathManager(user_id, stock_name)
        path_manager.ensure_directories()
        
        data_processor = OptimizedDataProcessor(self.config, path_manager)
        
        try:
            # 1. 检查是否已有公告文件
            existing_files = list(path_manager.announcement_path.glob("*.pdf"))
            if not existing_files:
                logger.info("开始获取公告内容...")
                pdf_files = await self.get_announcements_optimized(
                    stock_name, path_manager, **kwargs
                )
            else:
                logger.info("发现已有公告文件，跳过下载")
                pdf_files = [str(f) for f in existing_files]
            
            # 2. 批量处理PDF转MD
            if pdf_files:
                logger.info(f"开始处理{len(pdf_files)}个PDF文件...")
                md_results = await data_processor.process_pdf_to_md_batch(pdf_files)
                latest_content = list(md_results.values())[0][:10000] if md_results else ""
            else:
                latest_content = ""
                
            # 3. 并行执行其他搜索任务
            search_tasks = [
                self.search_bocha(stock_name),
                self.prepare_financial_data(stock_name, str(path_manager.data_path))
            ]
            
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            bocha_results = search_results[0] if not isinstance(search_results[0], Exception) else ""
            data_preview = search_results[1] if not isinstance(search_results[1], Exception) else ""
            
            # 4. 组合结果
            total_preview = self.combine_results(latest_content, bocha_results, data_preview)
            
            # 5. 保存结果
            preview_file = path_manager.base_path / "total_preview.md"
            async with aiofiles.open(preview_file, 'w', encoding='utf-8') as f:
                await f.write(total_preview)
                
            # 6. 异步向量化
            asyncio.create_task(self.vectorize_files_async(path_manager))
            
            logger.info("数据准备工作流完成")
            return total_preview
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            raise

    async def get_announcements_optimized(self, stock_name: str, path_manager: PathManager, **kwargs) -> List[str]:
        """优化的公告获取"""
        
        years = ["2024", "2023", "2022", "2021", "2020"]
        keywords = [f"{stock_name} 年度报告"] + \
                   [f"{stock_name} {y} 年度报告" for y in years] + \
                   [f"{stock_name} {y} 年报" for y in years] + \
                   [f"{stock_name} {y} 年年度报告" for y in years] + \
                   [f"{stock_name} 招股说明书"]
        
        downloaded_files = []
        
        # 使用信号量控制并发搜索
        semaphore = asyncio.Semaphore(2)  # 限制同时只有2个搜索任务
        
        async def search_single_keyword(keyword: str) -> List[str]:
            async with semaphore:
                try:
                    logger.info(f"搜索关键词: {keyword}")
                    
                    async with EnhancedCrawler(self.config, str(path_manager.base_path)) as crawler:
                        announcements = await crawler.search_with_timeout(keyword, 50)
                        
                        if announcements:
                            # 按年份过滤（若关键词包含年份，或者限定在目标年份集合内）
                            target_years = {"2020", "2021", "2022", "2023", "2024"}
                            year_in_kw = None
                            for y in target_years:
                                if y in keyword:
                                    year_in_kw = y
                                    break

                            if year_in_kw:
                                announcements = [a for a in announcements if (a.announcement_time or "").startswith(year_in_kw)]
                            else:
                                announcements = [a for a in announcements if (a.announcement_time or "")[:4] in target_years]

                            # 下载前按关键词过滤，减少无关项
                            download_results = await crawler.download_announcements(
                                announcements,
                                filter_keywords=["年度报告", "年年度报告", "年报", "招股说明书"]
                            )
                            successful_files = [path for path in download_results.values() if path]
                            logger.info(f"关键词 '{keyword}' 下载成功 {len(successful_files)} 个文件")
                            return successful_files
                        else:
                            logger.warning(f"关键词 '{keyword}' 未找到相关公告")
                            return []
                            
                except Exception as e:
                    logger.error(f"搜索关键词 '{keyword}' 失败: {e}")
                    return []
        
        # 并发搜索所有关键词
        search_tasks = [search_single_keyword(keyword) for keyword in keywords]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # 收集所有成功下载的文件
        for result in search_results:
            if isinstance(result, list):
                downloaded_files.extend(result)
        
        # 筛选年报和招股说明书
        filtered_files = self.filter_annual_reports(downloaded_files)

        # 保障2020-2024覆盖：根据文件名提取年份，缺失则针对缺失年份再搜索
        have_years = set()
        year_pattern = re.compile(r"20(20|21|22|23|24)")
        for fp in filtered_files:
            m = year_pattern.search(Path(fp).name)
            if m:
                have_years.add(m.group(0))
        missing_years = [y for y in years if y not in have_years]

        if missing_years:
            logger.warning(f"缺失年份 {missing_years}，尝试定向补充搜索")

            async def search_missing(year: str) -> List[str]:
                try:
                    kw_variants = [
                        f"{stock_name} {year} 年度报告",
                        f"{stock_name} {year} 年报",
                        f"{stock_name} {year} 年年度报告",
                    ]
                    aggregate: List[str] = []
                    for kw in kw_variants:
                        async with EnhancedCrawler(self.config, str(path_manager.base_path)) as crawler:
                            anns = await crawler.search_with_timeout(kw, 10)
                            if anns:
                                dl = await crawler.download_announcements(anns)
                                aggregate.extend([p for p in dl.values() if p])
                    return aggregate
                except Exception as e:
                    logger.error(f"定向搜索年份 {year} 失败: {e}")
                    return []

            more_tasks = [search_missing(y) for y in missing_years]
            more_results = await asyncio.gather(*more_tasks, return_exceptions=True)
            for r in more_results:
                if isinstance(r, list):
                    filtered_files.extend(self.filter_annual_reports(r))

        # 去重
        filtered_files = list(dict.fromkeys(filtered_files))

        # 复制到公告文件夹并返回目标路径
        dest_paths: List[str] = []
        for file_path in filtered_files:
            try:
                dest_path = path_manager.announcement_path / Path(file_path).name
                if str(Path(file_path).resolve()) != str(dest_path.resolve()):
                    shutil.copy2(file_path, dest_path)
                dest_paths.append(str(dest_path))
            except Exception as e:
                logger.warning(f"复制文件失败 {file_path}: {e}")
        
        return dest_paths

    def filter_annual_reports(self, file_paths: List[str]) -> List[str]:
        """筛选年报和招股说明书（排除摘要/英文/修订/更正等）"""
        filtered = []
        for file_path in file_paths:
            filename = Path(file_path).name
            lower = filename.lower()
            if any(k in filename for k in ["年度报告", "年年度报告", "招股说明书", "年报"]):
                if not any(bad in lower for bad in ["半年", "半年度", "摘要", "英文", "修订", "更正", "取消", "取消审核", "问询回复", "回复", "公告格式"]):
                    filtered.append(file_path)
        return filtered

    async def search_bocha(self, stock_name: str) -> str:
        """博查搜索"""
        try:
            keyword = f"{stock_name} 主营业务"
            
            url = "https://api.bochaai.com/v1/web-search"
            payload = {
                "query": keyword,
                "summary": True,
                "count": 10
            }
            
            headers = {
                'Authorization': f'Bearer {self.config.bocha_key}',
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        search_results = data.get("data", {}).get("webPages", {}).get("value", [])
                        
                        content = ""
                        for result in search_results:
                            content += f"{result.get('name', '')}\n{result.get('url', '')}\n{result.get('snippet', '')}\n---\n"
                        
                        return content[:10000]
                    else:
                        logger.warning(f"博查搜索失败，状态码: {response.status}")
                        return ""
                        
        except Exception as e:
            logger.error(f"博查搜索异常: {e}")
            return ""

    async def prepare_financial_data(self, stock_name: str, data_path: str) -> str:
        """准备财务数据"""
        try:
            # 异步执行财务数据准备
            def sync_prepare_data():
                indicator = "按年度"
                return prepare_data(stock_name, indicator, start_year="2020", folder_path=data_path)
            
            fin_debt_df, financial_abstract, financial_analysis_indicator = await asyncio.get_event_loop().run_in_executor(
                None, sync_prepare_data
            )
            
            preview_fin_debt = preview_dataframe_as_blocks(fin_debt_df)
            preview_financial_abstract = preview_dataframe_as_blocks(financial_abstract)
            preview_financial_indicator = preview_dataframe_as_blocks(financial_analysis_indicator)
            
            return f"""
# 资产负债表
{preview_fin_debt}
# 利润表摘要  
{preview_financial_abstract}
# 财务指标分析
{preview_financial_indicator}
"""
        except Exception as e:
            logger.error(f"财务数据准备失败: {e}")
            return ""

    def combine_results(self, latest_content: str, bocha_results: str, data_preview: str) -> str:
        """组合所有结果"""
        return f"""
# 股票数据预览
{data_preview}

# 最新财报部分信息
{latest_content}

# 互联网搜索信息
{bocha_results}
"""

    async def vectorize_files_async(self, path_manager: PathManager):
        """异步向量化文件"""
        try:
            logger.info("开始异步向量化...")
            
            # 在后台线程中执行向量化
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.batch_vectorize_sync,
                str(path_manager.announcement_path),
                str(path_manager.vectors_path)
            )
            
            logger.info("向量化完成")
            
        except Exception as e:
            logger.error(f"向量化失败: {e}")

    def batch_vectorize_sync(self, announcement_path: str, vectors_path: str):
        """同步批量向量化"""
        md_files = list(Path(announcement_path).glob("*.md"))
        
        for md_file in md_files:
            try:
                pkl_file_path = vectors_path + "/" + md_file.stem + "_vectors.pkl"
                
                if os.path.exists(pkl_file_path):
                    logger.info(f"向量文件已存在，跳过: {pkl_file_path}")
                    continue
                
                # 分段处理
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 跳过空文件或过短内容
                if not content or len(content.strip()) < 50:
                    logger.warning(f"MD文件为空或内容过短，跳过向量化: {md_file}")
                    continue
                
                paragraphs = smart_paragraph_split_v2(content, target_length=self.config.chunk_size)
                if not paragraphs:
                    logger.warning(f"分段结果为空，跳过向量化: {md_file}")
                    continue
                
                # 添加文件路径前缀
                final_paras = [f"{md_file}\n{para}" for para in paragraphs]
                
                # 向量化
                db = VectorDatabase(save_path=pkl_file_path)
                db.batch_vectorize(
                    texts=final_paras,
                    max_workers=8,
                    model="doubao-embedding-vision-250328",
                    model_type="doubao",
                    bge_batch_size=self.config.embedding_batch_size
                )
                db.save_to_file()
                
                logger.info(f"向量化完成: {md_file.name}")
                
            except Exception as e:
                logger.error(f"向量化失败 {md_file}: {e}")


# 主执行函数
async def main():
    """主函数"""
    try:
        # 配置参数
        config = Config()
        
        # 用户参数
        user_id = "sam"
        stock_name = "中石科技"
        
        # 创建工作流
        workflow = OptimizedWorkflow(config)
        
        # 执行工作流
        result = await workflow.execute(
            user_id=user_id,
            stock_name=stock_name,
            count=20
        )
        
        logger.info(f"工作流执行完成，结果长度: {len(result)}")
        print(f"预览内容总长度: {len(result)} 字符")

        # 向量化所有markdown文件
        path_manager = PathManager(user_id, stock_name)
        await workflow.vectorize_files_async(path_manager)
        
    except Exception as e:
        logger.error(f"主函数执行失败: {e}")
        raise

if __name__ == "__main__":
    # 需要添加缺失的导入
    import aiohttp
    start_time = time.time()
    # 运行主函数
    asyncio.run(main())
    end_time = time.time()
    total_time = float(f"{end_time - start_time:.2f}")
    print(f"总耗时: {total_time/60:.2f} 分钟")

