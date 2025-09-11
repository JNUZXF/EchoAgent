"""
提示词管理器
文件路径: agent_core/prompts.py
功能: 统一生成系统提示词、判断提示词、意图识别提示词，注入工具Schema与会话上下文

Author: Your Name
Date: 2025-09-10
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from prompts.agent_prompts import (
    AGENT_SYSTEM_PROMPT,
    AGENT_JUDGE_PROMPT,
    AGENT_INTENTION_RECOGNITION_PROMPT,
    AGENT_TOOLS_GUIDE,
    FRAMEWORK_RUNNING_CHARACTER,
    AGENT_INTENTION_RECOGNITION_PROMPT_V2,
)


class AgentPromptManager:
    """根据上下文与工具动态生成提示词。"""

    def get_system_prompt(self, **kwargs: Any) -> str:
        user_system_prompt = kwargs.get("user_system_prompt", "")
        try:
            return AGENT_SYSTEM_PROMPT.format(
                AGENT_TOOLS_GUIDE=AGENT_TOOLS_GUIDE,
                FRAMEWORK_RUNNING_CHARACTER=FRAMEWORK_RUNNING_CHARACTER,
                user_system_prompt=user_system_prompt,
            )
        except KeyError as e:
            logging.getLogger("agent.prompt").error(f"系统提示词格式化失败: {e}")
            return AGENT_SYSTEM_PROMPT

    def get_judge_prompt(self, full_context_conversations: str, **kwargs: Any) -> str:
        try:
            return AGENT_JUDGE_PROMPT.format(
                full_context_conversations=full_context_conversations,
                session_dir=kwargs.get("session_dir", ""),
                files=kwargs.get("files", ""),
                agent_name=kwargs.get("agent_name", ""),
                current_date=datetime.now().strftime("%Y-%m-%d"),
                tools=kwargs.get("tool_configs", ""),
            )
        except KeyError as e:
            logging.getLogger("agent.prompt").error(f"判断提示词格式化失败: {e}")
            return AGENT_JUDGE_PROMPT

    def get_intention_prompt(self, **kwargs: Any) -> str:
        tool_use_example = kwargs.get("tool_use_example", "")
        try:
            return AGENT_INTENTION_RECOGNITION_PROMPT.format(
                AGENT_TOOLS_GUIDE=AGENT_TOOLS_GUIDE,
                tools=kwargs.get("tool_configs", ""),
                files=kwargs.get("files", ""),
                userID=kwargs.get("user_id", ""),
                conversation=kwargs.get("display_conversations", ""),
                tool_use_example=tool_use_example,
            )
        except KeyError as e:
            logging.getLogger("agent.prompt").error(f"意图识别提示词格式化失败: {e}")
            return AGENT_INTENTION_RECOGNITION_PROMPT

    def get_intention_prompt_v2(self, **kwargs: Any) -> str:
        tool_use_example = kwargs.get("tool_use_example", "")
        try:
            return AGENT_INTENTION_RECOGNITION_PROMPT_V2.format(
                AGENT_TOOLS_GUIDE=AGENT_TOOLS_GUIDE,
                tools=kwargs.get("tool_configs", ""),
                files=kwargs.get("files", ""),
                userID=kwargs.get("user_id", ""),
                conversation=kwargs.get("display_conversations", ""),
                tool_use_example=tool_use_example,
            )
        except KeyError as e:
            logging.getLogger("agent.prompt").error(f"意图识别提示词格式化失败: {e}")
            return AGENT_INTENTION_RECOGNITION_PROMPT_V2


