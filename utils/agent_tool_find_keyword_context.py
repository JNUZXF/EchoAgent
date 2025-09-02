import re
from typing import List, Dict, Optional, Tuple

def find_keyword_context(md_path: str, keyword: str, 
                        context_lines: int = 10,
                        max_char_context: int = 2000,
                        case_sensitive: bool = False,
                        extend_to_headers: bool = True,
                        ensure_completeness: bool = True) -> List[Dict]:
    """
    在MD文件中查找关键词并返回完整的上下文
    
    Args:
        md_path: MD文件路径
        keyword: 要搜索的关键词
        context_lines: 前后获取的行数（作为初始范围）
        max_char_context: 最大字符数上下文（会根据内容完整性智能扩展）
        case_sensitive: 是否区分大小写
        extend_to_headers: 是否扩展到标题边界以保证内容完整性
        ensure_completeness: 是否确保表格、代码块等结构的完整性
    
    Returns:
        包含匹配结果的字典列表
    """
    try:
        # 读取文件
        with open(md_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        results = []
        
        # 设置搜索模式
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(keyword), flags)
        
        # 逐行搜索
        for i, line in enumerate(lines):
            matches = pattern.finditer(line)
            
            for match in matches:
                if extend_to_headers or ensure_completeness:
                    # 使用智能边界扩展
                    context, start_line, end_line, extension_info = _get_enhanced_smart_context(
                        lines, i, context_lines, max_char_context, 
                        extend_to_headers, ensure_completeness
                    )
                else:
                    # 使用原始方法
                    start_line = max(0, i - context_lines)
                    end_line = min(len(lines), i + context_lines + 1)
                    context_lines_list = lines[start_line:end_line]
                    context = ''.join(context_lines_list)
                    extension_info = {}
                    
                    if len(context) > max_char_context:
                        context = _trim_context_by_chars(context, keyword, max_char_context)
                
                result = {
                    'match_text': match.group(),
                    'line_number': i + 1,
                    'context': context.strip(),
                    'start_line': start_line + 1,
                    'end_line': end_line,
                    'match_position': match.start(),
                    'full_line': line.strip(),
                    'context_length': len(context),
                    'extended_for_completeness': extend_to_headers or ensure_completeness,
                    'extension_info': extension_info
                }
                
                results.append(result)
        
        return results
        
    except FileNotFoundError:
        print(f"错误：文件 {md_path} 不存在")
        return []
    except UnicodeDecodeError:
        print(f"错误：无法读取文件 {md_path}，编码问题")
        return []
    except Exception as e:
        print(f"错误：处理文件时出现异常 - {str(e)}")
        return []

def _get_enhanced_smart_context(lines: List[str], target_line: int, 
                               initial_context_lines: int, max_char_context: int,
                               extend_to_headers: bool, ensure_completeness: bool) -> Tuple[str, int, int, Dict]:
    """
    增强的智能上下文获取，确保内容完整性
    """
    # 初始范围
    start_line = max(0, target_line - initial_context_lines)
    end_line = min(len(lines), target_line + initial_context_lines + 1)
    
    extension_info = {
        'original_start': start_line,
        'original_end': end_line,
        'extended_for_headers': False,
        'extended_for_completeness': False,
        'final_char_count': 0,
        'exceeded_limit': False
    }
    
    # 第一步：扩展到标题边界
    if extend_to_headers:
        start_line, end_line = _extend_to_header_boundaries(
            lines, start_line, end_line, max_char_context
        )
        if start_line != extension_info['original_start'] or end_line != extension_info['original_end']:
            extension_info['extended_for_headers'] = True
    
    # 第二步：确保结构完整性
    if ensure_completeness:
        start_line, end_line, completeness_info = _ensure_structural_completeness(
            lines, start_line, end_line, max_char_context
        )
        extension_info.update(completeness_info)
    
    # 获取最终上下文
    context_lines_list = lines[start_line:end_line]
    context = ''.join(context_lines_list)
    
    extension_info['final_char_count'] = len(context)
    extension_info['exceeded_limit'] = len(context) > max_char_context
    
    return context, start_line, end_line, extension_info

