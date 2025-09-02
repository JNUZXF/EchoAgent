# type: ignore

import re
from typing import List, Tuple

# --------------------------- 基础工具 --------------------------- #
_SENT_END = r'[。．！？!?；;…\n\n]+'
_TABLE_LINE = re.compile(r'^\s*[\+\|\-].*[\|\+]\s*$')   # 简易检测：含 |---| 或 +----+
_CODE_FENCE = re.compile(r'^```|^~~~')
_HEADER = re.compile(r'^\s{0,3}#+\s+\S')

def _collect_block(lines: List[str], start: int) -> Tuple[str, int]:
    """
    根据当前行类型收集一个不可拆分块，返回 (block_text, next_index)
    """
    line = lines[start]

    # 1. 代码块 ``` / ~~~
    if _CODE_FENCE.match(line):
        end = start + 1
        while end < len(lines) and not _CODE_FENCE.match(lines[end]):
            end += 1
        end = min(end + 1, len(lines))  # 包含闭 fence
        return "\n".join(lines[start:end]), end

    # 2. 表格块：连续满足 TABLE_LINE 或含 '|' 的行
    if '|' in line or _TABLE_LINE.match(line):
        end = start + 1
        while end < len(lines) and ('|' in lines[end] or _TABLE_LINE.match(lines[end])):
            end += 1
        return "\n".join(lines[start:end]), end

    # 3. 标题（Markdown #...）单独成块
    if _HEADER.match(line):
        return line, start + 1

    # 4. 普通文本 —— 继续收集直到句末标点
    chunk = [line]
    end = start + 1
    while end < len(lines) and not lines[end].strip():  # 空行视为句终
        chunk.append(lines[end])
        end += 1
    # 如仍在正文，按句号等切割
    joined = "\n".join(chunk)
    sentences = re.split(f'({_SENT_END})', joined)
    if len(sentences) > 1:
        # 取第一个完整句
        first_sent = "".join(sentences[:2])
        rest = "".join(sentences[2:])
        if rest.strip():
            # 把剩余重新插回行序列，让外层循环继续处理
            lines[start] = rest
            return first_sent, start + 1
    # 如果不是句子或最后一行
    return joined, end

def _split_to_units(text: str) -> List[str]:
    lines = text.splitlines()
    idx = 0
    units = []
    while idx < len(lines):
        block, idx = _collect_block(lines, idx)
        units.append(block)
    return [u for u in units if u.strip()]

# ------------------------- 主接口函数 -------------------------- #
def smart_paragraph_split_v2(text: str,
                             target_length: int = 500,
                             delta: float = 0.15) -> List[str]:
    """
    根据 target_length 智能分段，保持段落完整性（句子/表格/代码块不被拆分）。

    Args:
        text (str): 待切分全文
        target_length (int): 期望每段字符数
        delta (float): 长度容忍比例，例如 0.15 表示 ±15%

    Returns:
        List[str]: 分段结果
    """
    units = _split_to_units(text)
    if not units:
        return []

    paragraphs = []
    current = []
    cur_len = 0
    max_len = int(target_length * (1 + delta))

    for u in units:
        u_len = len(u)
        # 不加时距离 vs. 加后距离
        without_gap = abs(target_length - cur_len)
        with_gap = abs(target_length - (cur_len + u_len))
        if current and (cur_len + u_len > max_len) and (without_gap < with_gap):
            paragraphs.append("".join(current).strip())
            current = [u]
            cur_len = u_len
        else:
            current.append(u)
            cur_len += u_len

        # 极端情况：单块超长 -> 直接成段
        if u_len >= max_len:
            paragraphs.append("".join(current).strip())
            current, cur_len = [], 0

    if current:
        paragraphs.append("".join(current).strip())

    # 最后一段过短则尝试回并
    if len(paragraphs) >= 2 and len(paragraphs[-1]) < target_length * 0.5:
        tail = paragraphs.pop()
        if len(paragraphs[-1]) + len(tail) <= max_len:
            paragraphs[-1] += "\n" + tail
        else:
            paragraphs.append(tail)

    return paragraphs
