# type: ignore

import os
import sys
import fitz  # PyMuPDF
import io
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np
import cv2
from dataclasses import dataclass
from enum import Enum
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageType(Enum):
    """图片类型枚举"""
    EMBEDDED = "embedded"      # 嵌入图片
    VECTOR = "vector"         # 矢量图
    CHART = "chart"           # 图表
    DIAGRAM = "diagram"       # 示意图
    PHOTO = "photo"           # 照片
    SCREENSHOT = "screenshot"  # 截图
    UNKNOWN = "unknown"       # 未知类型

@dataclass
class ImageInfo:
    """图片信息数据类"""
    page_num: int
    image_index: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    width: int
    height: int
    image_type: ImageType
    format: str
    size_bytes: int
    quality_score: float
    is_duplicate: bool
    hash_value: str
    confidence: float
    metadata: Dict[str, Any]

class PDFImageExtractor:
    """高级PDF图片提取器"""
    
    def __init__(self, 
                 min_width: int = 50,
                 min_height: int = 50,
                 min_area: int = 2500,
                 quality_threshold: float = 0.3,
                 duplicate_threshold: float = 0.95,
                 extract_vector_graphics: bool = True,
                 enhance_images: bool = True):
        """
        初始化PDF图片提取器
        
        Args:
            min_width: 最小图片宽度
            min_height: 最小图片高度
            min_area: 最小图片面积
            quality_threshold: 图片质量阈值
            duplicate_threshold: 重复图片检测阈值
            extract_vector_graphics: 是否提取矢量图
            enhance_images: 是否增强图片质量
        """
        self.min_width = min_width
        self.min_height = min_height
        self.min_area = min_area
        self.quality_threshold = quality_threshold
        self.duplicate_threshold = duplicate_threshold
        self.extract_vector_graphics = extract_vector_graphics
        self.enhance_images = enhance_images
        
        # 存储提取的图片信息
        self.extracted_images: List[ImageInfo] = []
        self.image_hashes: Dict[str, int] = {}  # 用于重复检测
        
    def extract_images_from_pdf(self, pdf_path: str, output_dir: str) -> List[ImageInfo]:
        """
        从PDF提取所有图片
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            提取的图片信息列表
        """
        logger.info(f"开始提取PDF图片: {pdf_path}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 打开PDF文档
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"PDF总页数: {len(doc)}")
        except Exception as e:
            logger.error(f"无法打开PDF文件: {e}")
            return []
        
        self.extracted_images = []
        self.image_hashes = {}
        
        try:
            # 遍历每一页
            for page_num in range(len(doc)):
                page = doc[page_num]
                logger.info(f"处理第 {page_num + 1} 页")
                
                # 提取嵌入图片
                embedded_images = self._extract_embedded_images(page, page_num, output_dir)
                self.extracted_images.extend(embedded_images)
                
                # 提取矢量图形（如果启用）
                if self.extract_vector_graphics:
                    vector_images = self._extract_vector_graphics(page, page_num, output_dir)
                    self.extracted_images.extend(vector_images)
                
                # 提取页面截图中的图片区域
                screenshot_images = self._extract_from_screenshot(page, page_num, output_dir)
                self.extracted_images.extend(screenshot_images)
        
        finally:
            doc.close()
        
        # 后处理：去重、分类、质量评估
        self._post_process_images()
        
        logger.info(f"提取完成，共找到 {len(self.extracted_images)} 张图片")
        return self.extracted_images
    
    def _extract_embedded_images(self, page: fitz.Page, page_num: int, output_dir: str) -> List[ImageInfo]:
        """提取页面中的嵌入图片"""
        images = []
        
        try:
            # 获取页面中的图片列表
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                try:
                    # 获取图片数据
                    xref = img[0]
                    pix = fitz.Pixmap(page.parent, xref)
                    
                    # 检查图片尺寸
                    if pix.width < self.min_width or pix.height < self.min_height:
                        pix = None
                        continue
                    
                    if pix.width * pix.height < self.min_area:
                        pix = None
                        continue
                    
                    # 转换为PIL图片
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_data = pix.tobytes("ppm")
                        pil_image = Image.open(io.BytesIO(img_data))
                    else:  # CMYK
                        pix1 = fitz.Pixmap(fitz.csRGB, pix)
                        img_data = pix1.tobytes("ppm")
                        pil_image = Image.open(io.BytesIO(img_data))
                        pix1 = None
                    
                    # 计算图片哈希
                    img_hash = self._calculate_image_hash(pil_image)
                    
                    # 检查是否重复
                    is_duplicate = self._is_duplicate_image(img_hash)
                    
                    # 评估图片质量
                    quality_score = self._assess_image_quality(pil_image)
                    
                    # 分类图片类型
                    image_type = self._classify_image_type(pil_image)
                    
                    # 获取图片在页面中的位置
                    bbox = self._get_image_bbox(page, xref)
                    
                    # 增强图片质量（如果启用）
                    if self.enhance_images and quality_score < 0.7:
                        pil_image = self._enhance_image(pil_image)
                    
                    # 保存图片
                    filename = f"page_{page_num+1:03d}_img_{img_index+1:03d}.png"
                    filepath = os.path.join(output_dir, filename)
                    pil_image.save(filepath, "PNG")
                    
                    # 创建图片信息对象
                    img_info = ImageInfo(
                        page_num=page_num + 1,
                        image_index=img_index + 1,
                        bbox=bbox,
                        width=pil_image.width,
                        height=pil_image.height,
                        image_type=image_type,
                        format="PNG",
                        size_bytes=os.path.getsize(filepath),
                        quality_score=quality_score,
                        is_duplicate=is_duplicate,
                        hash_value=img_hash,
                        confidence=0.9,
                        metadata={
                            "extraction_method": "embedded",
                            "original_format": self._get_original_format(img),
                            "filepath": filepath
                        }
                    )
                    
                    images.append(img_info)
                    
                    # 记录哈希值
                    if not is_duplicate:
                        self.image_hashes[img_hash] = len(self.image_hashes)
                    
                    pix = None
                    
                except Exception as e:
                    logger.warning(f"提取第 {page_num+1} 页第 {img_index+1} 张图片失败: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"提取第 {page_num+1} 页嵌入图片失败: {e}")
        
        return images
    
    def _extract_vector_graphics(self, page: fitz.Page, page_num: int, output_dir: str) -> List[ImageInfo]:
        """提取矢量图形"""
        images = []
        
        try:
            # 获取页面的绘图指令
            drawings = page.get_drawings()
            
            if not drawings:
                return images
            
            # 将矢量图形渲染为图片
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2倍分辨率
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # 使用图像分割技术提取图形区域
            vector_regions = self._segment_vector_graphics(pil_image, drawings)
            
            for idx, region in enumerate(vector_regions):
                if region['area'] < self.min_area:
                    continue
                
                # 裁剪图形区域
                bbox = region['bbox']
                cropped_image = pil_image.crop(bbox)
                
                # 计算哈希值
                img_hash = self._calculate_image_hash(cropped_image)
                is_duplicate = self._is_duplicate_image(img_hash)
                
                # 评估质量
                quality_score = self._assess_image_quality(cropped_image)
                
                if quality_score < self.quality_threshold:
                    continue
                
                # 保存图片
                filename = f"page_{page_num+1:03d}_vector_{idx+1:03d}.png"
                filepath = os.path.join(output_dir, filename)
                cropped_image.save(filepath, "PNG")
                
                # 创建图片信息
                img_info = ImageInfo(
                    page_num=page_num + 1,
                    image_index=idx + 1,
                    bbox=bbox,
                    width=cropped_image.width,
                    height=cropped_image.height,
                    image_type=ImageType.VECTOR,
                    format="PNG",
                    size_bytes=os.path.getsize(filepath),
                    quality_score=quality_score,
                    is_duplicate=is_duplicate,
                    hash_value=img_hash,
                    confidence=0.7,
                    metadata={
                        "extraction_method": "vector",
                        "drawing_count": len(drawings),
                        "filepath": filepath
                    }
                )
                
                images.append(img_info)
                
                if not is_duplicate:
                    self.image_hashes[img_hash] = len(self.image_hashes)
            
            pix = None
            
        except Exception as e:
            logger.error(f"提取第 {page_num+1} 页矢量图形失败: {e}")
        
        return images
    
    def _extract_from_screenshot(self, page: fitz.Page, page_num: int, output_dir: str) -> List[ImageInfo]:
        """从页面截图中提取图片区域"""
        images = []
        
        try:
            # 获取高分辨率页面截图
            mat = fitz.Matrix(3, 3)  # 3倍分辨率
            pix = page.get_pixmap(matrix=mat)
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # 使用计算机视觉技术检测图片区域
            image_regions = self._detect_image_regions(pil_image)
            
            for idx, region in enumerate(image_regions):
                if region['confidence'] < 0.5:
                    continue
                
                bbox = region['bbox']
                cropped_image = pil_image.crop(bbox)
                
                # 检查尺寸
                if cropped_image.width < self.min_width or cropped_image.height < self.min_height:
                    continue
                
                # 计算哈希和质量
                img_hash = self._calculate_image_hash(cropped_image)
                is_duplicate = self._is_duplicate_image(img_hash)
                quality_score = self._assess_image_quality(cropped_image)
                
                if quality_score < self.quality_threshold:
                    continue
                
                # 分类图片类型
                image_type = self._classify_image_type(cropped_image)
                
                # 保存图片
                filename = f"page_{page_num+1:03d}_region_{idx+1:03d}.png"
                filepath = os.path.join(output_dir, filename)
                cropped_image.save(filepath, "PNG")
                
                # 创建图片信息
                img_info = ImageInfo(
                    page_num=page_num + 1,
                    image_index=idx + 1,
                    bbox=bbox,
                    width=cropped_image.width,
                    height=cropped_image.height,
                    image_type=image_type,
                    format="PNG",
                    size_bytes=os.path.getsize(filepath),
                    quality_score=quality_score,
                    is_duplicate=is_duplicate,
                    hash_value=img_hash,
                    confidence=region['confidence'],
                    metadata={
                        "extraction_method": "screenshot",
                        "detection_method": region['method'],
                        "filepath": filepath
                    }
                )
                
                images.append(img_info)
                
                if not is_duplicate:
                    self.image_hashes[img_hash] = len(self.image_hashes)
            
            pix = None
            
        except Exception as e:
            logger.error(f"从第 {page_num+1} 页截图提取图片失败: {e}")
        
        return images
    
    def _calculate_image_hash(self, image: Image.Image) -> str:
        """计算图片的感知哈希值"""
        try:
            # 转换为灰度图
            gray = image.convert('L')
            # 缩放到8x8
            gray = gray.resize((8, 8), Image.LANCZOS)
            # 计算平均值
            pixels = list(gray.getdata())
            avg = sum(pixels) / len(pixels)
            # 生成哈希
            hash_bits = []
            for pixel in pixels:
                hash_bits.append('1' if pixel > avg else '0')
            return ''.join(hash_bits)
        except:
            return hashlib.md5(image.tobytes()).hexdigest()
    
    def _is_duplicate_image(self, img_hash: str) -> bool:
        """检查图片是否重复"""
        for existing_hash in self.image_hashes.keys():
            # 计算汉明距离
            distance = sum(c1 != c2 for c1, c2 in zip(img_hash, existing_hash))
            similarity = 1 - (distance / len(img_hash))
            if similarity >= self.duplicate_threshold:
                return True
        return False
    
    def _assess_image_quality(self, image: Image.Image) -> float:
        """评估图片质量"""
        try:
            # 转换为numpy数组
            img_array = np.array(image)
            
            # 计算多个质量指标
            scores = []
            
            # 1. 清晰度（拉普拉斯方差）
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(laplacian_var / 1000, 1.0)
            scores.append(sharpness_score)
            
            # 2. 对比度
            contrast = gray.std() / 255.0
            scores.append(contrast)
            
            # 3. 亮度分布
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            brightness_score = 1 - abs(0.5 - (gray.mean() / 255.0))
            scores.append(brightness_score)
            
            # 4. 信息熵
            entropy = -np.sum(hist * np.log2(hist + 1e-10)) / hist.sum()
            entropy_score = min(entropy / 8, 1.0)
            scores.append(entropy_score)
            
            # 综合评分
            quality_score = np.mean(scores)
            return float(quality_score)
            
        except Exception as e:
            logger.warning(f"质量评估失败: {e}")
            return 0.5
    
    def _classify_image_type(self, image: Image.Image) -> ImageType:
        """分类图片类型"""
        try:
            width, height = image.size
            aspect_ratio = width / height
            
            # 转换为numpy数组进行分析
            img_array = np.array(image)
            
            # 计算颜色复杂度
            if len(img_array.shape) == 3:
                color_complexity = len(np.unique(img_array.reshape(-1, img_array.shape[2]), axis=0))
            else:
                color_complexity = len(np.unique(img_array))
            
            # 计算边缘密度
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / (width * height)
            
            # 基于特征分类
            if edge_density > 0.1 and color_complexity < 100:
                return ImageType.DIAGRAM
            elif edge_density > 0.05 and aspect_ratio > 1.2:
                return ImageType.CHART
            elif color_complexity > 1000:
                return ImageType.PHOTO
            elif edge_density < 0.02:
                return ImageType.SCREENSHOT
            else:
                return ImageType.UNKNOWN
                
        except Exception as e:
            logger.warning(f"图片分类失败: {e}")
            return ImageType.UNKNOWN
    
    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """增强图片质量"""
        try:
            # 锐化
            enhanced = image.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
            
            # 调整对比度
            enhancer = ImageEnhance.Contrast(enhanced)
            enhanced = enhancer.enhance(1.2)
            
            # 调整亮度
            enhancer = ImageEnhance.Brightness(enhanced)
            enhanced = enhancer.enhance(1.1)
            
            return enhanced
        except:
            return image
    
    def _get_image_bbox(self, page: fitz.Page, xref: int) -> Tuple[float, float, float, float]:
        """获取图片在页面中的边界框"""
        try:
            # 查找图片在页面中的位置
            for item in page.get_images(full=True):
                if item[0] == xref:
                    # 尝试获取变换矩阵
                    try:
                        rect = page.get_image_bbox(item)
                        return (rect.x0, rect.y0, rect.x1, rect.y1)
                    except:
                        pass
            
            # 如果无法获取精确位置，返回默认值
            return (0, 0, 100, 100)
        except:
            return (0, 0, 100, 100)
    
    def _get_original_format(self, img_info: tuple) -> str:
        """获取图片原始格式"""
        try:
            ext = img_info[8] if len(img_info) > 8 else ""
            if ext:
                return ext.upper()
            return "UNKNOWN"
        except:
            return "UNKNOWN"
    
    def _segment_vector_graphics(self, image: Image.Image, drawings: list) -> List[Dict]:
        """分割矢量图形区域"""
        regions = []
        try:
            # 简化实现：基于绘图指令的边界框
            for drawing in drawings:
                if 'rect' in drawing:
                    rect = drawing['rect']
                    bbox = (int(rect.x0), int(rect.y0), int(rect.x1), int(rect.y1))
                    area = (rect.x1 - rect.x0) * (rect.y1 - rect.y0)
                    
                    regions.append({
                        'bbox': bbox,
                        'area': area,
                        'confidence': 0.8
                    })
        except Exception as e:
            logger.warning(f"矢量图形分割失败: {e}")
        
        return regions
    
    def _detect_image_regions(self, image: Image.Image) -> List[Dict]:
        """检测图片区域"""
        regions = []
        try:
            # 转换为OpenCV格式
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # 使用边缘检测和轮廓查找
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h
                
                if area > self.min_area:
                    regions.append({
                        'bbox': (x, y, x + w, y + h),
                        'area': area,
                        'confidence': 0.6,
                        'method': 'contour_detection'
                    })
        
        except Exception as e:
            logger.warning(f"图片区域检测失败: {e}")
        
        return regions
    
    def _post_process_images(self):
        """后处理提取的图片"""
        logger.info("开始后处理图片...")
        
        # 按质量分数排序
        self.extracted_images.sort(key=lambda x: x.quality_score, reverse=True)
        
        # 移除低质量图片
        high_quality_images = [img for img in self.extracted_images 
                              if img.quality_score >= self.quality_threshold]
        
        logger.info(f"过滤后保留 {len(high_quality_images)} 张高质量图片")
        self.extracted_images = high_quality_images
    
    def save_extraction_report(self, output_path: str):
        """保存提取报告"""
        report = {
            'total_images': len(self.extracted_images),
            'extraction_settings': {
                'min_width': self.min_width,
                'min_height': self.min_height,
                'min_area': self.min_area,
                'quality_threshold': self.quality_threshold,
                'duplicate_threshold': self.duplicate_threshold
            },
            'images': []
        }
        
        for img in self.extracted_images:
            report['images'].append({
                'page_num': img.page_num,
                'image_index': img.image_index,
                'bbox': img.bbox,
                'width': img.width,
                'height': img.height,
                'image_type': img.image_type.value,
                'format': img.format,
                'size_bytes': img.size_bytes,
                'quality_score': img.quality_score,
                'is_duplicate': img.is_duplicate,
                'confidence': img.confidence,
                'metadata': img.metadata
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"提取报告已保存到: {output_path}")

# 便捷函数
def extract_images_from_pdf(pdf_path: str, 
                          output_dir: str,
                          min_width: int = 50,
                          min_height: int = 50,
                          min_area: int = 2500,
                          quality_threshold: float = 0.3,
                          extract_vector: bool = True,
                          enhance_images: bool = True,
                          save_report: bool = True) -> List[ImageInfo]:
    """
    从PDF提取图片的便捷函数
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        min_width: 最小宽度
        min_height: 最小高度
        min_area: 最小面积
        quality_threshold: 质量阈值
        extract_vector: 是否提取矢量图
        enhance_images: 是否增强图片
        save_report: 是否保存报告
        
    Returns:
        提取的图片信息列表
    """
    extractor = PDFImageExtractor(
        min_width=min_width,
        min_height=min_height,
        min_area=min_area,
        quality_threshold=quality_threshold,
        extract_vector_graphics=extract_vector,
        enhance_images=enhance_images
    )
    
    images = extractor.extract_images_from_pdf(pdf_path, output_dir)
    
    if save_report:
        report_path = os.path.join(output_dir, "extraction_report.json")
        extractor.save_extraction_report(report_path)
    
    return images

# 示例使用
if __name__ == "__main__":
    pdf_file = r"D:\AgentBuilding\FinAgent\files\arxiv_papers\2408.02544v2.pdf"
    output_directory = "extracted_images"
    
    if os.path.exists(pdf_file):
        images = extract_images_from_pdf(
            pdf_path=pdf_file,
            output_dir=output_directory,
            min_width=100,
            min_height=100,
            quality_threshold=0.4,
            extract_vector=True,
            enhance_images=True
        )
        
        print(f"成功提取 {len(images)} 张图片")
        for img in images:
            print(f"页面 {img.page_num}: {img.image_type.value} - 质量: {img.quality_score:.2f}")
    else:
        print(f"PDF文件不存在: {pdf_file}") 