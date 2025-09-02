import re
import json
from typing import Union, List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from json.decoder import JSONDecodeError

@dataclass
class JsonExtractResult:
    """存储JSON提取结果的数据类"""
    success: bool
    data: Union[Dict[str, Any], List[Any], None]
    error: str = ""

class JsonTextExtractor:
    """JSON文本提取器"""
    
    def __init__(self):
        # 匹配```json开头和```结尾的正则表达式
        self.json_block_pattern = r'```json\s*(.*?)\s*```'
        # 编译正则表达式以提高性能
        self.block_pattern = re.compile(self.json_block_pattern, re.DOTALL)

    def _normalize_text(self, text: str) -> str:
        """规范化文本"""
        if not isinstance(text, str):
            raise TypeError("Input must be a string")
        
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 删除UTF-8 BOM
        text = text.replace('\ufeff', '')
        # 确保文本两端有足够的空白字符
        text = f"\n{text}\n"
        return text

    def _clean_json_text(self, json_text: str) -> str:
        """清理JSON文本"""
        # 移除注释
        json_text = re.sub(r'//.*?\n|/\*.*?\*/', '', json_text, flags=re.DOTALL)
        # 去掉前后空白字符
        return json_text.strip()

    def _find_json_object(self, text: str, start: int = 0) -> Tuple[int, int]:
        """
        在文本中查找完整的JSON对象
        
        Args:
            text: 要搜索的文本
            start: 开始搜索的位置
            
        Returns:
            Tuple[int, int]: (start_pos, end_pos) 如果找到，否则 (-1, -1)
        """
        # 查找开始的大括号
        start_pos = text.find('{', start)
        if start_pos == -1:
            return -1, -1
            
        stack = []
        in_string = False
        escape = False
        pos = start_pos
        
        while pos < len(text):
            char = text[pos]
            
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"' and not escape:
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    stack.append(char)
                elif char == '}':
                    if not stack:
                        return -1, -1
                    stack.pop()
                    if not stack:
                        return start_pos, pos + 1
            
            pos += 1
            
        return -1, -1

    def _extract_json_from_block(self, block_text: str) -> JsonExtractResult:
        """从代码块中提取JSON"""
        try:
            # 查找第一个{和最后一个}
            start = block_text.find('{')
            if start == -1:
                return JsonExtractResult(success=False, data=None, 
                                       error="No JSON object found")
            
            # 从开始位置向后查找匹配的结束括号
            stack = []
            in_string = False
            escape = False
            pos = start
            end = -1
            
            while pos < len(block_text):
                char = block_text[pos]
                
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if char == '{':
                        stack.append(char)
                    elif char == '}':
                        if stack:
                            stack.pop()
                            if not stack:
                                end = pos + 1
                                break
                
                pos += 1
            
            if end == -1:
                return JsonExtractResult(success=False, data=None, 
                                       error="No matching closing brace found")
            
            json_text = block_text[start:end]
            return self._parse_json(json_text)
            
        except Exception as e:
            return JsonExtractResult(success=False, data=None, 
                                   error=f"Error extracting JSON: {str(e)}")

    def extract_json(self, text: str) -> Union[JsonExtractResult, List[JsonExtractResult]]:
        """
        从文本中提取JSON数据
        
        Args:
            text: 包含JSON数据的文本
            
        Returns:
            如果只有一个JSON块，返回单个JsonExtractResult
            如果有多个JSON块，返回JsonExtractResult列表
        """
        try:
            # 规范化文本
            text = self._normalize_text(text)
            results = []
            
            # 首先尝试查找```json块
            block_matches = self.block_pattern.finditer(text)
            for match in block_matches:
                block_text = match.group(1)
                result = self._extract_json_from_block(block_text)
                if result.success:
                    results.append(result)
                    continue
            
            # 如果没有找到有效的```json块，尝试直接查找JSON对象
            if not results:
                pos = 0
                while pos < len(text):
                    start, end = self._find_json_object(text, pos)
                    if start == -1:
                        break
                        
                    json_text = text[start:end]
                    cleaned_json = self._clean_json_text(json_text)
                    result = self._parse_json(cleaned_json)
                    if result.success:
                        results.append(result)
                    
                    pos = end
            
            # 根据结果数量返回
            if not results:
                return JsonExtractResult(success=False, data=None, 
                                       error="No valid JSON found")
            return results[0] if len(results) == 1 else results
            
        except Exception as e:
            return JsonExtractResult(success=False, data=None, 
                                   error=f"Extraction error: {str(e)}")

    def _parse_json(self, json_text: str) -> JsonExtractResult:
        """解析JSON文本"""
        try:
            # 尝试解析JSON
            data = json.loads(json_text)
            return JsonExtractResult(success=True, data=data)
        except json.JSONDecodeError as e:
            return JsonExtractResult(success=False, data=None, 
                                   error=f"JSON parsing error: {str(e)}")
        except Exception as e:
            return JsonExtractResult(success=False, data=None, 
                                   error=f"Unexpected error: {str(e)}")

