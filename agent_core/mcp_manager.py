"""
MCP工具管理器
文件路径: agent_core/mcp_manager.py
功能: 管理MCP服务器连接、工具注册和执行，提供异步接入和优雅关闭

【模块化设计】【异步处理】【分层架构】
这个模块实现了MCP(Model Context Protocol)的客户端管理功能：
- 异步连接多个MCP服务器
- 统一管理MCP工具注册
- 提供工具执行接口
- 支持优雅关闭和资源清理

Author: Your Name
Date: 2025-09-14
"""

import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPToolDefinition(TypedDict):
    """MCP工具定义类型"""
    name: str
    description: str
    input_schema: dict


class MCPManager:
    """
    【单一职责原则】【依赖倒置】MCP服务器连接和工具管理器
    
    负责管理与MCP服务器的连接、工具注册和执行。
    支持异步初始化和优雅关闭。
    """
    
    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        初始化MCP管理器
        
        Args:
            config_path: MCP服务器配置文件路径，默认为server_config.json
        """
        self.logger = logging.getLogger("agent.mcp")
        self.config_path = config_path or "server_config.json"
        
        # 连接管理
        self.sessions: List[ClientSession] = []
        self.exit_stack = AsyncExitStack()
        
        # 工具管理
        self.available_tools: List[MCPToolDefinition] = []
        self.tool_to_session: Dict[str, ClientSession] = {}
        self.server_status: Dict[str, bool] = {}
        
        self.logger.info("MCP管理器初始化完成")
    
    async def connect_to_server(self, server_name: str, server_config: dict) -> bool:
        """
        【错误处理】连接单个MCP服务器
        
        Args:
            server_name: 服务器名称
            server_config: 服务器配置
            
        Returns:
            连接是否成功
        """
        try:
            self.logger.info(f"正在连接MCP服务器: {server_name}")
            print(f"🔌 尝试连接MCP服务器: {server_name}")
            print(f"   命令: {server_config.get('command')} {' '.join(server_config.get('args', []))}")
            
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
            await session.initialize()
            self.sessions.append(session)
            
            # 获取服务器提供的工具列表
            response = await session.list_tools()
            tools = response.tools
            
            tool_names = [t.name for t in tools]
            self.logger.info(f"成功连接到 {server_name}，可用工具: {tool_names}")
            print(f"✅ 成功连接到 {server_name}，获得工具: {tool_names}")
            
            # 注册工具到管理器
            for tool in tools:
                self.tool_to_session[tool.name] = session
                self.available_tools.append({
                    "name": tool.name,
                    "description": tool.description or f"MCP工具: {tool.name}",
                    "input_schema": tool.inputSchema or {}
                })
            
            self.server_status[server_name] = True
            return True
            
        except Exception as e:
            self.logger.error(f"连接MCP服务器 {server_name} 失败: {e}")
            print(f"❌ 连接MCP服务器 {server_name} 失败: {e}")
            print(f"   可能原因: 命令不存在或依赖未安装")
            self.server_status[server_name] = False
            return False
    
    async def connect_to_servers(self) -> Dict[str, bool]:
        """
        【配置外置】连接所有配置的MCP服务器
        
        Returns:
            各服务器的连接状态字典
        """
        try:
            # 查找配置文件
            config_file = Path(self.config_path)
            if not config_file.exists():
                # 尝试在当前目录和mcp_project目录查找
                for search_path in [".", "mcp_project"]:
                    alt_config = Path(search_path) / "server_config.json"
                    if alt_config.exists():
                        config_file = alt_config
                        break
            
            if not config_file.exists():
                self.logger.warning(f"MCP配置文件不存在: {self.config_path}")
                return {}
            
            self.logger.info(f"加载MCP配置文件: {config_file}")
            
            with open(config_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            if not servers:
                self.logger.warning("配置文件中未找到MCP服务器配置")
                return {}
            
            # 并发连接所有服务器
            connection_tasks = []
            for server_name, server_config in servers.items():
                task = self.connect_to_server(server_name, server_config)
                connection_tasks.append((server_name, task))
            
            # 等待所有连接完成
            results = {}
            for server_name, task in connection_tasks:
                try:
                    success = await task
                    results[server_name] = success
                except Exception as e:
                    self.logger.error(f"连接服务器 {server_name} 时发生异常: {e}")
                    results[server_name] = False
            
            # 汇总连接结果
            successful_connections = sum(1 for success in results.values() if success)
            total_tools = len(self.available_tools)
            
            self.logger.info(
                f"MCP服务器连接完成: {successful_connections}/{len(servers)} 成功, "
                f"共获得 {total_tools} 个工具"
            )
            
            return results
            
        except Exception as e:
            self.logger.exception(f"连接MCP服务器时发生错误: {e}")
            return {}
    
    async def execute_mcp_tool(self, tool_name: str, arguments: dict) -> Any:
        """
        【异常处理】执行MCP工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
            
        Raises:
            ValueError: 工具不存在
            Exception: 工具执行失败
        """
        if tool_name not in self.tool_to_session:
            raise ValueError(f"MCP工具 '{tool_name}' 不存在")
        
        session = self.tool_to_session[tool_name]
        
        try:
            self.logger.debug(f"执行MCP工具: {tool_name}, 参数: {arguments}")
            
            result = await session.call_tool(tool_name, arguments=arguments)
            
            # 汇总工具返回的所有文本内容
            content_text = ""
            if hasattr(result, 'content') and result.content:
                for content in result.content:
                    if hasattr(content, 'text'):
                        content_text += content.text
            
            self.logger.debug(f"MCP工具 {tool_name} 执行完成，结果长度: {len(content_text)}")
            
            return content_text if content_text else str(result)
            
        except Exception as e:
            self.logger.error(f"执行MCP工具 {tool_name} 失败: {e}")
            raise Exception(f"MCP工具执行失败: {str(e)}")
    
    def list_available_tools(self) -> List[str]:
        """
        获取所有可用的MCP工具名称列表
        
        Returns:
            工具名称列表
        """
        return [tool["name"] for tool in self.available_tools]
    
    def get_tool_schemas_for_prompt(self) -> List[dict]:
        """
        【接口设计】获取工具Schema，用于提示词生成
        
        Returns:
            工具Schema列表，格式适合嵌入提示词
        """
        schemas = []
        for tool in self.available_tools:
            schema = {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("input_schema", {})
            }
            schemas.append(schema)
        return schemas
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        获取连接状态信息
        
        Returns:
            包含连接状态的字典
        """
        return {
            "servers": dict(self.server_status),
            "total_tools": len(self.available_tools),
            "active_sessions": len(self.sessions),
            "available_tools": self.list_available_tools()
        }
    
    async def cleanup(self) -> None:
        """
        【资源管理】优雅关闭所有MCP连接
        """
        try:
            self.logger.info("正在关闭MCP连接...")
            await self.exit_stack.aclose()
            self.sessions.clear()
            self.available_tools.clear()
            self.tool_to_session.clear()
            self.logger.info("MCP连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭MCP连接时发生错误: {e}")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        if self.sessions:
            self.logger.warning("MCP管理器被销毁时仍有活跃连接，请调用cleanup()方法")
