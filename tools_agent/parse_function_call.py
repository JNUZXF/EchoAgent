import re
import ast
import json

def parse_function_call(function_call: str) -> dict:
    """
    文件路径：tools_agent/parse_function_call.py
    功能：解析函数调用字符串，提取函数名和参数
    
    例如：
    1) "SearchTableByKeywords(keywords=['信托公司', '代码类型', '企业信息'])"
    2) "execute_sql(sql='SELECT ... CompanyCode = 1749 ...')"
    3) "arxiv_deep_search(keyword='AI', max_results=5, sort_by='arxiv.SortCriterion.SubmittedDate')"
    
    输出:
    {
        "function_name": "<函数名>",
        "params": {
            "<key>": <Python解析后的值(可能是list,str,int,float,bool等)>
        }
    }
    """
    function_call = function_call.strip()

    # 1) 提取函数名
    function_name_pattern = r'^([a-zA-Z_]\w*)\('
    function_name_match = re.match(function_name_pattern, function_call)
    function_name = function_name_match.group(1) if function_name_match else None

    # 2) 提取括号内的参数部分（支持多行，用 DOTALL）
    param_pattern = r'\((.*)\)'
    params_match = re.search(param_pattern, function_call, flags=re.DOTALL)
    if not params_match:
        return {"function_name": function_name, "params": {}}
    
    param_str = params_match.group(1).strip()

    # 3) 匹配类似 `key=...` 的顶层参数对：
    #    - key 只能是 (\w+)
    #    - 等号后面紧跟：
    #      a) 单引号包裹的内容 '...'
    #      b) 双引号包裹的内容 "..."
    #      c) 方括号包裹的内容 [...]
    #      d) 数字（整数或浮点数）
    #      e) 布尔值（True/False）
    #      f) None值
    #      g) 其他标识符（如枚举值等）
    
    param_pattern2 = r'''
        (\w+)\s*=\s*                # 键 = 
        (                           # 分组1: 值
            "(?:[^"\\]|\\.)*"       #   双引号字符串 (简版, 不含复杂转义)
          | '(?:[^'\\]|\\.)*'       #   单引号字符串 (简版, 不含复杂转义)
          | \[[^\]]*\]             #   最简单的方括号匹配(不支持嵌套)
          | \d+\.\d+               #   浮点数 (如 3.14)
          | \d+                    #   整数 (如 5, 123)
          | True|False             #   布尔值
          | None                   #   None值
          | [a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*  #   标识符或点分标识符 (如 arxiv.SortCriterion.SubmittedDate)
        )
    '''
    # 使用 re.VERBOSE 可以分行写正则，并忽略注释和多余空白
    matches = re.finditer(param_pattern2, param_str, flags=re.VERBOSE)

    params_dict = {}
    for match in matches:
        key = match.group(1)
        value_str = match.group(2)
        # 用 ast.literal_eval 去把字符串解析成 Python 对象
        try:
            # 对于标识符（如枚举值），不能用 ast.literal_eval，直接保留为字符串
            if re.match(r'^[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*$', value_str) and value_str not in ['True', 'False', 'None']:
                python_val = value_str  # 保留为字符串
            else:
                python_val = ast.literal_eval(value_str)
        except Exception:
            # 如果解析失败，就当原始字符串
            python_val = value_str
        
        params_dict[key] = python_val

    return {
        "function_name": function_name,
        "params": params_dict
    }

if __name__ == "__main__":
    # 测试用例，包含各种数据类型
    test_case1 = "SearchTableByKeywords(keywords=['信托公司', '代码类型', '企业信息'])"
    test_case2 = """execute_sql(sql='SELECT MSHName, CompanyCode = 1749 FROM SomeTable LIMIT 10')"""
    test_case3 = "arxiv_deep_search(keyword='AI', max_results=5, sort_by='arxiv.SortCriterion.SubmittedDate', sort_order='arxiv.SortOrder.Descending', search_field='all')"
    test_case4 = "test_function(name='test', count=10, rate=3.14, enabled=True, value=None)"
    test_case5 = "complex_function(items=[1, 2, 3], threshold=0.5, debug=False)"
    
    for tc in [test_case1, test_case2, test_case3, test_case4, test_case5]:
        result = parse_function_call(tc)
        print("源字符串：", tc)
        print("解析结果：", json.dumps(result, ensure_ascii=False, indent=4))
        print("--------------------------------------------------")
