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


class CodeRunnerArgs(BaseModel):
    """CodeRunner 工具的参数模型"""
    code: Optional[str] = Field(default=None, description="要执行的 Python 代码字符串; 若为空, 将由上文响应中提取")
    timeout: float = Field(default=60.0, description="执行超时时间(秒)")
    use_persistent: bool = Field(default=True, description="是否启用持久化上下文")


@tool
def CodeRunner(args: CodeRunnerArgs):
    """执行 Python 代码, 返回格式化后的结果摘要与上下文信息。"""
    executor = CodeExecutor(timeout=args.timeout, enable_persistence=True)
    result = executor.execute(code=args.code or "", use_persistent=args.use_persistent)
    return result


class ContinueAnalyzeArgs(BaseModel):
    """继续分析工具参数模型(占位, 无入参)"""
    pass


@tool
def continue_analyze(args: ContinueAnalyzeArgs):
    """当需要继续进行文本分析时调用, 无需参数。"""
    tool_impl = ContinueAnalyze()
    return tool_impl.execute()


