# -*- coding: utf-8 -*-
"""
文件管理器
文件路径: utils/file_manager.py
功能: 统一管理项目中的所有文件与路径，提供生产级会话目录创建、日志与持久化落盘路径。

设计目标:
- 只需调用一次Agent框架的会话接口, 即自动在固定位置创建: files/{user_id}/{agent_name}/{session_id}/
- 统一提供对会话内: 日志(logs/)、会话记录(conversations/)、产物(artifacts/)、上传(uploads/)、输出(outputs/)、临时(temp/) 的路径
- 支持环境变量配置根目录: AGENT_FILES_ROOT (默认: 项目根目录/files)
- 提供latest快捷指针(文本记录最新session_id)方便运维查找
"""

import os
import json
import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

def _get_project_root() -> Path:
    """基于当前文件向上查找项目根目录(包含README.md)"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "README.md").exists():
            return parent
    return current.parent.parent

def _sanitize_for_fs(name: str) -> str:
    """将用户ID等字符串转为文件系统安全的名称"""
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name.strip())

@dataclass
class SessionInfo:
    """会话信息载体"""
    user_id: str
    agent_name: str
    session_id: str
    root_dir: Path
    # 标记是否为workspace模式：此时root_dir指向 workspaces/{user}/{workspace}
    # 而非 files 根目录
    is_workspace: bool = False

    @property
    def session_dir(self) -> Path:
        if self.is_workspace:
            # workspaces/{user}/{workspace}/{agent}/{session_id}
            return self.root_dir / _sanitize_for_fs(self.agent_name) / self.session_id
        # files/{user}/{agent}/{session_id}
        return self.root_dir / _sanitize_for_fs(self.user_id) / _sanitize_for_fs(self.agent_name) / self.session_id

    @property
    def logs_dir(self) -> Path:
        return self.session_dir / "logs"

    @property
    def conversations_dir(self) -> Path:
        return self.session_dir / "conversations"

    @property
    def artifacts_dir(self) -> Path:
        return self.session_dir / "artifacts"

    @property
    def uploads_dir(self) -> Path:
        return self.session_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.session_dir / "outputs"

    @property
    def temp_dir(self) -> Path:
        return self.session_dir / "temp"

    @property
    def images_dir(self) -> Path:
        return self.session_dir / "images"

class FileManager:
    """
    【模块化设计】【单一职责原则】统一文件与路径管理器

    - 通过create_session()创建一次聊天会话目录
    - 暴露会话下标准化文件路径, 供Agent各组件统一使用
    - 提供生产级日志落盘, 每个会话有独立日志文件, 同时在控制台输出
    """

    _instance: Optional["FileManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.project_root: Path = _get_project_root()
        self.workspaces_root: Path = self.project_root / "workspaces"

        self._session_loggers: Dict[str, logging.Logger] = {}
        # 日志可配置参数
        self.log_max_bytes: int = int(os.environ.get("AGENT_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
        self.log_backup_count: int = int(os.environ.get("AGENT_LOG_BACKUP", "5"))
        self.console_level: int = getattr(logging, os.environ.get("AGENT_LOG_CONSOLE_LEVEL", "INFO").upper(), logging.INFO)
        self.file_level: int = getattr(logging, os.environ.get("AGENT_LOG_FILE_LEVEL", "DEBUG").upper(), logging.DEBUG)
        self._initialized = True

    # ======== 会话与路径 ========
    def create_session(self, user_id: str, agent_name: str, session_id: Optional[str] = None, workspace: Optional[str] = None) -> SessionInfo:
        """
        创建会话目录结构: files/{user_id}/{agent_name}/{session_id}/
        子目录: logs/, conversations/, artifacts/, uploads/, outputs/, temp/
        并写入最新会话指针 latest.json
        """
        if workspace:
            # 根目录只到 workspace，避免后续再拼 user/agent 重复
            default_root = self.workspaces_root / user_id / workspace
        else:   
            default_root = self.project_root / "files"
        
        env_root = os.environ.get("AGENT_FILES_ROOT", str(default_root))
        self.files_root: Path = Path(env_root).resolve()
        self.files_root.mkdir(parents=True, exist_ok=True)
        
        safe_user = _sanitize_for_fs(user_id)
        safe_agent = _sanitize_for_fs(agent_name)
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        info = SessionInfo(
            user_id=safe_user,
            agent_name=safe_agent,
            session_id=session_id,
            root_dir=self.files_root,
            is_workspace=bool(workspace),
        )

        # 创建目录
        for d in [
            info.session_dir,
            info.logs_dir,
            info.conversations_dir,
            info.artifacts_dir,
            info.uploads_dir,
            info.outputs_dir,
            info.temp_dir,
            info.images_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        # latest 指针
        if workspace:
            # workspaces/{user}/{workspace}/{agent}/latest.json
            latest_file = self.files_root / safe_agent / "latest.json"
        else:
            # files/{user}/{agent}/latest.json
            latest_file = self.files_root / safe_user / safe_agent / "latest.json"
        latest_file.parent.mkdir(parents=True, exist_ok=True)
        latest_file.write_text(json.dumps({"session_id": session_id}, ensure_ascii=False, indent=2), encoding="utf-8")

        return info

    def get_latest_session_id(self, user_id: str, agent_name: str) -> Optional[str]:
        safe_user = _sanitize_for_fs(user_id)
        safe_agent = _sanitize_for_fs(agent_name)
        latest_file = self.files_root / safe_user / safe_agent / "latest.json"
        if latest_file.exists():
            try:
                data = json.loads(latest_file.read_text(encoding="utf-8"))
                return data.get("session_id")
            except Exception:
                return None
        return None

    # ======== 标准文件路径 ========
    def conversation_files(self, session: SessionInfo) -> Dict[str, Path]:
        base = session.conversations_dir
        return {
            "system_prompt": base / "agent_system_prompt.md",
            "tool_system_prompt": base / "tool_system_prompt.md",
            "judge_prompt": base / "judge_prompt.md",
            "conversations": base / "conversations.json",
            "display": base / "display_conversations.md",
            "full": base / "full_context_conversations.md",
            "tools": base / "tool_conversations.json",
            "tool_execute": base / "tool_execute_conversations.md",
            "team_context": base / "team_context.json",
        }

    # ======== 日志 ========
    def get_session_logger(self, session: SessionInfo) -> logging.Logger:
        key = f"{session.user_id}:{session.agent_name}:{session.session_id}"
        if key in self._session_loggers:
            return self._session_loggers[key]

        logger = logging.getLogger(f"agent.session.{key}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # 控制台Handler
        console = logging.StreamHandler()
        console.setLevel(self.console_level)
        console.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s | user=%(user_id)s session=%(session_id)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

        # 轮转文件Handler
        log_file = session.logs_dir / "agent.log"
        file_handler = RotatingFileHandler(str(log_file), maxBytes=self.log_max_bytes, backupCount=self.log_backup_count, encoding="utf-8")
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s | user=%(user_id)s session=%(session_id)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

        # 错误日志独立文件
        error_file = session.logs_dir / "error.log"
        error_handler = RotatingFileHandler(str(error_file), maxBytes=self.log_max_bytes, backupCount=self.log_backup_count, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s | user=%(user_id)s session=%(session_id)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

        # JSON事件日志（便于后续分析/可视化），一行一个事件
        json_file = session.logs_dir / "events.jsonl"
        json_handler = RotatingFileHandler(str(json_file), maxBytes=self.log_max_bytes, backupCount=self.log_backup_count, encoding="utf-8")
        json_handler.setLevel(self.file_level)
        json_formatter = jsonlogger.JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S")
        json_handler.setFormatter(json_formatter)

        # 自定义Filter注入上下文
        class _CtxFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                setattr(record, "user_id", session.user_id)
                setattr(record, "session_id", session.session_id)
                setattr(record, "agent_name", session.agent_name)
                return True

        # 重要: 既要给 logger 添加过滤器, 也要给每个 handler 添加
        # 这样可确保子 logger 通过父 handler 输出时, 记录在格式化前也拥有所需字段
        ctx_filter = _CtxFilter()
        logger.addFilter(ctx_filter)
        console.addFilter(ctx_filter)
        file_handler.addFilter(ctx_filter)
        error_handler.addFilter(ctx_filter)
        json_handler.addFilter(ctx_filter)

        logger.addHandler(console)
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)
        logger.addHandler(json_handler)

        self._session_loggers[key] = logger
        return logger

    def get_component_logger(self, session: SessionInfo, component: str) -> logging.Logger:
        """获取带有组件名的子Logger，复用同一套Handlers与上下文。

        示例: component="llm", "tools", "state"
        """
        parent = self.get_session_logger(session)
        child = parent.getChild(component)
        return child


# 全局实例
file_manager = FileManager()


