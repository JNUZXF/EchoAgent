
from utils.pdf2md import PDFToMarkdown

import re
from typing import List, Dict, Optional

def find_keyword_paragraphs(
    text: str, 
    keyword: str, 
    max_para_num: int = 3,
    case_sensitive: bool = False,
    expand_context: bool = True
) -> Dict:
    """
    基于关键词在文本中定位包含该关键词的完整段落
    
    参数:
        text (str): 待搜索的长文本
        keyword (str): 要搜索的关键词
        max_para_num (int): 返回的最大段落数量，默认3
        case_sensitive (bool): 是否区分大小写，默认False
        expand_context (bool): 是否扩展上下文确保段落完整，默认True
    
    返回:
        Dict: 包含找到的段落信息的字典
    """
    
    if not text or not keyword:
        return {
            "found": False,
            "message": "文本或关键词不能为空",
            "paragraphs": []
        }
    
    # 设置搜索模式
    search_flags = 0 if case_sensitive else re.IGNORECASE
    
    # 检查是否包含关键词
    if not re.search(re.escape(keyword), text, search_flags):
        return {
            "found": False,
            "message": f"在文本中未找到关键词: '{keyword}'",
            "paragraphs": []
        }
    
    # 按自然段落分割文本（双换行或多个换行符）
    natural_paragraphs = re.split(r'\n\s*\n', text.strip())
    natural_paragraphs = [p.strip() for p in natural_paragraphs if p.strip()]
    
    # 如果没有明显的段落分隔，则按句子重新组织段落
    if len(natural_paragraphs) == 1:
        natural_paragraphs = _reorganize_by_sentences(text)
    
    # 找到包含关键词的段落
    matching_paragraphs = []
    
    for i, paragraph in enumerate(natural_paragraphs):
        if re.search(re.escape(keyword), paragraph, search_flags):
            # 确保段落完整性，必要时扩展上下文
            complete_paragraph = paragraph
            if expand_context:
                complete_paragraph = _ensure_paragraph_completeness(
                    paragraph, natural_paragraphs, i
                )
            
            # 计算在原文本中的大概位置
            start_pos = text.find(paragraph[:50]) if len(paragraph) >= 50 else text.find(paragraph)
            
            # 高亮显示关键词
            highlighted_paragraph = re.sub(
                f'({re.escape(keyword)})', 
                r'【\1】', 
                complete_paragraph, 
                flags=search_flags
            )
            
            # 计算关键词出现次数
            keyword_count = len(re.findall(re.escape(keyword), complete_paragraph, search_flags))
            
            matching_paragraphs.append({
                "paragraph_index": i + 1,
                "start_position": start_pos if start_pos != -1 else "未知",
                "length": len(complete_paragraph),
                "content": complete_paragraph,
                "highlighted_content": highlighted_paragraph,
                "keyword_count": keyword_count,
                "is_expanded": complete_paragraph != paragraph
            })
    
    # 按关键词出现次数降序排序，取前max_para_num个
    matching_paragraphs.sort(key=lambda x: x["keyword_count"], reverse=True)
    matching_paragraphs = matching_paragraphs[:max_para_num]
    
    return {
        "found": True,
        "message": f"找到 {len(matching_paragraphs)} 个包含关键词 '{keyword}' 的完整段落",
        "total_paragraphs": len(natural_paragraphs),
        "paragraphs": matching_paragraphs
    }


def _reorganize_by_sentences(text: str) -> List[str]:
    """
    当文本没有明显段落分隔时，按句子重新组织成逻辑段落
    """
    # 按句号、感叹号、问号分割句子
    sentences = re.split(r'([。！？])', text)
    
    # 重新组合句子和标点
    organized_sentences = []
    for i in range(0, len(sentences)-1, 2):
        if i+1 < len(sentences):
            sentence = sentences[i] + sentences[i+1]
            if sentence.strip():
                organized_sentences.append(sentence.strip())
    
    # 将连续的短句组合成段落（以主题相关性为准）
    paragraphs = []
    current_paragraph = ""
    
    for sentence in organized_sentences:
        # 如果是新的主题开始（通过一些关键词判断）
        topic_starters = ['首先', '其次', '然后', '接下来', '最后', '总之', '因此', '所以', '但是', '然而', '不过']
        is_new_topic = any(sentence.strip().startswith(starter) for starter in topic_starters)
        
        if is_new_topic and current_paragraph:
            paragraphs.append(current_paragraph.strip())
            current_paragraph = sentence
        else:
            current_paragraph += sentence
        
        # 如果当前段落已经比较长了，考虑分段
        if len(current_paragraph) > 300:
            paragraphs.append(current_paragraph.strip())
            current_paragraph = ""
    
    # 添加最后一个段落
    if current_paragraph:
        paragraphs.append(current_paragraph.strip())
    
    return [p for p in paragraphs if p]


def _ensure_paragraph_completeness(paragraph: str, all_paragraphs: List[str], current_index: int) -> str:
    """
    确保段落的完整性，必要时向前或向后扩展
    """
    complete_paragraph = paragraph
    
    # 检查段落开头是否完整（不以小写字母或某些词开始）
    incomplete_starts = ['和', '或', '但', '而', '因为', '所以', '然后', '接着', '同时', '另外', '此外']
    if (paragraph[0].islower() or 
        any(paragraph.startswith(start) for start in incomplete_starts)):
        # 向前扩展
        if current_index > 0:
            complete_paragraph = all_paragraphs[current_index - 1] + " " + complete_paragraph
    
    # 检查段落结尾是否完整（不以逗号、分号等结尾）
    incomplete_ends = [',', '，', ';', '；', '、', '和', '或', '以及']
    if any(paragraph.rstrip().endswith(end) for end in incomplete_ends):
        # 向后扩展
        if current_index < len(all_paragraphs) - 1:
            complete_paragraph = complete_paragraph + " " + all_paragraphs[current_index + 1]
    
    return complete_paragraph


def print_results(result: Dict):
    """
    格式化打印搜索结果
    """
    print("=" * 80)
    print(f"搜索结果: {result['message']}")
    print("=" * 80)
    
    if result['found']:
        print(f"文本总段落数: {result['total_paragraphs']}")
        print()
        
        for i, para in enumerate(result['paragraphs'], 1):
            print(f"【段落 {i}】")
            print(f"原文段落序号: {para['paragraph_index']}")
            print(f"起始位置: {para['start_position']}")
            print(f"段落长度: {para['length']} 字符")
            print(f"关键词出现次数: {para['keyword_count']}")
            print(f"是否扩展了上下文: {'是' if para['is_expanded'] else '否'}")
            print(f"内容: {para['highlighted_content']}")
            print("-" * 60)

# 使用示例
if __name__ == "__main__":
    keyword = "Agent"
    pdf_path = r"D:\AgentBuilding\my_agent_frame\agent_cases\research_agent\arxiv_papers\2306.01284v4_Post-COVID Inflation  the Monetary Policy Dilemma An Agent-Based Scenario Analysis.pdf"
    enable_ocr = False
    endpoint = None
    converter = PDFToMarkdown(enable_plugins=False, use_ocr=enable_ocr, docintel_endpoint=endpoint)
    md_text = converter.convert(pdf_path)
    
    # 搜索关键词 "人工智能"
    result = find_keyword_paragraphs(
        text=md_text,
        keyword="Agent",
        max_para_num=3,
        expand_context=True
    )
    
    print_results(result)












