import re
import json

def get_func_name(text):
    """
    提取文本中的函数名称
    """
    pattern = r'([a-zA-Z_]\w*)\('
    function_name = re.search(pattern, text)
    return function_name.group(1) if function_name else None

def convert_outer_quotes(tool: str) -> str:
    """
    将字符串中的 execute_sql(sql='...') 的最外层单引号
    替换为双引号，不修改内部其他单引号。
    """
    # 1) 找到 "sql='" 这个位置
    match = re.search(r"(sql=)'", tool)
    if not match:
        # 如果找不到 sql='，直接返回原字符串
        return tool
    
    # match.end() 是匹配到 ' 之后的位置，所以 -1 即可回到这个单引号的位置
    start_quote_idx = match.end() - 1
    
    # 2) 从字符串末尾往前找最后一个单引号
    end_quote_idx = tool.rfind("'")
    # 如果没找到，或者它就跟 start_quote_idx 相同(异常情况)，也不改
    if end_quote_idx <= start_quote_idx:
        return tool
    
    # 3) 构造新的字符串：把外层两个单引号改成双引号，其余部分不动
    new_tool = (
        tool[:start_quote_idx] +
        '"' +
        tool[start_quote_idx + 1:end_quote_idx] +
        '"' +
        tool[end_quote_idx + 1:]
    )
    return new_tool

def extract_params_to_json(function_call: str) -> str:
    """
    提取函数中的参数部分，并转换为 JSON 格式
    """
    # 首先提取整个参数部分
    param_pattern = r'\((.*)\)'
    params_match = re.search(param_pattern, function_call)
    if not params_match:
        return "{}"
    
    params_str = params_match.group(1)
    
    # 使用更强大的正则表达式来匹配参数
    param_pattern = r"""
        (\w+)\s*=\s*    # 键名和等号
        (?:
            '((?:[^'\\]|\\.)*)'  # 单引号值，支持转义
            |
            "((?:[^"\\]|\\.)*)"  # 双引号值，支持转义
        )
    """
    
    # 使用非贪婪模式来分割参数
    params_dict = {}
    matches = re.finditer(param_pattern, params_str, re.VERBOSE)
    
    for match in matches:
        key = match.group(1)
        # 获取非None的值（单引号或双引号中的内容）
        value = next(v for v in (match.group(2), match.group(3)) if v is not None)
        params_dict[key] = value
    
    return json.dumps(params_dict, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "SearchTableByKeywords(keywords=['信托公司', '代码类型', '企业信息'])",
    ]
    for test_case in test_cases:
        print("Output:", extract_params_to_json(test_case))
        print("-" * 80)