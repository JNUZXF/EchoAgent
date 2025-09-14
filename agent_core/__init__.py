"""
Agent核心模块包
文件路径: agent_core/__init__.py
功能: 暴露核心可复用类，便于主框架按需引入（模型、状态、工具、提示词）

Author: Your Name
Date: 2025-09-10
"""

from .models import ToolEventModel, IntentionResultModel, TeamContextModel
from .state_manager import AgentStateManager
from .tools import LocalToolManager, AgentToolManager
from .prompts import AgentPromptManager

# MCP管理器可选导入
try:
    from .mcp_manager import MCPManager
    _mcp_available = True
except ImportError:
    MCPManager = None
    _mcp_available = False

__all__ = [
    "ToolEventModel",
    "IntentionResultModel",
    "TeamContextModel",
    "AgentStateManager",
    "LocalToolManager",
    "AgentToolManager",
    "AgentPromptManager",
]

if _mcp_available:
    __all__.append("MCPManager")