def get_json(text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
    """
    便捷函数，直接从文本中提取JSON数据
    
    Args:
        text: 包含JSON的文本
        
    Returns:
        解析后的JSON数据，如果解析失败返回None
    """
    try:
        extractor = JsonTextExtractor()
        result = extractor.extract_json(text)
        
        # 处理单个结果
        if isinstance(result, JsonExtractResult):
            return result.data if result.success else None
        
        # 处理多个结果列表
        if isinstance(result, list) and len(result) > 0:
            first_result = result[0]
            return first_result.data if first_result.success else None
            
        return None
        
    except Exception as e:
        print(f"Error in get_json: {str(e)}")
        return None

# 示例使用
if __name__ == "__main__":
    test_cases = [
        ("测试用例1", """这是一个包含JSON的文本：{ "tools": "value" }"""),
        ("测试用例2", """
```json
{
    "tools": ["execute_sql(sql='SELECT NetProfit FROM AStockFinanceDB.LC_IncomeStatementAll WHERE CompanyCode = 1070 AND EndDate LIKE '2021-06-30%' AND IfAdjusted = 2 AND IfMerged = 1')"]
}
```
"""),
        ("测试用例3", """
```json
{
    "tools": ["execute_sql(sql='SELECT COUNT(*) AS StockCount FROM AStockIndustryDB.LC_ExgIndustry WHERE SecondIndustryName = \'专用设备\'')"]
}
```
"""),
        ("测试用例4", """
```json
{
    "title": "论文标题",
    "authors": "作者",
    "publish_time": "发表时间",
    "publish_institution": "发表机构",
    "github_link": "github链接"
}
```
"""),
        ("测试用例5", """
```json
{
    "title": "AGENTIC RETRIEVAL-AUGMENTED GENERATION: A SURVEY ON AGENTIC RAG",
    "authors": "Aditi Singh, Abul Ehtesham, Saket Kumar, Tala Talaei Khoei",
    "publish_time": "15 Jan 2025",
    "publish_institution": "arXiv",
    "github_link": "https://github.com/asinghcsu/AgenticRAG-Survey"
}
```
"""),
        (
            "测试用例6",
            """
            ```json
{
    "tools": ["pubmed_deep_search(page_range=[(1, 3)], results_per_page=10, sleep_time=3, num_processes=8)"]
}
```

            """
        )
    ]
    
    for test_name, test_text in test_cases:
        print(f"\n{'='*50}")
        print(f"运行 {test_name}:")
        print(f"输入文本:\n{test_text}")
        result = get_json(test_text)
        
        if result is not None and isinstance(result, dict):
            # 安全地访问字典键
            keys = list(result.keys())
            if keys:
                key = keys[0]
                value = result[key]
                if isinstance(value, list) and len(value) > 0:
                    print(f"结果: {value[0]}")
                else:
                    print(f"结果: {value}")
            else:
                print(f"结果: {result}")
        else:
            print(f"结果: {result}")

