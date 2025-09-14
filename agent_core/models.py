"""
Pydantic模型定义
文件路径: agent_core/models.py
功能: 定义工具事件、意图结果、TeamContext 等核心数据模型，提供统一校验与序列化

Author: Your Name
Date: 2025-09-10
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
    from pydantic import ConfigDict
    from typing import Literal
except Exception:
    BaseModel = object  # type: ignore
    Field = lambda *args, **kwargs: None  # type: ignore
    ConfigDict = dict  # type: ignore
    from typing import Literal  # type: ignore


class ToolEventModel(BaseModel):
    """
    工具事件结构（用于统一生成/校验工具事件并序列化为前端可消费格式）。
    """

    type: Literal["tool_start", "tool_result", "tool_error"] = Field(description="事件类型")
    tool_name: str = Field(description="工具名称")
    timestamp: float = Field(description="事件时间戳")
    status: Literal["running", "completed", "failed"] = Field(default="running")
    tool_args: Optional[Dict[str, Any]] = None
    content: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_event_string(self) -> str:
        try:
            return f"[[TOOL_EVENT]]{json.dumps(self.model_dump(exclude_none=True), ensure_ascii=False, default=str)}"
        except Exception:
            payload = {
                "type": getattr(self, "type", "unknown"),
                "tool_name": getattr(self, "tool_name", "unknown"),
                "timestamp": getattr(self, "timestamp", time.time()),
                "status": getattr(self, "status", "running"),
            }
            for k in ("tool_args", "content", "result", "error"):
                v = getattr(self, k, None)
                if v is not None:
                    payload[k] = v
            return f"[[TOOL_EVENT]]{json.dumps(payload, ensure_ascii=False, default=str)}"


class IntentionResultModel(BaseModel):
    """意图识别结果模型。"""

    tools: List[str] = Field(default_factory=list)


class TeamContextModel(BaseModel):
    """
    TeamContext 标准化模型：
    - 允许常用关键字段；
    - 允许附加自定义字段（extra=allow）。
    """

    model_config = ConfigDict(extra="allow")

    team_goal: Optional[str] = None
    objectives: Optional[List[str]] = None
    milestones: Optional[List[str]] = None
    findings: Optional[List[str]] = None
    decisions: Optional[List[str]] = None
    blockers: Optional[List[str]] = None
    next_actions: Optional[List[str]] = None

    def merge_patch(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """返回合并后的 dict（不修改当前实例）。"""
        try:
            validated = TeamContextModel.model_validate(patch)  # type: ignore[attr-defined]
            merged = {**self.model_dump(), **validated.model_dump(exclude_unset=True, exclude_none=True)}
            return merged
        except Exception:
            return {**getattr(self, "model_dump", lambda: {})(), **(patch or {})}  # type: ignore[misc]


