import os
import base64
import mimetypes
import asyncio
import aiohttp
import aiofiles
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from textwrap import dedent
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
from volcenginesdkarkruntime import Ark
from dotenv import load_dotenv

load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('image_processing.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DOUBAO_VLM_PROMPT = dedent("""
    请阅读我上传的pdf文件，使用markdown格式返回所有的信息。
    如果有图片，需要你用一个markdown标题+文字描述，标题为图片的标题，文字描述需要详细全面地介绍这张图片的内容。

    # 注意：
    - 你的输出必须与原文的语种一致。如果我提供的图片是英文，你的输出必须是英文；如果我提供的图片是中文，你的输出必须是中文。即：你的输出语种要与我的图片语种一致，不需要做翻译。

    开始输出：
""").strip()

@dataclass
class ProcessingResult:
    image_path: str
    success: bool
    content: str = ""
    error: str = ""
    processing_time: float = 0.0

class FastImageProcessor:
    def __init__(self, max_concurrent_requests: int = 20, max_retries: int = 3):
        """
        初始化快速图片处理器
        
        Args:
            max_concurrent_requests: 最大并发请求数
            max_retries: 最大重试次数
        """
        self.max_concurrent_requests = max_concurrent_requests
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_count = 0
        self.total_count = 0
        self.start_time = 0
        
    async def __aenter__(self):
        # 创建持久的HTTP会话，配置连接池
        connector = aiohttp.TCPConnector(
            limit=50,  # 总连接池大小
            limit_per_host=25,  # 每个主机的连接数
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector, 
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def get_image_base64(self, image_path: str) -> str:
        """同步获取图片的base64编码"""
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
            
            mime_type, _ = mimetypes.guess_type(image_path)
            if mime_type is None:
                mime_type = "application/octet-stream"
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            return f"data:{mime_type};base64,{image_base64}"
        except Exception as e:
            logger.error(f"读取图片失败 {image_path}: {e}")
            raise

    async def process_single_image_async(self, image_path: str, output_path: str) -> ProcessingResult:
        """异步处理单个图片"""
        start_time = time.time()
        
        async with self.semaphore:  # 限制并发数
            try:
                # 在线程池中执行I/O密集型操作
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=4) as executor:
                    image_base64 = await loop.run_in_executor(
                        executor, self.get_image_base64, image_path
                    )
                
                # 异步调用API
                content = await self.call_doubao_api_async(image_base64, image_path)
                
                # 异步写入文件
                async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
                    await f.write(content)
                
                processing_time = time.time() - start_time
                self.processed_count += 1
                
                # 计算进度和预估时间
                progress = (self.processed_count / self.total_count) * 100
                elapsed = time.time() - self.start_time
                avg_time_per_image = elapsed / self.processed_count
                remaining_images = self.total_count - self.processed_count
                eta = remaining_images * avg_time_per_image
                
                logger.info(
                    f"✅ 完成 [{self.processed_count}/{self.total_count}] "
                    f"({progress:.1f}%) {Path(image_path).name} "
                    f"耗时: {processing_time:.2f}s, "
                    f"预计剩余: {eta:.1f}s, "
                    f"平均速度: {avg_time_per_image:.2f}s/图"
                )
                
                return ProcessingResult(
                    image_path=image_path,
                    success=True,
                    content=content,
                    processing_time=processing_time
                )
                
            except Exception as e:
                processing_time = time.time() - start_time
                error_msg = f"处理图片失败: {e}"
                logger.error(f"❌ {Path(image_path).name}: {error_msg}")
                
                return ProcessingResult(
                    image_path=image_path,
                    success=False,
                    error=error_msg,
                    processing_time=processing_time
                )

    async def call_doubao_api_async(self, image_base64: str, image_path: str) -> str:
        """异步调用豆包API"""
        conversations = [
            {"role": "system", "content": "你必须精准提取PDF图片的内容。"}, 
            {"role": "user", "content": [
                {"type": "text", "text": DOUBAO_VLM_PROMPT},
                {"type": "image_url", "image_url": {"url": image_base64}}
            ]}
        ]
        
        for attempt in range(self.max_retries):
            try:
                # 使用同步的volcengine SDK，但在线程池中运行
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=2) as executor:
                    content = await loop.run_in_executor(
                        executor, self._sync_call_doubao, conversations
                    )
                return content
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(f"⚠️  {Path(image_path).name} API调用失败 (尝试 {attempt + 1}/{self.max_retries}): {e}, {wait_time}s后重试")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ {Path(image_path).name} API调用最终失败: {e}")
                    raise

    def _sync_call_doubao(self, conversations) -> str:
        """同步调用豆包API"""
        client = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=os.environ.get("DOUBAO_API_KEY"),
        )
        
        response = client.chat.completions.create(
            model="doubao-seed-1-6-flash-250615",
            messages=conversations,
            temperature=1,
            top_p=0.7,
            max_tokens=16384,
            thinking={"type": "disabled"},
            stream=True
        )
        
        content = ""
        for chunk in response:
            reasoning_content = chunk.choices[0].delta.reasoning_content
            delta_content = chunk.choices[0].delta.content
            if reasoning_content:
                content += reasoning_content
            if delta_content:
                content += delta_content
        
        return content

    async def process_images_batch(self, image_folder_path: str, batch_size: int = 50) -> List[ProcessingResult]:
        """批量处理图片文件夹"""
        
        # 获取所有图片文件（修复重复计数问题）
        image_paths = []
        folder_path = Path(image_folder_path)
        
        # 支持的图片扩展名
        supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        
        # 遍历文件夹中的所有文件
        for file_path in folder_path.iterdir():
            if file_path.is_file():
                # 将扩展名转为小写进行比较，避免重复
                file_ext = file_path.suffix.lower()
                if file_ext in supported_extensions:
                    image_paths.append(file_path)
        
        # 去重（以防万一）并排序
        image_paths = list(set(image_paths))
        image_paths.sort()
        
        self.total_count = len(image_paths)
        self.start_time = time.time()
        
        logger.info(f"📁 文件夹扫描完成: 发现 {self.total_count} 张图片")
        
        # 打印文件扩展名统计
        ext_count = {}
        for path in image_paths:
            ext = path.suffix.lower()
            ext_count[ext] = ext_count.get(ext, 0) + 1
        
        logger.info(f"📊 文件类型分布: {dict(ext_count)}")
        
        if self.total_count == 0:
            logger.warning(f"❌ 文件夹 {image_folder_path} 中没有找到图片文件")
            return []
        
        logger.info(f"🚀 开始处理 {self.total_count} 张图片，目标: 1分钟内完成")
        logger.info(f"⚙️  配置: 最大并发数={self.max_concurrent_requests}, 批次大小={batch_size}")
        
        # 准备任务列表
        tasks = []
        for image_path in image_paths:
            output_path = image_path.with_suffix('.md')
            task = self.process_single_image_async(str(image_path), str(output_path))
            tasks.append(task)
        
        # 分批处理以避免内存过载
        all_results = []
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(tasks) + batch_size - 1) // batch_size
            
            logger.info(f"📦 处理批次 {batch_num}/{total_batches} (包含 {len(batch_tasks)} 个任务)")
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # 处理异常结果
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    image_path = str(image_paths[i + j])
                    logger.error(f"❌ 批次处理异常 {Path(image_path).name}: {result}")
                    all_results.append(ProcessingResult(
                        image_path=image_path,
                        success=False,
                        error=str(result)
                    ))
                else:
                    all_results.append(result)
        
        return all_results

    def print_summary(self, results: List[ProcessingResult]):
        """打印处理摘要"""
        total_time = time.time() - self.start_time
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        avg_processing_time = sum(r.processing_time for r in results if r.success) / max(successful, 1)
        images_per_minute = (successful / total_time) * 60 if total_time > 0 else 0
        
        logger.info("=" * 60)
        logger.info("📊 处理完成统计:")
        logger.info(f"   总图片数: {len(results)}")
        logger.info(f"   成功处理: {successful}")
        logger.info(f"   处理失败: {failed}")
        logger.info(f"   总耗时: {total_time:.2f}秒")
        logger.info(f"   平均每张: {avg_processing_time:.2f}秒")
        logger.info(f"   处理速度: {images_per_minute:.1f}张/分钟")
        logger.info(f"   目标达成: {'✅ 是' if images_per_minute >= 400 else '❌ 否'}")
        logger.info("=" * 60)
        
        if failed > 0:
            logger.info("❌ 失败的文件:")
            for result in results:
                if not result.success:
                    logger.error(f"   {Path(result.image_path).name}: {result.error}")

async def main():
    """主函数"""
    # 配置参数
    image_folder_path = "files/aier"
    max_concurrent_requests = 30  # 根据API限制调整
    batch_size = 100  # 批次大小
    
    # 检查文件夹是否存在
    if not os.path.exists(image_folder_path):
        logger.error(f"❌ 文件夹不存在: {image_folder_path}")
        return
    
    # 使用异步上下文管理器
    async with FastImageProcessor(
        max_concurrent_requests=max_concurrent_requests,
        max_retries=3
    ) as processor:
        
        # 批量处理图片
        results = await processor.process_images_batch(
            image_folder_path=image_folder_path,
            batch_size=batch_size
        )
        
        # 打印摘要
        processor.print_summary(results)
        
        # 保存详细报告
        await save_processing_report(results)

async def save_processing_report(results: List[ProcessingResult]):
    """保存处理报告"""
    report_path = "processing_report.md"
    
    report_content = "# 图片处理报告\n\n"
    report_content += f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    successful_results = [r for r in results if r.success]
    failed_results = [r for r in results if not r.success]
    
    report_content += f"## 统计信息\n"
    report_content += f"- 总数: {len(results)}\n"
    report_content += f"- 成功: {len(successful_results)}\n"
    report_content += f"- 失败: {len(failed_results)}\n\n"
    
    if successful_results:
        report_content += "## 成功处理的文件\n"
        for result in successful_results:
            report_content += f"- {Path(result.image_path).name} ({result.processing_time:.2f}s)\n"
        report_content += "\n"
    
    if failed_results:
        report_content += "## 处理失败的文件\n"
        for result in failed_results:
            report_content += f"- {Path(result.image_path).name}: {result.error}\n"
        report_content += "\n"
    
    async with aiofiles.open(report_path, "w", encoding="utf-8") as f:
        await f.write(report_content)
    
    logger.info(f"📄 详细报告已保存至: {report_path}")

# 同步版本的快速处理器（如果不想使用异步）
class SyncFastImageProcessor:
    def __init__(self, max_workers: int = 20):
        self.max_workers = max_workers
        self.processed_count = 0
        self.total_count = 0
        self.start_time = 0
    
    def get_image_base64(self, image_path: str) -> str:
        """获取图片的base64编码"""
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None:
            mime_type = "application/octet-stream"
        
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{image_base64}"

    def call_doubao_api(self, image_base64: str) -> str:
        """调用豆包API"""
        conversations = [
            {"role": "system", "content": "你必须精准提取PDF图片的内容。"}, 
            {"role": "user", "content": [
                {"type": "text", "text": DOUBAO_VLM_PROMPT},
                {"type": "image_url", "image_url": {"url": image_base64}}
            ]}
        ]
        
        client = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=os.environ.get("DOUBAO_API_KEY"),
        )
        
        response = client.chat.completions.create(
            model="doubao-seed-1-6-flash-250615",
            messages=conversations,
            temperature=1,
            top_p=0.7,
            max_tokens=16384,
            thinking={"type": "disabled"},
            stream=True
        )
        
        content = ""
        for chunk in response:
            reasoning_content = chunk.choices[0].delta.reasoning_content
            delta_content = chunk.choices[0].delta.content
            if reasoning_content:
                content += reasoning_content
            if delta_content:
                content += delta_content
        
        return content

    def process_single_image(self, image_path: str, output_path: str) -> ProcessingResult:
        """处理单个图片"""
        start_time = time.time()
        
        try:
            image_base64 = self.get_image_base64(image_path)
            content = self.call_doubao_api(image_base64)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            processing_time = time.time() - start_time
            self.processed_count += 1
            
            # 计算进度
            progress = (self.processed_count / self.total_count) * 100
            elapsed = time.time() - self.start_time
            avg_time = elapsed / self.processed_count
            eta = (self.total_count - self.processed_count) * avg_time
            
            logger.info(
                f"✅ 完成 [{self.processed_count}/{self.total_count}] "
                f"({progress:.1f}%) {Path(image_path).name} "
                f"耗时: {processing_time:.2f}s, ETA: {eta:.1f}s"
            )
            
            return ProcessingResult(
                image_path=image_path,
                success=True,
                content=content,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"❌ {Path(image_path).name}: {error_msg}")
            
            return ProcessingResult(
                image_path=image_path,
                success=False,
                error=error_msg,
                processing_time=processing_time
            )

    def process_images_concurrent(self, image_folder_path: str) -> List[ProcessingResult]:
        """使用线程池并发处理图片"""
        
        # 获取所有图片文件（修复重复计数问题）
        image_paths = []
        folder_path = Path(image_folder_path)
        
        # 支持的图片扩展名
        supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        
        # 遍历文件夹中的所有文件
        for file_path in folder_path.iterdir():
            if file_path.is_file():
                # 将扩展名转为小写进行比较，避免重复
                file_ext = file_path.suffix.lower()
                if file_ext in supported_extensions:
                    image_paths.append(file_path)
        
        # 去重（以防万一）并排序
        image_paths = list(set(image_paths))
        image_paths.sort()
        
        self.total_count = len(image_paths)
        self.start_time = time.time()
        
        logger.info(f"📁 文件夹扫描完成: 发现 {self.total_count} 张图片")
        
        # 打印文件扩展名统计
        ext_count = {}
        for path in image_paths:
            ext = path.suffix.lower()
            ext_count[ext] = ext_count.get(ext, 0) + 1
        
        logger.info(f"📊 文件类型分布: {dict(ext_count)}")
        
        if self.total_count == 0:
            logger.warning(f"❌ 文件夹 {image_folder_path} 中没有找到图片文件")
            return []
        
        logger.info(f"🚀 开始并发处理 {self.total_count} 张图片")
        logger.info(f"⚙️  配置: 最大并发数={self.max_workers}")
        
        # 准备任务参数
        task_args = []
        for image_path in image_paths:
            output_path = image_path.with_suffix('.md')
            task_args.append((str(image_path), str(output_path)))
        
        # 使用线程池并发执行
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(
                lambda args: self.process_single_image(*args), 
                task_args
            ))
        
        return results

def run_sync_version():
    """运行同步版本"""
    image_folder_path = "files/aier"
    
    processor = SyncFastImageProcessor(max_workers=20)
    results = processor.process_images_concurrent(image_folder_path)
    
    # 打印统计信息
    total_time = time.time() - processor.start_time
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    images_per_minute = (successful / total_time) * 60 if total_time > 0 else 0
    
    logger.info("=" * 60)
    logger.info("📊 处理完成统计:")
    logger.info(f"   成功: {successful}, 失败: {failed}")
    logger.info(f"   总耗时: {total_time:.2f}秒")
    logger.info(f"   处理速度: {images_per_minute:.1f}张/分钟")
    logger.info(f"   目标达成: {'✅ 是' if images_per_minute >= 400 else '❌ 否'}")
    logger.info("=" * 60)

# ============= Jupyter 环境适配代码 =============

def is_jupyter_environment():
    """检测是否在Jupyter环境中运行"""
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except ImportError:
        return False

def setup_jupyter_asyncio():
    """为Jupyter环境配置asyncio"""
    try:
        import nest_asyncio
        nest_asyncio.apply()
        logger.info("✅ Jupyter asyncio环境配置完成")
    except ImportError:
        logger.warning("⚠️  需要安装 nest_asyncio: pip install nest_asyncio")
        raise ImportError("请运行: pip install nest_asyncio")

async def run_in_jupyter(image_folder_path: str = "files/aier", 
                        max_concurrent: int = 30, 
                        batch_size: int = 100):
    """
    在Jupyter中运行的主函数
    
    Args:
        image_folder_path: 图片文件夹路径
        max_concurrent: 最大并发数
        batch_size: 批次大小
    """
    logger.info("🔧 Jupyter环境启动中...")
    
    # 检查文件夹是否存在
    if not os.path.exists(image_folder_path):
        logger.error(f"❌ 文件夹不存在: {image_folder_path}")
        return None
    
    # 使用异步上下文管理器
    async with FastImageProcessor(
        max_concurrent_requests=max_concurrent,
        max_retries=3
    ) as processor:
        
        # 批量处理图片
        results = await processor.process_images_batch(
            image_folder_path=image_folder_path,
            batch_size=batch_size
        )
        
        # 打印摘要
        processor.print_summary(results)
        
        # 保存详细报告
        await save_processing_report(results)
        
        return results

# ============= 不同环境的运行方式 =============

if __name__ == "__main__":
    if is_jupyter_environment():
        print("⚠️  检测到Jupyter环境，请使用以下代码运行：")
        print("""
# 1. 首先运行这个cell安装依赖：
!pip install nest_asyncio aiohttp aiofiles

# 2. 然后在新的cell中运行：
setup_jupyter_asyncio()

# 3. 最后运行处理任务：
results = await run_in_jupyter(
    image_folder_path="files/aier",  # 修改为你的图片文件夹路径
    max_concurrent=30,               # 并发数，根据API限制调整
    batch_size=100                   # 批次大小
)
        """)
    else:
        # 普通Python环境运行
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("⏹️  用户中断处理")
        except Exception as e:
            logger.error(f"❌ 程序异常: {e}")

# ============= Jupyter简化运行函数 =============

def quick_start_jupyter(folder_path: str = "files/aier"):
    """
    Jupyter环境一键启动函数
    
    Usage in Jupyter:
        quick_start_jupyter("your_image_folder_path")
    """
    if not is_jupyter_environment():
        logger.error("❌ 此函数仅适用于Jupyter环境")
        return
    
    try:
        setup_jupyter_asyncio()
        
        # 创建并运行任务
        import asyncio
        loop = asyncio.get_event_loop()
        
        async def _run():
            return await run_in_jupyter(folder_path)
        
        return loop.create_task(_run())
        
    except Exception as e:
        logger.error(f"❌ Jupyter启动失败: {e}")
        return None

# ============= 原版本运行方式保留 =============

def run_sync_version_main():
    """运行同步版本的主函数"""
    image_folder_path = "files/aier"
    
    processor = SyncFastImageProcessor(max_workers=20)
    results = processor.process_images_concurrent(image_folder_path)
    
    # 打印统计信息
    total_time = time.time() - processor.start_time
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    images_per_minute = (successful / total_time) * 60 if total_time > 0 else 0
    
    logger.info("=" * 60)
    logger.info("📊 处理完成统计:")
    logger.info(f"   成功: {successful}, 失败: {failed}")
    logger.info(f"   总耗时: {total_time:.2f}秒")
    logger.info(f"   处理速度: {images_per_minute:.1f}张/分钟")
    logger.info(f"   目标达成: {'✅ 是' if images_per_minute >= 400 else '❌ 否'}")
    logger.info("=" * 60)

