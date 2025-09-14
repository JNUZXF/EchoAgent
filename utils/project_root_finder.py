# -*- coding: utf-8 -*-
"""
项目根目录查找器
文件路径: utils/project_root_finder.py
功能: 提供统一的、智能的项目根目录查找机制，支持多种部署环境和项目结构
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProjectRootConfig:
    """
    【配置外置】项目根目录查找配置
    """
    # 环境变量名称
    env_var: str = "AGENT_PROJECT_ROOT"
    
    # 特征文件列表（按优先级排序）
    signature_files: List[str] = None
    
    # 项目标识文件
    project_markers: List[str] = None
    
    # 最大向上查找层数
    max_search_depth: int = 10
    
    # 是否启用缓存
    enable_cache: bool = True
    
    def __post_init__(self):
        if self.signature_files is None:
            self.signature_files = [
                "agent_frame.py",     # 项目主文件（最高优先级）
                "pyproject.toml",     # Python项目配置
                "setup.py",           # Python包配置
                "requirements.txt",   # Python依赖
                "package.json",       # Node.js项目
                "Cargo.toml",         # Rust项目
                ".git",               # Git仓库根目录
                "README.md",          # 文档文件（较低优先级）
                "README.rst",         # RST文档
            ]
        
        if self.project_markers is None:
            self.project_markers = [
                ".project-root",      # 项目根目录标识文件
                ".agent-root",        # Agent项目根目录标识
            ]

class ProjectRootFinder:
    """
    【单一职责原则】【模块化设计】统一项目根目录查找器
    
    支持多种查找策略的组合使用：
    1. 环境变量指定
    2. 项目标识文件
    3. 特征文件组合
    4. 智能推断
    """
    
    _instance: Optional["ProjectRootFinder"] = None
    _cached_root: Optional[Path] = None
    
    def __new__(cls, config: Optional[ProjectRootConfig] = None):
        """【单例模式】确保全局统一的根目录管理"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[ProjectRootConfig] = None):
        if hasattr(self, "_initialized") and self._initialized:
            return
            
        self.config = config or ProjectRootConfig()
        self._initialized = True
        
        logger.debug(f"项目根目录查找器初始化完成 - 配置: {self.config}")
    
    def find_project_root(self, start_path: Optional[Path] = None, force_refresh: bool = False) -> Path:
        """
        【分层架构】查找项目根目录
        
        Args:
            start_path: 开始查找的路径，默认为当前文件所在目录
            force_refresh: 是否强制刷新缓存
            
        Returns:
            项目根目录路径
        """
        # 使用缓存（如果启用且存在）
        if self.config.enable_cache and self._cached_root and not force_refresh:
            logger.debug(f"使用缓存的项目根目录: {self._cached_root}")
            return self._cached_root
        
        if start_path is None:
            start_path = Path(__file__).resolve()
        else:
            start_path = Path(start_path).resolve()
        
        logger.debug(f"开始查找项目根目录，起始路径: {start_path}")
        
        # 策略1: 环境变量指定
        root = self._find_by_env_var()
        if root:
            logger.info(f"通过环境变量 {self.config.env_var} 找到项目根目录: {root}")
            return self._cache_and_return(root)
        
        # 策略2: 项目标识文件
        root = self._find_by_project_markers(start_path)
        if root:
            logger.info(f"通过项目标识文件找到项目根目录: {root}")
            return self._cache_and_return(root)
        
        # 策略3: 特征文件组合
        root = self._find_by_signature_files(start_path)
        if root:
            logger.info(f"通过特征文件找到项目根目录: {root}")
            return self._cache_and_return(root)
        
        # 策略4: 智能推断兜底
        root = self._fallback_inference(start_path)
        logger.warning(f"使用兜底策略确定项目根目录: {root}")
        return self._cache_and_return(root)
    
    def _find_by_env_var(self) -> Optional[Path]:
        """【配置外置】通过环境变量查找"""
        env_path = os.environ.get(self.config.env_var)
        if env_path:
            path = Path(env_path).resolve()
            if path.exists() and path.is_dir():
                return path
            else:
                logger.warning(f"环境变量 {self.config.env_var} 指定的路径不存在: {env_path}")
        return None
    
    def _find_by_project_markers(self, start_path: Path) -> Optional[Path]:
        """【扩展性】通过项目标识文件查找"""
        current = start_path if start_path.is_dir() else start_path.parent
        depth = 0
        
        while current != current.parent and depth < self.config.max_search_depth:
            for marker in self.config.project_markers:
                marker_path = current / marker
                if marker_path.exists():
                    # 如果是文件，读取内容作为根目录（相对路径）
                    if marker_path.is_file():
                        try:
                            content = marker_path.read_text(encoding='utf-8').strip()
                            # 只处理非空且非注释的第一行
                            lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
                            if lines:
                                first_line = lines[0]
                                # 支持相对路径
                                if first_line.startswith('.'):
                                    return (current / first_line).resolve()
                                elif first_line.startswith('/') or (len(first_line) > 1 and first_line[1] == ':'):
                                    # 绝对路径
                                    return Path(first_line).resolve()
                                # 如果不是路径格式，当前目录就是根目录
                        except Exception as e:
                            logger.warning(f"读取项目标识文件失败 {marker_path}: {e}")
                    
                    # 标识文件存在，当前目录就是根目录
                    return current
            
            current = current.parent
            depth += 1
        
        return None
    
    def _find_by_signature_files(self, start_path: Path) -> Optional[Path]:
        """【性能设计】通过特征文件组合查找"""
        current = start_path if start_path.is_dir() else start_path.parent
        depth = 0
        
        # 为不同类型的项目定义组合策略
        project_patterns = [
            # Python Agent 项目
            {"files": ["agent_frame.py", "requirements.txt"], "weight": 100},
            {"files": ["agent_frame.py"], "weight": 90},
            
            # Python 项目
            {"files": ["pyproject.toml", "README.md"], "weight": 80},
            {"files": ["setup.py", "requirements.txt"], "weight": 75},
            {"files": ["requirements.txt", "README.md"], "weight": 70},
            
            # 通用项目
            {"files": [".git", "README.md"], "weight": 60},
            {"files": ["README.md"], "weight": 30},  # 最低优先级
        ]
        
        best_match = None
        best_weight = 0
        
        while current != current.parent and depth < self.config.max_search_depth:
            for pattern in project_patterns:
                matches = sum(1 for f in pattern["files"] if (current / f).exists())
                if matches == len(pattern["files"]) and pattern["weight"] > best_weight:
                    best_match = current
                    best_weight = pattern["weight"]
                    # 如果找到高权重匹配，可以提前返回
                    if best_weight >= 90:
                        return best_match
            
            current = current.parent
            depth += 1
        
        return best_match
    
    def _fallback_inference(self, start_path: Path) -> Path:
        """【容错设计】兜底推断策略"""
        # 如果是在项目内的文件，尝试向上找到合理的根目录
        current = start_path if start_path.is_dir() else start_path.parent
        
        # 查找包含多个子目录的目录作为可能的根目录
        while current != current.parent:
            try:
                subdirs = [p for p in current.iterdir() if p.is_dir() and not p.name.startswith('.')]
                # 如果包含常见的项目目录结构，认为是根目录
                common_dirs = {"src", "lib", "utils", "config", "docs", "tests", "scripts"}
                if len(subdirs) >= 3 and any(d.name in common_dirs for d in subdirs):
                    return current
            except PermissionError:
                pass
            
            current = current.parent
        
        # 最终兜底：使用起始路径的父目录
        fallback = start_path.parent if start_path.is_file() else start_path
        return fallback.resolve()
    
    def _cache_and_return(self, root: Path) -> Path:
        """【性能设计】缓存并返回结果"""
        if self.config.enable_cache:
            self._cached_root = root
        return root
    
    def clear_cache(self):
        """【扩展性】清空缓存，强制重新查找"""
        self._cached_root = None
        logger.debug("项目根目录缓存已清空")
    
    def validate_project_root(self, root: Path) -> bool:
        """
        【测试策略】验证项目根目录的有效性
        
        Args:
            root: 待验证的根目录路径
            
        Returns:
            是否为有效的项目根目录
        """
        if not root.exists() or not root.is_dir():
            return False
        
        # 检查是否有基本的项目结构
        indicators = 0
        
        # Python项目指示器
        if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
            indicators += 2
        
        # 代码目录
        for code_dir in ["src", "lib", "utils", "agent_core", "tools_agent"]:
            if (root / code_dir).exists():
                indicators += 1
        
        # 文档
        for doc in ["README.md", "README.rst", "docs"]:
            if (root / doc).exists():
                indicators += 1
        
        # 配置文件
        for config in [".git", ".gitignore", "config"]:
            if (root / config).exists():
                indicators += 1
        
        return indicators >= 2
    
    def get_project_structure_info(self, root: Optional[Path] = None) -> Dict:
        """
        【监控原则】获取项目结构信息，用于调试和监控
        
        Returns:
            包含项目结构信息的字典
        """
        if root is None:
            root = self.find_project_root()
        
        info = {
            "root": str(root),
            "exists": root.exists(),
            "is_valid": self.validate_project_root(root),
            "signature_files": {},
            "subdirectories": [],
            "detection_method": "unknown"
        }
        
        # 检查特征文件
        for sig_file in self.config.signature_files:
            sig_path = root / sig_file
            info["signature_files"][sig_file] = sig_path.exists()
        
        # 获取子目录
        try:
            info["subdirectories"] = [
                p.name for p in root.iterdir() 
                if p.is_dir() and not p.name.startswith('.')
            ]
        except (PermissionError, FileNotFoundError):
            pass
        
        return info


