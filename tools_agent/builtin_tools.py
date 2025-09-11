"""
内置工具定义
文件路径: tools_agent/builtin_tools.py
功能: 使用 @tool 装饰器将现有本地工具(CodeExecutor, ContinueAnalyze)以 Pydantic Schema 方式暴露, 便于自动生成工具参数 Schema 与统一执行。
"""

from typing import Optional
from pydantic import BaseModel, Field

from utils.code_runner import CodeExecutor
from utils.agent_tool_continue_analyze import ContinueAnalyze
from .toolkit import tool

# 【持久化上下文】全局CodeExecutor实例，确保跨工具调用的持久化
_global_code_executor = None

def get_global_code_executor() -> CodeExecutor:
    """获取全局CodeExecutor实例，确保代码执行的持久化上下文"""
    global _global_code_executor
    if _global_code_executor is None:
        _global_code_executor = CodeExecutor(enable_persistence=True)
    return _global_code_executor


class CodeRunnerArgs(BaseModel):
    """CodeRunner 工具的参数模型"""
    code: Optional[str] = Field(default=None, description="空字符串，代码已经从前文提取")
    # timeout: float = Field(default=60.0, description="执行超时时间(秒)")
    use_persistent: bool = Field(default=True, description="是否启用持久化上下文")


@tool
def CodeRunner(args: CodeRunnerArgs):
    """
    执行 Python 代码。
    示例用法：
    Assistant：接下来要运行代码
    你的输出：
    {{"tools": ["CodeRunner(code="")"]}}
    """
    # 【持久化上下文】使用全局实例确保跨调用持久化
    executor = get_global_code_executor()
    # 更新超时设置（如果需要）
    if hasattr(args, 'timeout'):
        executor.timeout = args.timeout
    result = executor.execute(code=args.code or "", use_persistent=args.use_persistent)
    
    # 【上下文分离】为智能体对话准备简化的结果摘要
    agent_result = {
        'success': result.get('success', False),
        'execution_time': result.get('execution_time', 0),
        'stdout': result.get('stdout', ''),
        'error': result.get('error', None)
    }
    
    # 如果有执行结果，添加简化描述
    if result.get('result') is not None:
        result_value = result.get('result')
        result_type = type(result_value).__name__
        
        # 对不同类型的结果提供简化描述
        if hasattr(result_value, 'shape') and hasattr(result_value, 'dtypes'):
            # pandas DataFrame/Series
            agent_result['result_summary'] = f"{result_type} (shape: {result_value.shape})"
        elif isinstance(result_value, (list, tuple, dict)):
            # 集合类型
            agent_result['result_summary'] = f"{result_type} (length: {len(result_value)})"
        elif isinstance(result_value, (int, float, str, bool)):
            # 基本类型，直接显示值（如果不太长）
            str_value = str(result_value)
            if len(str_value) <= 100:
                agent_result['result_summary'] = f"{result_type}: {str_value}"
            else:
                agent_result['result_summary'] = f"{result_type} (length: {len(str_value)})"
        else:
            # 其他类型
            agent_result['result_summary'] = f"{result_type} object"
    
    # 添加持久化变量数量信息（不包含具体内容）
    if result.get('context_variables'):
        var_count = len(result['context_variables'])
        agent_result['persistent_variables_count'] = var_count
    
    return agent_result


class ResetCodeContextArgs(BaseModel):
    """重置代码执行上下文的参数模型"""
    confirm: bool = Field(default=True, description="确认重置操作")


@tool
def ResetCodeContext(args: ResetCodeContextArgs):
    """重置代码执行的持久化上下文，清理所有已定义的变量和导入。谨慎使用，这会清除所有之前代码执行中定义的变量。"""
    if not args.confirm:
        return {
            'success': False,
            'message': '重置操作被取消，需要确认参数为True'
        }
    
    # 【持久化上下文】重置全局CodeExecutor实例的上下文
    executor = get_global_code_executor()
    
    # 获取重置前的变量数量
    old_context_vars = executor.get_context_variables()
    old_var_count = len(old_context_vars) if old_context_vars else 0
    
    # 执行重置
    executor.reset_context()
    
    return {
        'success': True,
        'message': f'代码执行上下文已重置',
        'cleared_variables_count': old_var_count,
        'status': '所有持久化变量和导入已清除，下次代码执行将从全新环境开始'
    }


class ViewCodeContextArgs(BaseModel):
    """查看代码执行上下文的参数模型"""
    show_details: bool = Field(default=False, description="是否显示变量的详细信息（类型和简要内容）")


@tool
def ViewCodeContext(args: ViewCodeContextArgs):
    """查看当前代码执行上下文中的持久化变量信息，帮助了解当前可用的变量。"""
    # 【持久化上下文】获取全局CodeExecutor实例的上下文信息
    executor = get_global_code_executor()
    context_vars = executor.get_context_variables()
    
    if not context_vars:
        return {
            'success': True,
            'message': '当前代码执行上下文为空',
            'variables_count': 0,
            'variables': {}
        }
    
    variables_info = {}
    
    for var_name, var_value in context_vars.items():
        var_type = type(var_value).__name__
        
        if args.show_details:
            # 提供变量的详细信息
            if hasattr(var_value, 'shape') and hasattr(var_value, 'dtypes'):
                # pandas DataFrame/Series
                variables_info[var_name] = {
                    'type': var_type,
                    'info': f'shape: {var_value.shape}',
                    'summary': str(var_value)[:200] + ('...' if len(str(var_value)) > 200 else '')
                }
            elif isinstance(var_value, (list, tuple, dict)):
                # 集合类型
                variables_info[var_name] = {
                    'type': var_type,
                    'info': f'length: {len(var_value)}',
                    'summary': str(var_value)[:200] + ('...' if len(str(var_value)) > 200 else '')
                }
            elif isinstance(var_value, (int, float, str, bool)):
                # 基本类型
                str_value = str(var_value)
                variables_info[var_name] = {
                    'type': var_type,
                    'info': f'value: {str_value[:100] + ("..." if len(str_value) > 100 else "")}'
                }
            else:
                # 其他类型
                variables_info[var_name] = {
                    'type': var_type,
                    'info': 'complex object'
                }
        else:
            # 只显示类型信息
            variables_info[var_name] = var_type
    
    return {
        'success': True,
        'message': f'当前代码执行上下文包含 {len(context_vars)} 个持久化变量',
        'variables_count': len(context_vars),
        'variables': variables_info
    }


class ContinueAnalyzeArgs(BaseModel):
    """继续分析工具参数模型(占位, 无入参)"""
    pass


@tool
def continue_analyze(args: ContinueAnalyzeArgs):
    """当需要继续进行文本分析时调用, 无需参数。"""
    tool_impl = ContinueAnalyze()
    return tool_impl.execute()


