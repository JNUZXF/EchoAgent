# -*- coding: utf-8 -*-
"""
路径管理器
文件路径: agent/utils/path_manager.py
功能: 提供统一的路径管理和动态导入功能，解决路径混乱问题
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
import importlib.util
import logging

logger = logging.getLogger(__name__)

class PathManager:
    """
    【模块化设计】【单一职责原则】统一路径管理器
    
    负责管理项目中的所有路径问题，确保无论从哪个目录运行都能正确导入模块
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式，确保全局只有一个路径管理器实例"""
        if cls._instance is None:
            cls._instance = super(PathManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """【单一职责原则】初始化路径管理器"""
        if self._initialized:
            return
            
        self.project_root = self._find_project_root()
        self.agent_dir = os.path.join(self.project_root, "agent")
        self._setup_python_path()
        self._initialized = True
        
        logger.info(f"路径管理器初始化完成 - 项目根目录: {self.project_root}")
    
    def _find_project_root(self) -> str:
        """
        【分层架构】自动查找项目根目录
        
        通过查找特征文件来确定项目根目录，避免硬编码路径
        """
        # 从当前文件开始向上查找
        current_path = Path(__file__).resolve()
        
        # 查找包含agent目录和README.md的目录作为项目根目录
        for parent in current_path.parents:
            if (parent / "agent").exists() and (parent / "README.md").exists():
                return str(parent)
        
        # 如果找不到，使用当前文件所在目录的父目录的父目录
        return str(current_path.parent.parent.parent)
    
    def _setup_python_path(self):
        """
        【性能设计】设置Python路径，确保能正确导入所有模块
        """
        paths_to_add = [
            self.project_root,
            self.agent_dir,
        ]
        
        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)
                logger.debug(f"添加路径到Python路径: {path}")
    
    def get_agent_path(self, *sub_paths) -> str:
        """
        【扩展性】获取agent目录下的路径
        
        Args:
            *sub_paths: 子路径组件
            
        Returns:
            完整的路径字符串
        """
        return os.path.join(self.agent_dir, *sub_paths)
    
    def get_project_path(self, *sub_paths) -> str:
        """
        【扩展性】获取项目根目录下的路径
        
        Args:
            *sub_paths: 子路径组件
            
        Returns:
            完整的路径字符串
        """
        return os.path.join(self.project_root, *sub_paths)
    
    def ensure_path_exists(self, path: str) -> bool:
        """
        【容错设计】确保路径存在，如果不存在则创建
        
        Args:
            path: 要检查/创建的路径
            
        Returns:
            路径是否存在或创建成功
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"创建路径失败: {path}, 错误: {e}")
            return False
    
    def safe_import(self, module_name: str, package: Optional[str] = None):
        """
        【容错设计】安全导入模块，处理导入错误
        
        Args:
            module_name: 模块名称
            package: 包名称
            
        Returns:
            导入的模块或None
        """
        try:
            if package:
                module = importlib.import_module(module_name, package)
            else:
                module = importlib.import_module(module_name)
            return module
        except ImportError as e:
            logger.warning(f"模块导入失败: {module_name}, 错误: {e}")
            return None
    
    def get_relative_import_path(self, current_file: str, target_module: str) -> str:
        """
        【智能路径解析】根据当前文件位置生成正确的相对导入路径
        
        Args:
            current_file: 当前文件的绝对路径
            target_module: 目标模块路径
            
        Returns:
            正确的相对导入路径
        """
        current_dir = Path(current_file).parent
        agent_dir = Path(self.agent_dir)
        
        # 计算相对于agent目录的路径
        try:
            rel_path = current_dir.relative_to(agent_dir)
            # 根据层级深度生成相对导入前缀
            if rel_path == Path("."):
                return f".{target_module}"
            else:
                level = len(rel_path.parts)
                return f"{'.' * (level + 1)}{target_module}"
        except ValueError:
            # 如果当前文件不在agent目录下，使用绝对导入
            return f"agent.{target_module}"

# 全局路径管理器实例
path_manager = PathManager()

def setup_agent_imports():
    """
    【配置外置】便捷函数：设置智能体导入路径
    
    在任何需要导入agent模块的文件开头调用此函数
    """
    path_manager._setup_python_path()

def get_agent_path(*sub_paths) -> str:
    """【便捷接口】获取agent目录下的路径"""
    return path_manager.get_agent_path(*sub_paths)

def get_project_path(*sub_paths) -> str:
    """【便捷接口】获取项目根目录下的路径"""
    return path_manager.get_project_path(*sub_paths)

def safe_import(module_name: str, package: Optional[str] = None):
    """【便捷接口】安全导入模块"""
    return path_manager.safe_import(module_name, package)

# 自动初始化路径管理
setup_agent_imports() 