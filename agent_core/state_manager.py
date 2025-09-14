"""
智能体状态管理器
文件路径: agent_core/state_manager.py
功能: 管理/持久化对话、工具执行、TeamContext；提供会话文件读写与格式化输出

Author: Your Name
Date: 2025-09-10
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from utils.file_manager import file_manager, SessionInfo
from utils.conversation_store import ConversationStore, SessionKey
from .models import TeamContextModel


ConversationHistory = List[Dict[str, str]]


class AgentStateManager:
    """
    管理和持久化智能体的所有状态

    - 对话历史：conversations / tool_conversations
    - 可视内容：display_conversations
    - 全量上下文：full_context_conversations / tool_execute_conversations
    - TeamContext：团队共享上下文（支持外部共享文件）
    """

    def __init__(self, config: Union[Any, "AgentSettings"]) -> None:
        self.config = config
        self.session: Optional[SessionInfo] = None
        self.logger: logging.Logger = logging.getLogger("agent.session")

        self.conversations: ConversationHistory = []
        self.tool_conversations: ConversationHistory = []
        self.display_conversations: str = ""
        self.full_context_conversations: str = ""
        self.tool_execute_conversations: str = ""

        self.team_context: Dict[str, Any] = {}
        self._team_ctx_model: Optional[TeamContextModel] = None
        self._team_context_override_path: Optional[Path] = None

        self.config.user_folder.mkdir(parents=True, exist_ok=True)
        self._conv_files: Dict[str, Any] = {}

        # 可选: 数据库存储后端
        self._conv_store: Optional[ConversationStore] = None
        try:
            backend = str(getattr(self.config, "storage_backend", "filesystem")).lower()
            db_path = getattr(self.config, "db_path", None)
            if backend == "sqlite" and db_path:
                self._conv_store = ConversationStore(db_path=str(db_path), logger=self.logger)
                self.logger.info("已启用SQLite会话镜像存储", extra={"event": "db_store_enabled", "db_path": str(db_path)})
        except Exception as e:
            self.logger.exception("初始化数据库存储后端失败: %s", e)

        self.init_conversations()

    # ========== TeamContext 读写与格式化 ==========
    def set_team_context_override_path(self, path: Union[str, Path]) -> None:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._team_context_override_path = p
            self.logger.debug("设置team_context外部路径: %s", str(p))
        except Exception as e:
            self.logger.exception("设置team_context外部路径失败: %s", e)

    def _team_context_file(self) -> Path:
        if self._team_context_override_path is not None:
            return self._team_context_override_path
        if not self._conv_files and self.session is not None:
            self._conv_files = file_manager.conversation_files(self.session)
        return self._conv_files.get("team_context", (self.config.user_folder / "team_context.json"))

    def load_team_context(self) -> None:
        try:
            f = self._team_context_file()
            if f.exists():
                text = f.read_text(encoding="utf-8").strip()
                if text:
                    loaded = json.loads(text)
                    try:
                        self._team_ctx_model = TeamContextModel.model_validate(loaded)  # type: ignore[attr-defined]
                        self.team_context = self._team_ctx_model.model_dump()
                    except Exception:
                        self.team_context = loaded if isinstance(loaded, dict) else {}
                    # 清理历史遗留的不需要字段（如 answer）
                    if isinstance(self.team_context, dict) and "answer" in self.team_context:
                        try:
                            removed_preview = str(self.team_context.get("answer"))[:120]
                        except Exception:
                            removed_preview = "<unprintable>"
                        try:
                            del self.team_context["answer"]
                        except Exception:
                            pass
                        try:
                            if self._team_ctx_model is not None:
                                # 重新校验并同步模型
                                self._team_ctx_model = TeamContextModel.model_validate(self.team_context)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        self.logger.info(
                            "清理历史TeamContext字段: 移除 answer",
                            extra={
                                "event": "team_context_sanitize_on_load",
                                "removed_preview": removed_preview,
                            },
                        )
                        # 立即持久化一次，避免文件中残留
                        self.save_team_context()
                    self.logger.debug("加载team_context成功，键数: %s", len(self.team_context))
        except Exception as e:
            self.logger.exception("加载team_context失败: %s", e)

    def save_team_context(self) -> None:
        try:
            f = self._team_context_file()
            payload: Dict[str, Any]
            if self._team_ctx_model is not None:
                try:
                    payload = self._team_ctx_model.model_dump()
                except Exception:
                    payload = self.team_context
            else:
                payload = self.team_context
            f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self.logger.exception("保存team_context失败: %s", e)

    def update_team_context(self, patch: Dict[str, Any]) -> None:
        try:
            # 统一清洗：移除不需要写入 TeamContext 的字段
            sanitized_patch: Dict[str, Any] = dict(patch or {})
            if "answer" in sanitized_patch:
                try:
                    removed_preview = str(sanitized_patch.get("answer"))[:120]
                except Exception:
                    removed_preview = "<unprintable>"
                del sanitized_patch["answer"]
                self.logger.debug(
                    "移除TeamContext中不需要的字段: answer",
                    extra={
                        "event": "team_context_sanitize_patch",
                        "removed_preview": removed_preview,
                    },
                )

            if self._team_ctx_model is None:
                try:
                    self._team_ctx_model = TeamContextModel.model_validate(self.team_context or {})  # type: ignore[attr-defined]
                except Exception:
                    self._team_ctx_model = None
            if self._team_ctx_model is not None:
                merged = self._team_ctx_model.merge_patch(sanitized_patch or {})
                try:
                    self._team_ctx_model = TeamContextModel.model_validate(merged)  # type: ignore[attr-defined]
                    self.team_context = self._team_ctx_model.model_dump()
                except Exception:
                    self.team_context = merged
            else:
                self.team_context = {**(self.team_context or {}), **(sanitized_patch or {})}

            # 再次兜底：若合并后仍存在 answer 则移除
            if isinstance(self.team_context, dict) and "answer" in self.team_context:
                try:
                    del self.team_context["answer"]
                except Exception:
                    pass
            self.logger.info("更新TeamContext", extra={"event": "team_context_update", "patch_preview": str(patch)[:400]})
            self.save_team_context()
        except Exception as e:
            self.logger.exception("更新team_context失败: %s", e)

    def format_team_context_for_prompt(self) -> str:
        try:
            if not self.team_context:
                return "(暂无团队上下文)"
            ordered: Dict[str, Any] = {}
            for k in [
                "team_goal",
                "objectives",
                "milestones",
                "findings",
                "decisions",
                "blockers",
                "next_actions",
            ]:
                if k in self.team_context:
                    ordered[k] = self.team_context[k]
            for k, v in self.team_context.items():
                if k not in ordered:
                    ordered[k] = v
            return json.dumps(ordered, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.debug("格式化team_context失败: %s", e)
            return "(团队上下文格式化失败)"

    # ========== 会话/对话 ==========
    def init_conversations(self, system_prompt: str = "") -> None:
        self.conversations = [{"role": "system", "content": system_prompt}] if system_prompt else []
        try:
            if self.session is not None:
                if not self._conv_files:
                    self._conv_files = file_manager.conversation_files(self.session)
                self._conv_files["system_prompt"].write_text(system_prompt, encoding="utf-8")
        except Exception as e:
            self.logger.exception("写入系统提示词失败: %s", e)

    def restore_from_session_files(self) -> None:
        try:
            if self.session is None:
                return
            if not self._conv_files:
                self._conv_files = file_manager.conversation_files(self.session)
            conv_paths = self._conv_files

            try:
                display_path = conv_paths["display"]
                if display_path.exists():
                    self.display_conversations = display_path.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.debug("恢复display_conversations失败: %s", e)

            try:
                full_path = conv_paths["full"]
                if full_path.exists():
                    self.full_context_conversations = full_path.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.debug("恢复full_context_conversations失败: %s", e)

            try:
                tools_path = conv_paths["tools"]
                if tools_path.exists():
                    tools_text = tools_path.read_text(encoding="utf-8")
                    if tools_text.strip():
                        loaded_tools = json.loads(tools_text)
                        if isinstance(loaded_tools, list):
                            self.tool_conversations = loaded_tools
            except Exception as e:
                self.logger.debug("恢复tool_conversations失败: %s", e)

            try:
                conv_path = conv_paths["conversations"]
                if conv_path.exists():
                    conv_text = conv_path.read_text(encoding="utf-8")
                    if conv_text.strip():
                        loaded_conv = json.loads(conv_text)
                        if isinstance(loaded_conv, list):
                            self.conversations = loaded_conv
            except Exception as e:
                self.logger.debug("恢复conversations失败: %s", e)

            self.load_team_context()
        except Exception as e:
            self.logger.exception("恢复历史会话失败: %s", e)

    def add_message(self, role: str, content: str, stream_prefix: str = "") -> None:
        if role not in ["user", "assistant", "tool", "react"]:
            raise ValueError(f"不支持的消息角色: {role}")
        processed_content = self._decode_if_base64(content)
        if role == "user":
            self._add_user_message(processed_content)
        elif role == "assistant":
            self._add_assistant_message(processed_content)
        elif role == "tool":
            self._add_tool_message(processed_content, stream_prefix)
        elif role == "react":
            self._add_react_message(processed_content, stream_prefix)

    def _add_user_message(self, content: str) -> None:
        formatted_content = f"===user===: \n{content}\n"
        self.display_conversations += formatted_content
        self.full_context_conversations += formatted_content
        self.tool_execute_conversations += formatted_content
        self.conversations.append({"role": "user", "content": content})

    def _add_assistant_message(self, content: str) -> None:
        self.conversations.append({"role": "assistant", "content": content})
        formatted_content = f"===assistant===: \n{content}\n"
        self.display_conversations += formatted_content
        self.full_context_conversations += formatted_content

    def _add_tool_message(self, content: str, stream_prefix: str) -> None:
        formatted_content = f"===tool===: \n{stream_prefix}{content}\n"
        self.full_context_conversations += formatted_content

    def _add_react_message(self, content: str, stream_prefix: str) -> None:
        formatted_content = f"===react===: \n{stream_prefix}{content}\n"
        self.full_context_conversations += formatted_content

    def _decode_if_base64(self, content: str) -> str:
        if len(content) < 50 or any(char in content for char in [" ", "。", "，", "？", "！", "\n"]):
            return content
        base64_pattern = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")
        if not base64_pattern.match(content.strip()):
            return content
        try:
            decoded_bytes = base64.b64decode(content.strip())
            decoded_text = decoded_bytes.decode("utf-8")
            self.logger.debug("检测到Base64编码内容，已解码为: %s...", decoded_text[:100])
            return decoded_text
        except Exception:
            return content

    def get_full_display_conversations(self) -> str:
        return self.display_conversations

    def list_user_files(self, recursive: bool = False) -> str:
        try:
            user_folder = Path(self.session.session_dir) if self.session is not None else self.config.user_folder
            self.logger.debug(f"正在扫描会话/用户文件夹: {user_folder}, 递归模式: {recursive}")
            if not user_folder.exists():
                self.logger.debug(f"会话/用户文件夹不存在，正在创建: {user_folder}")
                user_folder.mkdir(parents=True, exist_ok=True)
                return "用户文件夹为空"
            folder_files: Dict[str, List[str]]
            folder_files = self._scan_files_recursive(user_folder) if recursive else self._scan_files_single_level(user_folder)
            if not folder_files:
                return "用户文件夹为空"
            return self._format_file_list(folder_files)
        except Exception as e:
            self.logger.exception("扫描用户文件夹时出错: %s", e)
            return f"扫描用户文件夹时出错: {e}"

    def _scan_files_recursive(self, user_folder: Path) -> Dict[str, List[str]]:
        folder_files: Dict[str, List[str]] = {}
        for root, _dirs, filenames in os.walk(str(user_folder)):
            if filenames:
                relative_root = os.path.relpath(root, str(user_folder)).replace("\\", "/")
                if relative_root == ".":
                    relative_root = "根目录"
                folder_files[relative_root] = sorted(filenames)
                self.logger.debug("文件夹 %s 包含 %s 个文件", relative_root, len(filenames))
        return folder_files

    def _scan_files_single_level(self, user_folder: Path) -> Dict[str, List[str]]:
        folder_files: Dict[str, List[str]] = {}
        filenames = [f.name for f in user_folder.iterdir() if f.is_file()]
        if filenames:
            folder_files["根目录"] = sorted(filenames)
        return folder_files

    def _format_file_list(self, folder_files: Dict[str, List[str]]) -> str:
        result_lines: List[str] = []
        for folder_name, files in sorted(folder_files.items()):
            result_lines.append(f"路径：{folder_name}")
            for file_name in files:
                result_lines.append(f"- {file_name}")
            result_lines.append("")
        if result_lines and result_lines[-1] == "":
            result_lines.pop()
        return "\n".join(result_lines)

    def save_all_conversations(self) -> None:
        try:
            if self.session is not None:
                self._save_with_session()
            else:
                self._save_without_session()
            # 可选: 数据库镜像
            self._save_to_db_if_enabled()
        except Exception as e:
            self.logger.exception("保存对话历史时出错: %s", e)

    def _save_with_session(self) -> None:
        if not self._conv_files:
            self._conv_files = file_manager.conversation_files(self.session)
        files_to_save = [
            ("conversations", json.dumps(self.conversations, ensure_ascii=False, indent=2)),
            ("display", self.display_conversations),
            ("full", self.full_context_conversations),
            ("tools", json.dumps(self.tool_conversations, ensure_ascii=False, indent=2)),
            ("tool_execute", self.tool_execute_conversations),
        ]
        for file_key, content in files_to_save:
            try:
                self._conv_files[file_key].write_text(content, encoding="utf-8")
            except Exception as e:
                self.logger.error(f"保存{file_key}文件失败: {e}")
        self.save_team_context()

    def _save_without_session(self) -> None:
        files_to_save = [
            ("conversations.json", json.dumps(self.conversations, ensure_ascii=False, indent=2)),
            ("display_conversations.md", self.display_conversations),
            ("full_context_conversations.md", self.full_context_conversations),
            ("tool_conversations.json", json.dumps(self.tool_conversations, ensure_ascii=False, indent=2)),
            ("tool_execute_conversations.md", self.tool_execute_conversations),
        ]
        for filename, content in files_to_save:
            try:
                file_path = self.config.user_folder / filename
                file_path.write_text(content, encoding="utf-8")
            except Exception as e:
                self.logger.error(f"保存{filename}文件失败: {e}")
        self.save_team_context()

    # ========== 数据库镜像写入 ==========
    def _save_to_db_if_enabled(self) -> None:
        try:
            if self._conv_store is None:
                return
            # 仅当存在 session 时写入数据库，确保 session_id 稳定
            if self.session is None:
                return
            key = SessionKey(
                user_id=str(getattr(self.config, "user_id", "unknown")),
                agent_name=str(getattr(self.config, "agent_name", "agent")),
                session_id=str(self.session.session_id),
            )
            self._conv_store.save_snapshot(
                key=key,
                messages=self.conversations,
                display_md=self.display_conversations,
                full_md=self.full_context_conversations,
                tool_conversations=self.tool_conversations,
                tool_execute_md=self.tool_execute_conversations,
                team_context=self.team_context or {},
            )
        except Exception as e:
            self.logger.exception("数据库镜像写入失败: %s", e)


