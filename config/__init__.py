"""
配置管理模块
文件路径: config/__init__.py
功能: 配置模块入口文件，便于导入配置类

Author: Your Name
Date: 2024-01-01
"""

from .agent_config import AgentSettings, create_agent_config

__all__ = ['AgentSettings', 'create_agent_config']
