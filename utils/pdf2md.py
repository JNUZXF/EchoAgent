# type: ignore

# pdftomd.py
from nltk.tokenize import sent_tokenize

from markitdown import MarkItDown
import io
from typing import List, Tuple

class PDFToMarkdown:
    """
    PDFToMarkdown 是一个用于将 PDF 文件转换为 Markdown 文本的实用类，基于 Microsoft 的 markitdown 库。
    """

    def __init__(self, enable_plugins: bool = False, use_ocr: bool = False, docintel_endpoint: str = None):
        """
        初始化转换器。
        :param enable_plugins: 是否启用 markitdown 插件。
        :param use_ocr: 是否对 PDF 进行 OCR，以处理图片型文本。
        :param docintel_endpoint: 若需使用 Azure Document Intelligence，可传递 endpoint URL。
        """
        kwargs = {}
        if enable_plugins:
            kwargs['enable_plugins'] = True
        if docintel_endpoint:
            kwargs['docintel_endpoint'] = docintel_endpoint
            kwargs['enable_plugins'] = True  # Document Intelligence 通常作为插件处理

        self.md = MarkItDown(**kwargs)

        # 如果 use_ocr 为 True，可以启用 OCR 插件（需要安装 markitdown[pdf]）
        self.use_ocr = use_ocr

    def convert(self, pdf_path: str) -> str:
        """
        将指定 PDF 文件转换为 Markdown 文本。
        :param pdf_path: 输入 PDF 文件路径
        :return: 转换后的 markdown 文本
        """
        # markitdown.convert 接收路径，也可接收 bytes buffer
        # 对于纯文本 PDF，无需 OCR；否则，可使用 Azure DocIntel 或其它 OCR 插件
        result = self.md.convert(pdf_path)
        return result.text_content

    def convert_stream(self, pdf_bytes: bytes) -> str:
        """
        接受 PDF 的二进制内容并转换为 Markdown 文本。
        :param pdf_bytes: PDF 文件的二进制内容
        :return: 转换后的 markdown 文本
        """
        stream = io.BytesIO(pdf_bytes)
        result = self.md.convert(stream)
        return result.text_content

    def split_into_paragraphs(self, cleaned_text: str) -> List[str]:
        """
        将文本分割成段落
        
        Returns:
            段落列表
        """
        # 使用双换行符作为段落分隔符
        paragraphs = cleaned_text.split('\n\n')
        
        # 过滤空段落并清理每个段落
        self.paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        return self.paragraphs
    
    def smart_chunk_text(self, target_chunk_size: int = 1000, 
                        overlap_size: int = 100) -> List[Tuple[str, int, int]]:
        """
        智能分段，确保不会在段落中间截断
        
        Args:
            target_chunk_size: 目标段落大小（字符数）
            overlap_size: 段落之间的重叠大小
            
        Returns:
            分段列表，每项为 (文本内容, 开始位置, 结束位置)
        """
        chunks = []
        current_chunk = []
        current_size = 0
        start_pos = 0
        
        for i, paragraph in enumerate(self.paragraphs):
            para_size = len(paragraph)
            
            # 如果单个段落就超过目标大小，需要进一步分割
            if para_size > target_chunk_size:
                # 使用句子分割
                sentences = sent_tokenize(paragraph)
                
                for sentence in sentences:
                    if current_size + len(sentence) > target_chunk_size and current_chunk:
                        # 保存当前块
                        chunk_text = '\n\n'.join(current_chunk)
                        end_pos = start_pos + len(chunk_text)
                        chunks.append((chunk_text, start_pos, end_pos))
                        
                        # 处理重叠
                        if overlap_size > 0 and len(current_chunk) > 1:
                            # 保留最后几个句子作为重叠
                            overlap_text = []
                            overlap_len = 0
                            for j in range(len(current_chunk) - 1, -1, -1):
                                if overlap_len + len(current_chunk[j]) <= overlap_size:
                                    overlap_text.insert(0, current_chunk[j])
                                    overlap_len += len(current_chunk[j])
                                else:
                                    break
                            current_chunk = overlap_text
                            current_size = overlap_len
                            start_pos = end_pos - overlap_len
                        else:
                            current_chunk = []
                            current_size = 0
                            start_pos = end_pos
                    
                    current_chunk.append(sentence)
                    current_size += len(sentence)
            
            else:
                # 检查是否需要开始新的块
                if current_size + para_size > target_chunk_size and current_chunk:
                    # 保存当前块
                    chunk_text = '\n\n'.join(current_chunk)
                    end_pos = start_pos + len(chunk_text)
                    chunks.append((chunk_text, start_pos, end_pos))
                    
                    # 处理重叠
                    if overlap_size > 0:
                        overlap_text = []
                        overlap_len = 0
                        for j in range(len(current_chunk) - 1, -1, -1):
                            if overlap_len + len(current_chunk[j]) <= overlap_size:
                                overlap_text.insert(0, current_chunk[j])
                                overlap_len += len(current_chunk[j])
                            else:
                                break
                        current_chunk = overlap_text
                        current_size = overlap_len
                        start_pos = end_pos - overlap_len
                    else:
                        current_chunk = []
                        current_size = 0
                        start_pos = end_pos
                
                current_chunk.append(paragraph)
                current_size += para_size
        
        # 保存最后一个块
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            end_pos = start_pos + len(chunk_text)
            chunks.append((chunk_text, start_pos, end_pos))
        
        return chunks
    
    def split_pdf_to_chunks(self, pdf_path: str, target_chunk_size: int = 1000) -> dict:
        """
        完整处理PDF文件
        
        Args:
            target_chunk_size: 目标分段大小
            
        Returns:
            处理结果字典
        """
        # 1. 提取文本
        print("正在提取PDF文本...")
        raw_text = self.convert(pdf_path)
        
        if not raw_text:
            return {
                "success": False,
                "error": "无法从PDF提取文本"
            }
        
        # 2. 清洗文本
        print("正在清洗文本...")
        cleaned_text = raw_text.replace("\n", " ")
        
        # 3. 分割段落
        print("正在分割段落...")
        paragraphs = self.split_into_paragraphs(cleaned_text)
        
        # 4. 智能分段
        print("正在进行智能分段...")
        chunks = self.smart_chunk_text(target_chunk_size)
        
        # 5. 统计信息
        stats = {
            "原始文本长度": len(raw_text),
            "清洗后文本长度": len(cleaned_text),
            "段落数量": len(paragraphs),
            "分段数量": len(chunks),
            "平均段落长度": sum(len(p) for p in paragraphs) / len(paragraphs) if paragraphs else 0,
            "平均分段长度": sum(len(c[0]) for c in chunks) / len(chunks) if chunks else 0
        }
        
        return {
            "success": True,
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "paragraphs": paragraphs,
            "chunks": chunks,
            "stats": stats
        }

if __name__ == "__main__":
    pdf_file = r"D:\AgentBuilding\FinAgent\files\arxiv_papers\2506.19676v3.pdf"
    enable_ocr = False
    endpoint = None

    converter = PDFToMarkdown(enable_plugins=False, use_ocr=enable_ocr, docintel_endpoint=endpoint)
    md = converter.convert(pdf_file)
    print(md)