# 全局实例和便捷函数
_finder = ProjectRootFinder()

def get_project_root(start_path: Optional[Path] = None, force_refresh: bool = False) -> Path:
    """
    【接口简化】获取项目根目录的便捷函数
    
    Args:
        start_path: 开始查找的路径
        force_refresh: 是否强制刷新缓存
        
    Returns:
        项目根目录路径
    """
    return _finder.find_project_root(start_path, force_refresh)

def create_project_marker(root_path: Path, marker_type: str = ".project-root") -> Path:
    """
    【扩展性】在指定目录创建项目标识文件
    
    Args:
        root_path: 项目根目录
        marker_type: 标识文件类型
        
    Returns:
        创建的标识文件路径
    """
    marker_path = root_path / marker_type
    marker_path.touch()
    logger.info(f"已创建项目标识文件: {marker_path}")
    return marker_path

def configure_project_root(env_var_value: str):
    """
    【配置管理】通过环境变量配置项目根目录
    
    Args:
        env_var_value: 项目根目录路径
    """
    config = ProjectRootConfig()
    os.environ[config.env_var] = str(Path(env_var_value).resolve())
    _finder.clear_cache()  # 清空缓存以应用新配置
    logger.info(f"已通过环境变量配置项目根目录: {env_var_value}")
