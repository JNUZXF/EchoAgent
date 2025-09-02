# -*- coding: utf-8 -*-
"""
FinAgent 工具模块
文件路径: agent/utils/__init__.py
功能: 提供各种工具函数和类的统一导入接口
"""

# 【架构设计原则】避免循环导入，使用延迟导入策略
from .code_runner import CodeExecutor
from .bocha_search import BochaSearch
from .embedding_doubao import VectorDatabase, VectorSearcher

# 【性能优化】延迟导入KB搜索工具，避免循环依赖和启动耗时
def get_kb_search():
    """延迟导入KB搜索工具"""
    from .agent_tool_kb_search import KBSearch
    return KBSearch

__all__ = [
    "CodeExecutor",
    "BochaSearch", 
    "VectorDatabase",
    "VectorSearcher",
    "get_kb_search",
    "get_embedding_doubao",
] 