def _ensure_structural_completeness(lines: List[str], start_line: int, end_line: int, 
                                  max_char_context: int) -> Tuple[int, int, Dict]:
    """
    确保结构化内容（表格、代码块、列表等）的完整性
    """
    completeness_info = {
        'extended_for_completeness': False,
        'table_completion': False,
        'code_block_completion': False,
        'list_completion': False,
        'quote_completion': False
    }
    
    original_start, original_end = start_line, end_line
    
    # 检查并完善开始边界
    start_line = _complete_start_boundary(lines, start_line)
    if start_line != original_start:
        completeness_info['extended_for_completeness'] = True
    
    # 检查并完善结束边界
    end_line, boundary_info = _complete_end_boundary(lines, end_line, max_char_context, start_line)
    if end_line != original_end:
        completeness_info['extended_for_completeness'] = True
        completeness_info.update(boundary_info)
    
    return start_line, end_line, completeness_info

def _complete_start_boundary(lines: List[str], start_line: int) -> int:
    """
    完善开始边界，确保不会从结构化内容中间开始
    """
    if start_line <= 0:
        return 0
    
    # 检查是否在表格中间
    if _is_in_middle_of_table(lines, start_line):
        start_line = _find_table_start(lines, start_line)
    
    # 检查是否在代码块中间
    if _is_in_middle_of_code_block(lines, start_line):
        start_line = _find_code_block_start(lines, start_line)
    
    # 检查是否在列表中间
    if _is_in_middle_of_list(lines, start_line):
        start_line = _find_list_start(lines, start_line)
    
    # 检查是否在引用块中间
    if _is_in_middle_of_quote(lines, start_line):
        start_line = _find_quote_start(lines, start_line)
    
    return start_line

def _complete_end_boundary(lines: List[str], end_line: int, max_char_context: int, 
                          start_line: int) -> Tuple[int, Dict]:
    """
    完善结束边界，确保结构化内容完整
    """
    boundary_info = {
        'table_completion': False,
        'code_block_completion': False,
        'list_completion': False,
        'quote_completion': False
    }
    
    if end_line >= len(lines):
        return len(lines), boundary_info
    
    max_extension = max_char_context * 2  # 允许适度超出限制以保证完整性
    
    # 检查表格完整性
    if _has_incomplete_table_at_end(lines, end_line):
        new_end = _find_table_end(lines, end_line)
        test_context = ''.join(lines[start_line:new_end])
        if len(test_context) <= max_extension:
            end_line = new_end
            boundary_info['table_completion'] = True
    
    # 检查代码块完整性
    if _has_incomplete_code_block_at_end(lines, start_line, end_line):
        new_end = _find_code_block_end(lines, end_line)
        test_context = ''.join(lines[start_line:new_end])
        if len(test_context) <= max_extension:
            end_line = new_end
            boundary_info['code_block_completion'] = True
    
    # 检查列表完整性
    if _has_incomplete_list_at_end(lines, end_line):
        new_end = _find_list_end(lines, end_line)
        test_context = ''.join(lines[start_line:new_end])
        if len(test_context) <= max_extension:
            end_line = new_end
            boundary_info['list_completion'] = True
    
    # 检查引用块完整性
    if _has_incomplete_quote_at_end(lines, end_line):
        new_end = _find_quote_end(lines, end_line)
        test_context = ''.join(lines[start_line:new_end])
        if len(test_context) <= max_extension:
            end_line = new_end
            boundary_info['quote_completion'] = True
    
    return end_line, boundary_info

# 表格相关检查函数
def _is_in_middle_of_table(lines: List[str], line_idx: int) -> bool:
    """检查是否在表格中间"""
    if line_idx <= 0 or line_idx >= len(lines):
        return False
    
    current_line = lines[line_idx].strip()
    prev_line = lines[line_idx - 1].strip() if line_idx > 0 else ""
    
    # 当前行是表格行，前一行也是表格相关行
    return ('|' in current_line and 
            ('|' in prev_line or re.match(r'^[\s\-\|:]+$', prev_line)))

def _find_table_start(lines: List[str], start_idx: int) -> int:
    """找到表格的开始"""
    for i in range(start_idx - 1, -1, -1):
        line = lines[i].strip()
        if not line or ('|' not in line and not re.match(r'^[\s\-\|:]+$', line)):
            return i + 1
    return 0

def _has_incomplete_table_at_end(lines: List[str], end_idx: int) -> bool:
    """检查结尾是否有不完整的表格"""
    if end_idx <= 0 or end_idx > len(lines):
        return False
    
    # 检查当前结束位置前的几行
    check_range = min(5, end_idx)
    for i in range(end_idx - check_range, end_idx):
        if i < len(lines) and '|' in lines[i]:
            # 如果有表格行，检查后面是否还有表格内容
            for j in range(end_idx, min(end_idx + 10, len(lines))):
                if '|' in lines[j] or re.match(r'^[\s\-\|:]+$', lines[j].strip()):
                    return True
            break
    return False

