# type: ignore

import os
import sys
import asyncio
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Tuple, Union
from pdf2image import convert_from_path
from PIL import Image
import multiprocessing as mp
from functools import partial
import time

class AsyncPDFToImageConverter:
    def __init__(self, max_workers: Optional[int] = None, dpi: int = 200):
        """
        初始化PDF转图片转换器
        
        Args:
            max_workers: 最大工作进程数，None表示自动设置
            dpi: 图片分辨率
        """
        self.dpi = dpi
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        self.is_jupyter = self._is_jupyter_environment()
        
    def _is_jupyter_environment(self) -> bool:
        """检测是否在Jupyter环境中运行"""
        try:
            from IPython import get_ipython
            return get_ipython() is not None
        except ImportError:
            return False
    
    def _convert_page_range(self, pdf_path: str, start_page: int, end_page: int, 
                           output_dir: str, file_prefix: str) -> List[str]:
        """
        转换指定页码范围的PDF页面
        
        Args:
            pdf_path: PDF文件路径
            start_page: 起始页码（1-based）
            end_page: 结束页码（1-based）
            output_dir: 输出目录
            file_prefix: 文件名前缀
            
        Returns:
            转换后的图片文件路径列表
        """
        try:
            # 转换指定页码范围
            images = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                first_page=start_page,
                last_page=end_page,
                fmt='PNG'
            )
            
            saved_files = []
            for i, image in enumerate(images):
                page_num = start_page + i
                output_path = os.path.join(output_dir, f"{file_prefix}_page_{page_num:04d}.png")
                image.save(output_path, 'PNG')
                saved_files.append(output_path)
                
            return saved_files
            
        except Exception as e:
            print(f"Error converting pages {start_page}-{end_page}: {str(e)}")
            return []
    
    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """获取PDF总页数"""
        try:
            # 只转换第一页来获取总页数信息
            from pdf2image.exceptions import PDFPageCountError
            import fitz  # PyMuPDF，更快地获取页数
            
            try:
                doc = fitz.open(pdf_path)
                page_count = doc.page_count
                doc.close()
                return page_count
            except:
                # 如果PyMuPDF不可用，使用pdf2image的方法
                test_images = convert_from_path(pdf_path, dpi=72, last_page=1)
                # 这里需要用其他方法获取总页数
                # 可以通过二分查找或者使用poppler工具
                return self._get_page_count_fallback(pdf_path)
                
        except Exception as e:
            print(f"Error getting page count: {str(e)}")
            return 0
    
    def _get_page_count_fallback(self, pdf_path: str) -> int:
        """备用方法获取PDF页数"""
        try:
            import subprocess
            result = subprocess.run(['pdfinfo', pdf_path], 
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if line.startswith('Pages:'):
                    return int(line.split(':')[1].strip())
            return 0
        except:
            # 最后的备用方法：尝试转换大页数并捕获异常
            try:
                convert_from_path(pdf_path, dpi=72, last_page=9999)
                return 9999  # 如果没有异常，说明页数很多
            except:
                # 二分查找确定页数
                return self._binary_search_page_count(pdf_path)
    
    def _binary_search_page_count(self, pdf_path: str) -> int:
        """使用二分查找确定PDF页数"""
        left, right = 1, 1000
        while left < right:
            mid = (left + right + 1) // 2
            try:
                convert_from_path(pdf_path, dpi=72, first_page=mid, last_page=mid)
                left = mid
            except:
                right = mid - 1
        return left
    
    async def convert_pdf_to_images_async(self, pdf_path: str, output_dir: str, 
                                        pages_per_batch: int = 10,
                                        file_prefix: Optional[str] = None) -> List[str]:
        """
        异步转换PDF到图片
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            pages_per_batch: 每个批次处理的页数
            file_prefix: 输出文件名前缀
            
        Returns:
            转换后的图片文件路径列表
        """
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取PDF总页数
        print("正在获取PDF页数...")
        total_pages = self._get_pdf_page_count(pdf_path)
        if total_pages == 0:
            raise ValueError("无法获取PDF页数或PDF文件无效")
        
        print(f"PDF总共有 {total_pages} 页")
        
        # 设置文件前缀
        if file_prefix is None:
            file_prefix = Path(pdf_path).stem
        
        # 创建页面批次
        batches = []
        for start in range(1, total_pages + 1, pages_per_batch):
            end = min(start + pages_per_batch - 1, total_pages)
            batches.append((start, end))
        
        print(f"将分 {len(batches)} 个批次处理，每批次 {pages_per_batch} 页")
        
        all_results = []
        
        # 检测操作系统，在Windows上使用线程池
        import platform
        is_windows = platform.system() == "Windows"
        
        if self.is_jupyter or is_windows:
            # Jupyter环境或Windows中使用线程池（避免多进程问题）
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                tasks = []
                for start_page, end_page in batches:
                    task = loop.run_in_executor(
                        executor,
                        self._convert_page_range,
                        pdf_path, start_page, end_page, output_dir, file_prefix
                    )
                    tasks.append(task)
                
                # 执行所有任务并显示进度
                for i, task in enumerate(asyncio.as_completed(tasks)):
                    result = await task
                    all_results.extend(result)
                    print(f"完成批次 {i+1}/{len(batches)}")
        else:
            # 非Jupyter环境使用进程池
            loop = asyncio.get_event_loop()
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                tasks = []
                for start_page, end_page in batches:
                    task = loop.run_in_executor(
                        executor,
                        self._convert_page_range,
                        pdf_path, start_page, end_page, output_dir, file_prefix
                    )
                    tasks.append(task)
                
                # 执行所有任务并显示进度
                for i, task in enumerate(asyncio.as_completed(tasks)):
                    result = await task
                    all_results.extend(result)
                    print(f"完成批次 {i+1}/{len(batches)}")
        
        # 按页码排序结果
        all_results.sort(key=lambda x: int(x.split('_page_')[1].split('.')[0]))
        return all_results
    
    def convert_pdf_to_images_sync(self, pdf_path: str, output_dir: str, 
                                 pages_per_batch: int = 10,
                                 file_prefix: Optional[str] = None) -> List[str]:
        """
        同步版本的转换方法（为了兼容性）
        """
        # 检测操作系统，在Windows上使用线程池而不是进程池
        import platform
        is_windows = platform.system() == "Windows"
        
        if self.is_jupyter or is_windows:
            # 在Jupyter或Windows中需要特殊处理asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用nest_asyncio
                    import nest_asyncio
                    nest_asyncio.apply()
            except:
                pass
        
        return asyncio.run(self.convert_pdf_to_images_async(
            pdf_path, output_dir, pages_per_batch, file_prefix
        ))

# 便捷函数
async def convert_pdf_async(pdf_path: str, output_dir: str, 
                          dpi: int = 200, pages_per_batch: int = 10,
                          max_workers: Optional[int] = None) -> List[str]:
    """
    便捷的异步PDF转换函数
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        dpi: 图片分辨率
        pages_per_batch: 每批次处理页数
        max_workers: 最大工作进程数
        
    Returns:
        转换后的图片文件路径列表
    """
    converter = AsyncPDFToImageConverter(max_workers=max_workers, dpi=dpi)
    return await converter.convert_pdf_to_images_async(
        pdf_path, output_dir, pages_per_batch
    )

def convert_pdf_sync(pdf_path: str, output_dir: str, 
                    dpi: int = 200, pages_per_batch: int = 10,
                    max_workers: Optional[int] = None) -> List[str]:
    """
    便捷的同步PDF转换函数
    """
    converter = AsyncPDFToImageConverter(max_workers=max_workers, dpi=dpi)
    return converter.convert_pdf_to_images_sync(
        pdf_path, output_dir, pages_per_batch
    )

# 示例使用代码
if __name__ == "__main__":
    # 添加多进程支持
    import multiprocessing
    multiprocessing.freeze_support()
    
    # 使用示例
    pdf_file = "files/爱尔眼科：2024年年度报告.pdf"
    output_directory = "files/aier"
    
    # 记录开始时间
    start_time = time.time()
    
    # 方式1: 使用同步方法（推荐，兼容性好）
    print("开始转换PDF...")
    image_files = convert_pdf_sync(
        pdf_path=pdf_file,
        output_dir=output_directory,
        dpi=100,
        pages_per_batch=5,  # 每批次处理5页
        max_workers=2       # 使用4个工作进程
    )
    
    end_time = time.time()
    print(f"转换完成！")
    print(f"总共转换了 {len(image_files)} 个图片文件")
    print(f"耗时: {end_time - start_time:.2f} 秒")
    print(f"平均每页: {(end_time - start_time) / len(image_files):.2f} 秒")
