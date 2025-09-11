"""
工具管理器
文件路径: agent_core/tools.py
功能: 统一管理本地工具与基于 @tool 的注册工具；封装执行逻辑与提示词Schema导出

Author: Your Name
Date: 2025-09-10
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List

from tools_agent.toolkit import ToolRegistry


ToolConfig = Dict[str, Any]
ToolResult = Any


class LocalToolManager:
    """本地工具包装器，兼容同步/异步执行。"""

    def __init__(self, tool_instance: Any, execute_method: str = "execute") -> None:
        self.instance = tool_instance
        self.execute_method_name = execute_method

    async def execute(self, **kwargs: Any) -> Any:
        if not hasattr(self.instance, self.execute_method_name):
            raise AttributeError(
                f"工具实例 {type(self.instance).__name__} 没有方法 {self.execute_method_name}"
            )
        method = getattr(self.instance, self.execute_method_name)
        if asyncio.iscoroutinefunction(method):
            return await method(**kwargs)
        else:
            return method(**kwargs)


class AgentToolManager:
    """统一管理所有工具（本地与注册表）。"""

    def __init__(self) -> None:
        self.local_tools: Dict[str, LocalToolManager] = {}
        self.tool_prompt_config: List[ToolConfig] = []
        self.registry: ToolRegistry = ToolRegistry()

    def register_local_tool(self, name: str, tool_instance: Any, tool_config_for_prompt: ToolConfig) -> None:
        if name in self.local_tools:
            raise ValueError(f"工具 '{name}' 已经注册")
        self.local_tools[name] = LocalToolManager(tool_instance)
        self.tool_prompt_config.append(tool_config_for_prompt)

    def register_tool_function(self, func: Callable[..., Any]) -> None:
        try:
            self.registry.register(func)
        except Exception as e:
            logging.getLogger("agent.tools").error(f"注册工具函数失败: {e}")
            raise

    def get_all_tool_configs_for_prompt(self) -> str:
        schemas = self.registry.get_schemas_json()
        if schemas and schemas != "[]":
            return schemas
        return json.dumps(self.tool_prompt_config, ensure_ascii=False, indent=2)

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        if self.registry.has(tool_name):
            try:
                return self.registry.execute(tool_name, json.dumps(kwargs, ensure_ascii=False))
            except Exception as e:
                logging.getLogger("agent.tools").error(f"执行注册表工具 '{tool_name}' 失败: {e}")
                raise
        if tool_name in self.local_tools:
            try:
                return await self.local_tools[tool_name].execute(**kwargs)
            except Exception as e:
                logging.getLogger("agent.tools").error(f"执行本地工具 '{tool_name}' 失败: {e}")
                raise
        raise ValueError(f"工具 '{tool_name}' 未找到")

    def list_available_tools(self) -> List[str]:
        registry_tools = list(self.registry.get_all_tool_names()) if hasattr(self.registry, "get_all_tool_names") else []
        local_tools = list(self.local_tools.keys())
        return registry_tools + local_tools


