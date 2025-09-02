"""
PDF阅读工具 - 为智能体提供PDF文档阅读能力
"""

import os
from typing import Dict, Any
from utils.pdf_processor import PDFTextProcessor

class PDFReaderTool:
    """PDF阅读工具类"""
    
    def __init__(self):
        self.name = "read_pdf"
        self.description = "阅读PDF文件并提取文本内容"
    
    def execute(self, pdf_path: str, **kwargs) -> str:
        """
        执行PDF阅读操作
        
        Args:
            pdf_path: PDF文件路径
            chunk_size: 文本分块大小（可选）
            **kwargs: 其他参数
            
        Returns:
            处理后的PDF文本内容
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(pdf_path):
                return f"错误：文件不存在 - {pdf_path}"
            
            # 检查是否为PDF文件
            if not pdf_path.lower().endswith('.pdf'):
                return f"错误：不是PDF文件 - {pdf_path}"
            
            print(f"[PDF阅读工具] 开始处理文件: {pdf_path}")
            
            # 创建PDF处理器实例
            processor = PDFTextProcessor(pdf_path)
            
            # 提取原始文本
            raw_text = processor.extract_text()
            # if not raw_text:
            #     return "错误：无法从PDF中提取文本内容"
            
            # # 清洗文本
            # cleaned_text = processor.clean_text(raw_text)
            
            # # 分割段落
            # paragraphs = processor.split_into_paragraphs()
            
            # # 智能分块
            # chunks = processor.smart_chunk_text(target_chunk_size=chunk_size)
            
            # # 格式化输出结果
            # result = self._format_pdf_content(pdf_path, cleaned_text, paragraphs, chunks)
            
            # print(f"[PDF阅读工具] 成功处理文件，提取了 {len(paragraphs)} 个段落，{len(chunks)} 个分块")
            
            return raw_text[:20000]
            
        except Exception as e:
            error_msg = f"PDF阅读工具执行出错: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return error_msg
    
    def _format_pdf_content(self, pdf_path: str, cleaned_text: str, 
                          paragraphs: list, chunks: list) -> str:
        """
        格式化PDF内容输出
        
        Args:
            pdf_path: PDF文件路径
            cleaned_text: 清洗后的文本
            paragraphs: 段落列表
            chunks: 分块列表
            
        Returns:
            格式化的内容字符串
        """
        # 获取文件基本信息
        file_name = os.path.basename(pdf_path)
        file_size = os.path.getsize(pdf_path)
        
        # 构建结果
        result_parts = []
        
        # 文件信息
        result_parts.append("="*60)
        result_parts.append(f"📄 PDF文件信息")
        result_parts.append("="*60)
        result_parts.append(f"文件名: {file_name}")
        result_parts.append(f"文件路径: {pdf_path}")
        result_parts.append(f"文件大小: {file_size / 1024:.2f} KB")
        result_parts.append(f"段落数量: {len(paragraphs)}")
        result_parts.append(f"分块数量: {len(chunks)}")
        result_parts.append(f"总字符数: {len(cleaned_text)}")
        result_parts.append("")
        
        # 内容摘要（前几个段落）
        result_parts.append("="*60)
        result_parts.append("📖 内容摘要（前3个段落）")
        result_parts.append("="*60)
        
        for i, paragraph in enumerate(paragraphs[:3]):
            result_parts.append(f"段落 {i+1}:")
            result_parts.append(paragraph)
            result_parts.append("")
        
        # 如果段落数量较多，显示更多信息
        if len(paragraphs) > 3:
            result_parts.append(f"... 还有 {len(paragraphs) - 3} 个段落")
            result_parts.append("")
        
        # 完整内容（如果文本不是太长）
        if len(cleaned_text) <= 5000:
            result_parts.append("="*60)
            result_parts.append("📋 完整内容")
            result_parts.append("="*60)
            result_parts.append(cleaned_text)
        else:
            result_parts.append("="*60)
            result_parts.append("📋 内容过长，仅显示前5000字符")
            result_parts.append("="*60)
            result_parts.append(cleaned_text[:5000])
            result_parts.append("\n... [内容已截断] ...")
        
        return "\n".join(result_parts) 
