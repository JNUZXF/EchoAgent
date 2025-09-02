"""
pdf2image：将pdf转换为图片
"""

import os
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import fitz  # PyMuPDF
from PIL import Image
import io

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PDFToImageConverter:
    def __init__(self, pdf_path, image_folder, dpi=150, format='png', max_workers=None):
        """
        初始化PDF转图片转换器
        
        Args:
            pdf_path: PDF文件路径
            image_folder: 输出图片文件夹路径
            dpi: 输出图片DPI (默认150，可以调低到100以提高速度)
            format: 图片格式 ('png', 'jpg', 'jpeg')
            max_workers: 最大线程数 (默认为CPU核心数)
        """
        self.pdf_path = Path(pdf_path)
        self.image_folder = Path(image_folder)
        self.dpi = dpi
        self.format = format.lower()
        self.max_workers = max_workers or os.cpu_count()
        
        # 进度跟踪
        self.completed_pages = 0
        self.total_pages = 0
        self.progress_lock = Lock()
        
        # 验证输入
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {self.pdf_path}")
        
        # 创建输出文件夹
        self.image_folder.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"PDF路径: {self.pdf_path}")
        logger.info(f"输出文件夹: {self.image_folder}")
        logger.info(f"DPI: {self.dpi}")
        logger.info(f"图片格式: {self.format}")
        logger.info(f"最大线程数: {self.max_workers}")
    
    def convert_page(self, page_num, pdf_path):
        """
        转换单个页面
        
        Args:
            page_num: 页码（从0开始）
            pdf_path: PDF文件路径
        
        Returns:
            tuple: (页码, 是否成功, 耗时)
        """
        start_time = time.time()
        
        try:
            # 每个线程独立打开PDF文档
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            
            # 设置缩放矩阵
            zoom = self.dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为pixmap
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            
            # 转换为PIL Image
            img_data = pixmap.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            
            # 如果是JPEG格式，转换为RGB（去除alpha通道）
            if self.format in ['jpg', 'jpeg']:
                if img.mode in ('RGBA', 'LA'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
            
            # 保存图片
            output_path = self.image_folder / f"page_{page_num + 1:04d}.{self.format}"
            
            # 设置保存参数
            save_kwargs = {}
            if self.format in ['jpg', 'jpeg']:
                save_kwargs['quality'] = 85
                save_kwargs['optimize'] = True
            
            img.save(output_path, **save_kwargs)
            
            # 清理资源
            doc.close()
            
            # 更新进度
            with self.progress_lock:
                self.completed_pages += 1
                progress = (self.completed_pages / self.total_pages) * 100
                logger.info(f"进度: {self.completed_pages}/{self.total_pages} ({progress:.1f}%) - 完成第 {page_num + 1} 页")
            
            elapsed = time.time() - start_time
            return page_num, True, elapsed
            
        except Exception as e:
            logger.error(f"转换第 {page_num + 1} 页时出错: {str(e)}")
            elapsed = time.time() - start_time
            return page_num, False, elapsed
    
    def convert(self):
        """
        执行PDF转换
        
        Returns:
            dict: 转换统计信息
        """
        start_time = time.time()
        
        # 获取PDF总页数
        doc = fitz.open(self.pdf_path)
        self.total_pages = len(doc)
        doc.close()
        
        logger.info(f"开始转换，共 {self.total_pages} 页")
        
        # 使用线程池并行处理
        successful_pages = 0
        failed_pages = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(self.convert_page, page_num, str(self.pdf_path)): page_num 
                for page_num in range(self.total_pages)
            }
            
            # 处理完成的任务
            for future in as_completed(futures):
                page_num, success, elapsed = future.result()
                
                if success:
                    successful_pages += 1
                else:
                    failed_pages.append(page_num + 1)
        
        # 计算总耗时
        total_time = time.time() - start_time
        
        # 输出统计信息
        stats = {
            'total_pages': self.total_pages,
            'successful_pages': successful_pages,
            'failed_pages': failed_pages,
            'total_time': total_time,
            'average_time_per_page': total_time / self.total_pages if self.total_pages > 0 else 0,
            'pages_per_second': self.total_pages / total_time if total_time > 0 else 0
        }
        
        logger.info("=" * 50)
        logger.info(f"转换完成！")
        logger.info(f"总页数: {stats['total_pages']}")
        logger.info(f"成功: {stats['successful_pages']}")
        logger.info(f"失败: {len(stats['failed_pages'])}")
        logger.info(f"总耗时: {stats['total_time']:.2f} 秒")
        logger.info(f"平均每页: {stats['average_time_per_page']:.3f} 秒")
        logger.info(f"速度: {stats['pages_per_second']:.1f} 页/秒")
        
        if stats['failed_pages']:
            logger.warning(f"失败的页面: {stats['failed_pages']}")
        
        return stats


def convert_pdf_to_images(pdf_path, image_folder, **kwargs):
    """
    便捷函数：转换PDF为图片
    
    Args:
        pdf_path: PDF文件路径
        image_folder: 输出图片文件夹路径
        **kwargs: 其他可选参数
            - dpi: 输出DPI (默认150)
            - format: 图片格式 (默认'png')
            - max_workers: 最大线程数
    
    Returns:
        dict: 转换统计信息
    """
    converter = PDFToImageConverter(pdf_path, image_folder, **kwargs)
    return converter.convert()


# 使用示例
if __name__ == "__main__":
    # 基础用法
    pdf_path = "files/爱尔眼科：2024年年度报告.pdf"
    image_folder = "files/aier"
    
    # 方式1：使用便捷函数
    stats = convert_pdf_to_images(
        pdf_path,
        image_folder,
        dpi=150,  # 可以降低到100以提高速度
        format='jpg',  # jpg比png快
        max_workers=8  # 根据CPU调整
    )
    
    # 方式2：使用类（更多控制）
    # converter = PDFToImageConverter(
    #     pdf_path=pdf_path,
    #     image_folder=image_folder,
    #     dpi=100,  # 低DPI = 更快速度
    #     format='jpg',
    #     max_workers=None  # 自动检测CPU核心数
    # )
    # stats = converter.convert()
    
    # 性能优化建议
    print("\n性能优化建议：")
    print("1. 降低DPI到100可以显著提高速度（质量会略有下降）")
    print("2. 使用JPEG格式比PNG快")
    print("3. 增加max_workers数量（但不要超过CPU核心数太多）")
    print("4. 确保有足够的RAM（每个线程会占用一定内存）")
    print("5. 使用SSD硬盘可以提高I/O性能")