def _find_table_end(lines: List[str], start_idx: int) -> int:
    """找到表格的结束"""
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        if not line:
            # 空行，检查下一行是否还是表格
            if i + 1 < len(lines) and '|' not in lines[i + 1]:
                return i
        elif '|' not in line and not re.match(r'^[\s\-\|:]+$', line):
            return i
    return len(lines)

# 代码块相关检查函数
def _is_in_middle_of_code_block(lines: List[str], line_idx: int) -> bool:
    """检查是否在代码块中间"""
    if line_idx <= 0:
        return False
    
    # 计算之前的代码块标记数量
    code_block_count = 0
    for i in range(line_idx):
        if lines[i].strip().startswith('```'):
            code_block_count += 1
    
    return code_block_count % 2 == 1  # 奇数表示在代码块中

def _find_code_block_start(lines: List[str], start_idx: int) -> int:
    """找到代码块的开始"""
    for i in range(start_idx - 1, -1, -1):
        if lines[i].strip().startswith('```'):
            return i
    return 0

def _has_incomplete_code_block_at_end(lines: List[str], start_idx: int, end_idx: int) -> bool:
    """检查是否有不完整的代码块"""
    code_block_count = 0
    for i in range(start_idx, min(end_idx, len(lines))):
        if lines[i].strip().startswith('```'):
            code_block_count += 1
    
    return code_block_count % 2 == 1

def _find_code_block_end(lines: List[str], start_idx: int) -> int:
    """找到代码块的结束"""
    for i in range(start_idx, len(lines)):
        if lines[i].strip().startswith('```'):
            return i + 1
    return len(lines)

# 列表相关检查函数
def _is_in_middle_of_list(lines: List[str], line_idx: int) -> bool:
    """检查是否在列表中间"""
    if line_idx <= 0 or line_idx >= len(lines):
        return False
    
    current_line = lines[line_idx].strip()
    prev_line = lines[line_idx - 1].strip() if line_idx > 0 else ""
    
    # 当前行是列表项或缩进内容，前一行也是列表相关
    list_pattern = re.compile(r'^[\s]*[-*+]\s+|^[\s]*\d+\.\s+|^[\s]{2,}')
    return (list_pattern.match(current_line) and 
            (list_pattern.match(prev_line) or not prev_line))

