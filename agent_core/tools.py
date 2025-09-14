"""
工具管理器
文件路径: agent_core/tools.py
功能: 统一管理本地工具、基于 @tool 的注册工具以及MCP工具；封装执行逻辑与提示词Schema导出

Author: Your Name
Date: 2025-09-14
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from tools_agent.toolkit import ToolRegistry

# 延迟导入MCP管理器，避免循环依赖
try:
    from .mcp_manager import MCPManager
except ImportError:
    MCPManager = None


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
    """【单一职责原则】【依赖倒置】统一管理所有工具（本地、注册表与MCP）。"""

    def __init__(self) -> None:
        self.local_tools: Dict[str, LocalToolManager] = {}
        self.tool_prompt_config: List[ToolConfig] = []
        self.registry: ToolRegistry = ToolRegistry()
        self.mcp_manager: Optional[MCPManager] = None
        self.logger = logging.getLogger("agent.tools")

    def register_local_tool(self, name: str, tool_instance: Any, tool_config_for_prompt: ToolConfig) -> None:
        if name in self.local_tools:
            raise ValueError(f"工具 '{name}' 已经注册")
        self.local_tools[name] = LocalToolManager(tool_instance)
        self.tool_prompt_config.append(tool_config_for_prompt)

    def register_tool_function(self, func: Callable[..., Any]) -> None:
        try:
            self.registry.register(func)
        except Exception as e:
            self.logger.error(f"注册工具函数失败: {e}")
            raise

    async def initialize_mcp_tools(self, config_path: Optional[str] = None) -> Dict[str, bool]:
        """
        【异步处理】【配置外置】初始化MCP工具连接
        
        Args:
            config_path: MCP配置文件路径
            
        Returns:
            各服务器的连接状态
        """
        if MCPManager is None:
            self.logger.warning("MCP管理器不可用，跳过MCP工具初始化")
            return {}
        
        try:
            self.mcp_manager = MCPManager(config_path)
            connection_results = await self.mcp_manager.connect_to_servers()
            
            # 记录连接结果
            successful = sum(1 for success in connection_results.values() if success)
            total = len(connection_results)
            available_tools = self.mcp_manager.list_available_tools()
            
            self.logger.info(
                f"MCP工具初始化完成: {successful}/{total} 服务器连接成功, "
                f"可用工具: {available_tools}"
            )
            
            return connection_results
            
        except Exception as e:
            self.logger.exception(f"初始化MCP工具失败: {e}")
            return {}

    def is_mcp_tool(self, tool_name: str) -> bool:
        """检查是否为MCP工具"""
        return (self.mcp_manager is not None and 
                tool_name in self.mcp_manager.list_available_tools())

    def get_all_tool_configs_for_prompt(self) -> str:
        """【接口设计】获取所有工具的配置信息，用于生成提示词"""
        all_schemas = []
        
        # 1. 获取注册表工具的Schema
        registry_schemas = self.registry.get_schemas_json()
        if registry_schemas and registry_schemas != "[]":
            try:
                registry_data = json.loads(registry_schemas)
                if isinstance(registry_data, list):
                    all_schemas.extend(registry_data)
            except json.JSONDecodeError:
                pass
        
        # 2. 添加本地工具配置
        all_schemas.extend(self.tool_prompt_config)
        
        # 3. 添加MCP工具配置
        if self.mcp_manager:
            mcp_schemas = self.mcp_manager.get_tool_schemas_for_prompt()
            all_schemas.extend(mcp_schemas)
        
        return json.dumps(all_schemas, ensure_ascii=False, indent=2)

    def get_tool_docs_for_prompt(self) -> str:
        """
        返回聚合后的工具文档纯文本（来自 @tool 函数的 docstring），用于系统提示词。
        """
        try:
            docs_text = self.registry.get_tool_docs_text() if hasattr(self.registry, "get_tool_docs_text") else ""
        except Exception:
            docs_text = ""

        # 追加本地工具与 MCP 工具的说明（如有需要，可在未来扩展）
        # 当前仅聚焦 @tool 工具，保持最小变更面
        return docs_text

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """【单一职责原则】【异常处理】统一执行各类工具"""
        
        # 1. 尝试执行注册表工具
        if self.registry.has(tool_name):
            try:
                return self.registry.execute(tool_name, json.dumps(kwargs, ensure_ascii=False))
            except Exception as e:
                self.logger.error(f"执行注册表工具 '{tool_name}' 失败: {e}")
                raise
        
        # 2. 尝试执行本地工具
        if tool_name in self.local_tools:
            try:
                return await self.local_tools[tool_name].execute(**kwargs)
            except Exception as e:
                self.logger.error(f"执行本地工具 '{tool_name}' 失败: {e}")
                raise
        
        # 3. 尝试执行MCP工具
        if self.is_mcp_tool(tool_name):
            try:
                return await self.mcp_manager.execute_mcp_tool(tool_name, kwargs)
            except Exception as e:
                self.logger.error(f"执行MCP工具 '{tool_name}' 失败: {e}")
                raise
        
        raise ValueError(f"工具 '{tool_name}' 未找到")

    def list_available_tools(self) -> List[str]:
        """【接口统一】获取所有可用工具的名称列表"""
        registry_tools = list(self.registry.get_all_tool_names()) if hasattr(self.registry, "get_all_tool_names") else []
        local_tools = list(self.local_tools.keys())
        mcp_tools = self.mcp_manager.list_available_tools() if self.mcp_manager else []
        return registry_tools + local_tools + mcp_tools

    def get_mcp_connection_status(self) -> Dict[str, Any]:
        """获取MCP连接状态信息"""
        if self.mcp_manager:
            return self.mcp_manager.get_connection_status()
        return {"servers": {}, "total_tools": 0, "active_sessions": 0, "available_tools": []}

    async def cleanup_mcp_connections(self) -> None:
        """【资源管理】清理MCP连接"""
        if self.mcp_manager:
            await self.mcp_manager.cleanup()
            self.mcp_manager = None
            self.logger.info("MCP连接已清理")


