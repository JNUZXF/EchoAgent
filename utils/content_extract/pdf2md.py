
"""

!pip install "markitdown[all]" --user

"""

from markitdown import MarkItDown
import io

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

if __name__ == "__main__":
    pdf_file = r"D:\AgentBuilding\FinAgent\files\arxiv_papers\2506.19676v3.pdf"
    enable_ocr = False
    endpoint = None

    converter = PDFToMarkdown(enable_plugins=False, use_ocr=enable_ocr, docintel_endpoint=endpoint)
    md = converter.convert(pdf_file)
    print(md)