def _find_list_start(lines: List[str], start_idx: int) -> int:
    """找到列表的开始"""
    list_pattern = re.compile(r'^[\s]*[-*+]\s+|^[\s]*\d+\.\s+')
    for i in range(start_idx - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        if not list_pattern.match(lines[i]) and not re.match(r'^[\s]{2,}', lines[i]):
            return i + 1
    return 0

def _has_incomplete_list_at_end(lines: List[str], end_idx: int) -> bool:
    """检查结尾是否有不完整的列表"""
    if end_idx <= 0 or end_idx > len(lines):
        return False
    
    list_pattern = re.compile(r'^[\s]*[-*+]\s+|^[\s]*\d+\.\s+|^[\s]{2,}')
    
    # 检查当前结束位置前的行是否是列表
    for i in range(max(0, end_idx - 3), end_idx):
        if i < len(lines) and list_pattern.match(lines[i]):
            # 检查后面是否还有列表内容
            for j in range(end_idx, min(end_idx + 5, len(lines))):
                if list_pattern.match(lines[j]):
                    return True
            break
    return False

def _find_list_end(lines: List[str], start_idx: int) -> int:
    """找到列表的结束"""
    list_pattern = re.compile(r'^[\s]*[-*+]\s+|^[\s]*\d+\.\s+|^[\s]{2,}')
    
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        if not line:
            # 空行，检查下一行
            if i + 1 < len(lines) and not list_pattern.match(lines[i + 1]):
                return i
        elif not list_pattern.match(lines[i]):
            return i
    return len(lines)

# 引用块相关检查函数
def _is_in_middle_of_quote(lines: List[str], line_idx: int) -> bool:
    """检查是否在引用块中间"""
    if line_idx <= 0 or line_idx >= len(lines):
        return False
    
    current_line = lines[line_idx].strip()
    prev_line = lines[line_idx - 1].strip() if line_idx > 0 else ""
    
    return (current_line.startswith('>') and prev_line.startswith('>'))

def _find_quote_start(lines: List[str], start_idx: int) -> int:
    """找到引用块的开始"""
    for i in range(start_idx - 1, -1, -1):
        line = lines[i].strip()
        if not line.startswith('>') and line:
            return i + 1
    return 0

def _has_incomplete_quote_at_end(lines: List[str], end_idx: int) -> bool:
    """检查结尾是否有不完整的引用块"""
    if end_idx <= 0 or end_idx > len(lines):
        return False
    
    # 检查当前结束位置前的行是否是引用
    for i in range(max(0, end_idx - 3), end_idx):
        if i < len(lines) and lines[i].strip().startswith('>'):
            # 检查后面是否还有引用内容
            for j in range(end_idx, min(end_idx + 5, len(lines))):
                if lines[j].strip().startswith('>'):
                    return True
            break
    return False

def _find_quote_end(lines: List[str], start_idx: int) -> int:
    """找到引用块的结束"""
    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        if not line:
            # 空行，检查下一行
            if i + 1 < len(lines) and not lines[i + 1].strip().startswith('>'):
                return i
        elif not line.startswith('>'):
            return i
    return len(lines)

def _extend_to_header_boundaries(lines: List[str], start_line: int, end_line: int, 
                               max_char_context: int) -> Tuple[int, int]:
    """
    扩展到标题边界，确保内容完整性
    """
    header_pattern = re.compile(r'^#{1,6}\s+')
    
    # 向上扩展到标题
    extended_start = start_line
    for i in range(start_line - 1, -1, -1):
        line = lines[i].strip()
        if header_pattern.match(line):
            extended_start = i
            break
        
        # 检查扩展后的长度
        test_context = ''.join(lines[i:end_line])
        if len(test_context) > max_char_context * 1.5:
            break
        extended_start = i
    
    # 向下扩展到下一个同级或更高级标题
    extended_end = end_line
    start_header_level = _get_line_header_level(lines[extended_start]) if extended_start < len(lines) else 0
    
    for i in range(end_line, len(lines)):
        line = lines[i].strip()
        if header_pattern.match(line):
            current_level = _get_line_header_level(lines[i])
            if start_header_level > 0 and current_level <= start_header_level:
                extended_end = i
                break
        
        # 检查扩展后的长度
        test_context = ''.join(lines[extended_start:i + 1])
        if len(test_context) > max_char_context * 1.5:
            break
        extended_end = i + 1
    
    return extended_start, extended_end

def _get_line_header_level(line: str) -> int:
    """
    获取行的标题级别
    """
    line = line.strip()
    if line.startswith('#'):
        level = 0
        for char in line:
            if char == '#':
                level += 1
            elif char == ' ':
                break
            else:
                return 0
        return level if level <= 6 else 0
    return 0

def _trim_context_by_chars(context: str, keyword: str, max_chars: int) -> str:
    """
    按字符数截取上下文，确保关键词在中间位置
    """
    keyword_pos = context.lower().find(keyword.lower())
    if keyword_pos == -1:
        return context[:max_chars]
    
    half_chars = max_chars // 2
    start_pos = max(0, keyword_pos - half_chars)
    end_pos = min(len(context), keyword_pos + len(keyword) + half_chars)
    
    trimmed = context[start_pos:end_pos]
    
    if start_pos > 0:
        trimmed = "..." + trimmed
    if end_pos < len(context):
        trimmed = trimmed + "..."
    
    return trimmed


class search_context_by_keyword:
    def execute(self, **kwargs):
        md_path = kwargs.get("md_path", "")
        keyword = kwargs.get("keyword", "")
        context_lines = kwargs.get("context_lines", 5)
        max_char_context = kwargs.get("max_char_context", 2000)
        extend_to_headers = kwargs.get("extend_to_headers", True)
        ensure_completeness = kwargs.get("ensure_completeness", True)

        results = find_keyword_context(
            md_path, 
            keyword, 
            context_lines=context_lines,
            max_char_context=max_char_context,
            extend_to_headers=extend_to_headers,
            ensure_completeness=ensure_completeness
        )
        results_list = [result["context"] for result in results]
        results_list = list(set(results_list))
        return results_list


if __name__ == "__main__":
    md_path = "files/fizz/歌尔股份/announcements/歌尔股份：2024年年度报告.md"
    keyword = "财务指标"

    kwargs = {
        "md_path": md_path,
        "keyword": keyword,
        "context_lines": 10,
        "max_char_context": 2000,
        "extend_to_headers": True,
        "ensure_completeness": True
    }

    results = search_context_by_keyword().execute(**kwargs)
    print(results[0])

