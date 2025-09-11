"""
智能体主框架
文件路径: agent_frame_v4.py
功能: 根据用户的需求，自主调用工具（1轮/多轮）/直接回答问题

这个模块实现了一个完整的智能体框架，包括：
- 配置管理：AgentConfig
- 状态管理：AgentStateManager  
- 工具管理：AgentToolManager
- 提示词管理：AgentPromptManager
- 核心框架：EchoAgent

Author: Your Name
Version: 1.0.0
Date: 2024-01-01
"""

import os
import json
import asyncio
import base64
import re
import time
from datetime import datetime
from typing import (
    List, Dict, Any, AsyncGenerator, Optional, Union, 
    Callable, Awaitable, Protocol
)
import logging
from pathlib import Path

# 第三方导入
from tools_agent.function_call_toolbox import get_func_name, convert_outer_quotes
from tools_agent.parse_function_call import parse_function_call
from tools_agent.json_tool import get_json
from tools_agent.llm_manager import LLMManager

from utils.code_runner import extract_python_code
from utils.file_manager import file_manager, SessionInfo

from prompts.agent_prompts import (
    AGENT_SYSTEM_PROMPT,
    AGENT_JUDGE_PROMPT,
    AGENT_INTENTION_RECOGNITION_PROMPT,
    AGENT_TOOLS_GUIDE,
    TOOL_RESULT_ANA_PROMPT,
    FRAMEWORK_RUNNING_CHARACTER
)
from tools_agent.toolkit import ToolRegistry
from tools_agent.builtin_tools import CodeRunner as Tool_CodeRunner, continue_analyze as Tool_ContinueAnalyze

# 导入配置管理模块
from config import AgentSettings, create_agent_config
from agent_core import ToolEventModel, IntentionResultModel, TeamContextModel
from agent_core import AgentStateManager, AgentToolManager, AgentPromptManager

# 配置环境变量
os.environ["NUMEXPR_MAX_THREADS"] = "32" 

# 模块级日志
MODULE_LOGGER = logging.getLogger("agent.bootstrap")
MODULE_LOGGER.info("AgentCoder模块加载完成")

# 类型别名
ConversationHistory = List[Dict[str, str]]
ToolConfig = Dict[str, Any]
ToolResult = Any


class ToolExecutor(Protocol):
    """工具执行器协议定义"""
    async def execute(self, **kwargs: Any) -> Any:
        """执行工具的协议方法"""
        ...

class EchoAgent:
    """
    智能体核心框架
    
    这是智能体的主要实现类，负责协调各个组件，处理用户查询，
    执行工具调用，并管理整个对话流程。
    
    Attributes:
        config: 智能体配置对象
        user_id: 用户唯一标识符
        conversation_id: 对话会话ID
        tool_manager: 工具管理器
        prompt_manager: 提示词管理器
        session: 会话信息对象
        logger: 日志记录器
        state_manager: 状态管理器
        main_llm: 主要LLM管理器
        tool_llm: 工具判断LLM管理器
        flash_llm: 快速响应LLM管理器
        question_count: 用户问题计数器
        STOP_SIGNAL: 停止信号常量
        tool_use_example:工具使用示例提示词，提高工具使用准确率，嵌入工具系统提示词中
    """

    # 类常量
    STOP_SIGNAL: str = "END()"
    STOP_SIGNAL_V2: str = "FINAL_ANS"
    
    def __init__(self, config: Union[Any, AgentSettings], **kwargs: Any) -> None:
        """
        【开闭原则】初始化智能体核心框架，兼容新旧配置系统
        
        Args:
            config: 智能体配置对象（支持新版AgentSettings或旧版配置）
            **kwargs: 其他初始化参数
            
        Raises:
            Exception: 初始化过程中的异常会被记录并重新抛出
        """
        try:
            self.config = config
            # 【兼容性设计】处理新旧配置系统的差异
            if isinstance(config, AgentSettings):
                # 新配置系统：直接使用AgentSettings对象
                self.user_id = config.user_id
                self.conversation_id = config.conversation_id
            else:
                # 旧配置系统：转换为兼容格式
                legacy_config = config.to_legacy_config() if hasattr(config, 'to_legacy_config') else config
                self.user_id = legacy_config.user_id
                self.conversation_id = legacy_config.conversation_id
            
            # 创建工具与提示词管理
            self.tool_manager = AgentToolManager()
            self.prompt_manager = AgentPromptManager()
            
            # 创建会话目录与日志（支持前端注入session_id）
            self.session: SessionInfo = file_manager.create_session(
                user_id=self.user_id,
                agent_name=self.config.agent_name,
                session_id=self.conversation_id if self.conversation_id else None,
                workspace=self.config.workspace
            )
            
            self.logger: logging.Logger = file_manager.get_session_logger(self.session)
            self.logger.info(
                "创建会话目录", 
                extra={
                    "event": "session_init", 
                    "session_dir": str(self.session.session_dir)
                }
            )
            
            # 状态管理器并注入会话
            self.state_manager = AgentStateManager(config)
            self.state_manager.session = self.session
            
            # 为状态管理器注入组件级 logger，确保日志落到会话目录
            self.state_manager.logger = file_manager.get_component_logger(
                self.session, "state"
            )
            
            # 初始化对话文件索引
            self.state_manager._conv_files = file_manager.conversation_files(self.session)
            
            # 恢复历史会话上下文，支持跨请求续聊
            try:
                self.state_manager.restore_from_session_files()
            except Exception as restore_error:
                self.logger.warning(f"恢复历史会话失败: {restore_error}")

            # 初始化LLM管理器
            self.main_llm = LLMManager(config.main_model)
            self.tool_llm = LLMManager(config.tool_model)
            self.flash_llm = LLMManager(config.flash_model)
            
            # 记录用户问题的次数
            self.question_count: int = 0
            
            # 注册本地工具
            self._register_local_tools()
            
            self.logger.info(
                "智能体初始化完成", 
                extra={
                    "event": "agent_init", 
                    "user_id": self.user_id,
                    "agent_name": config.agent_name
                }
            )
            self.tool_use_example = self.config.tool_use_example
            
        except Exception as e:
            logging.getLogger("agent.init").exception("智能体初始化失败: %s", e)
            raise

    # ================= TeamContext 对外API =================
    def set_team_context_override_path(self, path: Union[str, Path]) -> None:
        """设置TeamContext外部共享文件路径（跨Agent共享）。"""
        self.state_manager.set_team_context_override_path(path)

    def update_team_context(self, patch: Dict[str, Any]) -> None:
        """合并式更新TeamContext并持久化。"""
        self.state_manager.update_team_context(patch)

    def get_team_context(self) -> Dict[str, Any]:
        """获取当前TeamContext的浅拷贝。"""
        try:
            return dict(self.state_manager.team_context or {})
        except Exception:
            return {}

    def set_team_goal(self, goal: str) -> None:
        """设置团队目标(team_goal)。"""
        self.update_team_context({"team_goal": goal})

    def _register_local_tools(self) -> None:
        """
        注册所有本地工具
        
        这个方法负责注册智能体可以使用的所有工具，包括代码执行器
        和继续分析工具等。
        
        Raises:
            Exception: 工具注册失败时记录异常但不中断初始化
        """
        try:
            # 新体系: 注册基于 @tool 的函数工具
            self.tool_manager.register_tool_function(Tool_CodeRunner)
            self.tool_manager.register_tool_function(Tool_ContinueAnalyze)
            
            self.logger.debug("本地工具注册完成")
            
        except Exception as e:
            self.logger.exception("注册本地工具失败: %s", e)
            # 不抛出异常，允许智能体在没有某些工具的情况下继续运行
    
    async def _get_tool_intention(self) -> List[str]:
        """
        使用LLM判断用户的意图，并返回建议的工具列表
        
        这个方法分析当前对话上下文，判断用户意图，并决定需要调用哪些工具。
        
        Returns:
            建议使用的工具名称列表
            
        Raises:
            Exception: 意图判断过程中的异常会被捕获并记录
        """
        # 重置工具对话历史
        self.state_manager.tool_conversations = []
        
        try:
            # 准备意图识别的上下文参数
            kwargs = {
                "files": self.state_manager.list_user_files(),
                "user_id": self.config.user_id,
                "display_conversations": self.state_manager.display_conversations,
                "tool_configs": self.tool_manager.get_all_tool_configs_for_prompt(),
                "tool_use_example": self.tool_use_example
            }
            
            # 生成工具意图识别提示词
            tool_system_prompt = self.prompt_manager.get_intention_prompt(**kwargs)

            # 构建对话历史并执行意图判断
            self.state_manager.tool_conversations.append({
                "role": "user", 
                "content": tool_system_prompt
            })
            intention_history = [{"role": "user", "content": tool_system_prompt}]
            
            # 流式生成意图判断结果
            ans = ""
            self.logger.debug("开始意图判断")
            for char in self.tool_llm.generate_stream_conversation(intention_history):
                ans += char
                print(char, end="", flush=True)
            print()
                
            self.logger.debug("INTENTION RAW: %s", ans)
            self.state_manager.tool_conversations.append({
                "role": "assistant", 
                "content": ans
            })

            # 保存工具系统提示词到会话文件
            try:
                self.state_manager._conv_files["tool_system_prompt"].write_text(
                    tool_system_prompt, encoding="utf-8"
                )
            except Exception as save_error:
                self.logger.warning(f"保存工具系统提示词失败: {save_error}")

            self.state_manager.tool_execute_conversations += f"===assistant===: \n{ans}\n"

            # 解析JSON结果并提取工具列表
            return self._parse_intention_result(ans)
            
        except Exception as e:
            self.logger.exception("获取工具意图时发生错误: %s", e)
            return [self.STOP_SIGNAL]

    def _parse_intention_result(self, raw_response: str) -> List[str]:
        """
        解析意图判断的原始响应，提取工具列表
        
        Args:
            raw_response: LLM的原始响应内容
            
        Returns:
            解析出的工具名称列表，解析失败时返回停止信号
        """
        try:
            json_result = get_json(raw_response)
            
            if not isinstance(json_result, dict):
                self.logger.error("解析后的JSON不是一个字典: %s", json_result)
                return [self.STOP_SIGNAL]

            tools = json_result.get("tools", [self.STOP_SIGNAL])
            
            if not isinstance(tools, list):
                self.logger.error("'tools' 字段不是一个列表: %s", tools)
                return [self.STOP_SIGNAL]
                
            # 验证工具列表有效性
            if not tools:
                self.logger.warning("工具列表为空")
                return [self.STOP_SIGNAL]
                
            try:
                # 使用 Pydantic 校验
                validated = IntentionResultModel.model_validate({"tools": tools})  # type: ignore[attr-defined]
                tools_list = validated.tools
            except Exception:
                tools_list = tools
            self.logger.debug(f"解析出工具列表: {tools_list}")
            return tools_list
            
        except Exception as e:
            self.logger.exception("解析意图JSON时发生未知错误: %s", e)
            return [self.STOP_SIGNAL]
 
    async def _agent_reset(self) -> None:
        """
        重置智能体状态并准备新的对话轮次
        
        这个方法不会清空已有的显示/全量上下文，而是使用已有上下文
        生成新的系统/判断提示，保持续聊能力。
        
        Raises:
            Exception: 重置过程中的异常会被记录但不会中断流程
        """
        try:
            # 准备提示词生成参数
            # 将团队上下文注入到系统提示的可扩展区域
            team_ctx_text = self.state_manager.format_team_context_for_prompt()
            merged_user_system_prompt = (self.config.user_system_prompt or "") + "\n\n# 团队上下文(TeamContext)\n" + team_ctx_text
            kwargs = {
                "userID": self.user_id,
                "session_dir": str(self.session.session_dir),
                "files": self.state_manager.list_user_files(),
                "agent_name": self.config.agent_name,
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "tool_configs": self.tool_manager.get_all_tool_configs_for_prompt(),
                "user_system_prompt": merged_user_system_prompt,
                "tool_use_example": self.tool_use_example
            }
            
            # 生成并设置系统提示词
            system_prompt = self.prompt_manager.get_system_prompt(**kwargs)
            self.state_manager.init_conversations(system_prompt)
            
            # 生成判断提示词
            judge_prompt = self.prompt_manager.get_judge_prompt(
                self.state_manager.full_context_conversations, 
                **kwargs
            )
            
            # 保存judge_prompt到当前会话
            try:
                self.state_manager._conv_files["judge_prompt"].write_text(
                    judge_prompt, encoding="utf-8"
                )
            except Exception as save_error:
                self.state_manager.logger.warning(f"写入judge_prompt失败: {save_error}")
                
            # 添加判断提示词到对话历史
            self.state_manager.conversations.append({
                "role": "user", 
                "content": judge_prompt
            })
            
            self.logger.debug("智能体状态重置完成")
            
        except Exception as e:
            self.logger.exception("智能体重置失败: %s", e)

    async def process_query(self, question: str) -> AsyncGenerator[str, None]:
        """
        处理单个用户查询的完整工作流
        
        这是智能体的主要处理流程，包括：
        1. 初始化和记录用户问题
        2. 生成初始响应
        3. 判断工具调用意图
        4. 执行工具调用循环
        5. 保存状态和清理
        
        Args:
            question: 用户输入的问题
            
        Yields:
            流式响应内容，包括文本和工具事件
            
        Raises:
            Exception: 处理过程中的严重异常会被记录并可能中断流程
        """
        start_time = datetime.now()
        self.question_count += 1
        
        try:
            # 记录用户问题
            self.state_manager.add_message("user", question)
            self.logger.info(
                "收到用户问题: %s", 
                question, 
                extra={
                    "event": "user_question", 
                    "question_index": self.question_count
                }
            )

            # 初始化对话状态
            await self._agent_reset()

            # 生成初始响应
            initial_response = ""
            self.logger.info(
                "开始主模型流式回答\n======\n", 
                extra={
                    "event": "llm_answer_start", 
                    "model": self.config.main_model
                }
            )
            
            for char in self.main_llm.generate_stream_conversation(
                self.state_manager.conversations
            ):
                initial_response += char
                yield char
                
            yield "\n"
            self.state_manager.add_message("assistant", initial_response)
            # 记录智能体回答的完整内容
            self.logger.info("\n======\n")            
            # 记录智能体回答的完整内容
            self.logger.info(
                "主模型初次回答完成，内容: \n%s\n======", 
                initial_response, 
                extra={
                    "event": "llm_answer_end", 
                    "tokens": len(initial_response)
                }
            )

            # 获取工具调用意图
            intention_tools = await self._get_tool_intention()
            self.logger.info(
                "意图判断结果", 
                extra={
                    "event": "intention_tools", 
                    "tools": intention_tools
                }
            )
            
            last_agent_response = initial_response

            # 工具调用循环
            async for response_chunk in self._execute_tool_loop(
                intention_tools, 
                last_agent_response
            ):
                yield response_chunk

        except Exception as e:
            self.logger.exception("处理查询时发生严重错误: %s", e)
            yield f"\n❌ 处理查询时发生错误: {str(e)}\n"
        
        finally:
            # 结束和清理
            await self._finalize_query_processing(start_time)

    async def _get_tool_intention_v2(self) -> List[str]:
        """
        使用LLM判断用户的意图，并返回建议的工具列表
        
        这个方法分析当前对话上下文，判断用户意图，并决定需要调用哪些工具。
        
        Returns:
            建议使用的工具名称列表
            
        Raises:
            Exception: 意图判断过程中的异常会被捕获并记录
        """
        # 重置工具对话历史
        self.state_manager.tool_conversations = []
        
        try:
            # 准备意图识别的上下文参数
            kwargs = {
                "files": self.state_manager.list_user_files(),
                "user_id": self.config.user_id,
                "display_conversations": self.state_manager.display_conversations,
                "tool_configs": self.tool_manager.get_all_tool_configs_for_prompt(),
                "tool_use_example": self.tool_use_example
            }
            
            # 生成工具意图识别提示词
            tool_system_prompt = self.prompt_manager.get_intention_prompt_v2(**kwargs)

            # 构建对话历史并执行意图判断
            self.state_manager.tool_conversations.append({
                "role": "user", 
                "content": tool_system_prompt
            })
            intention_history = [{"role": "user", "content": tool_system_prompt}]
            
            # 流式生成意图判断结果
            ans = ""
            self.logger.debug("开始意图判断")
            for char in self.tool_llm.generate_stream_conversation(intention_history):
                ans += char
                print(char, end="", flush=True)
            print()
                
            self.logger.debug("INTENTION RAW: %s", ans)
            self.state_manager.tool_conversations.append({
                "role": "assistant", 
                "content": ans
            })

            # 保存工具系统提示词到会话文件
            try:
                self.state_manager._conv_files["tool_system_prompt"].write_text(
                    tool_system_prompt, encoding="utf-8"
                )
            except Exception as save_error:
                self.logger.warning(f"保存工具系统提示词失败: {save_error}")

            self.state_manager.tool_execute_conversations += f"===assistant===: \n{ans}\n"

            # 解析JSON结果并提取工具列表
            return self._parse_intention_result(ans)
            
        except Exception as e:
            self.logger.exception("获取工具意图时发生错误: %s", e)
            return [self.STOP_SIGNAL]

    async def process_query_v2(self, question: str) -> AsyncGenerator[str, None]:
        start_time = datetime.now()
        self.question_count += 1
        
        try:
            # 记录用户问题
            self.state_manager.add_message("user", question)
            self.logger.info(
                "收到用户问题: %s", 
                question, 
                extra={
                    "event": "user_question", 
                    "question_index": self.question_count
                }
            )

            # 初始化对话状态
            await self._agent_reset()

            # 获取工具调用意图
            intention_tools = await self._get_tool_intention_v2()
            self.logger.info(
                "意图判断结果", 
                extra={
                    "event": "intention_tools", 
                    "tools": intention_tools
                }
            )
            async for response_chunk in self._execute_tool_loop_v2(intention_tools):
                yield response_chunk

        except Exception as e:
            self.logger.exception("处理查询时发生严重错误: %s", e)
            yield f"\n❌ 处理查询时发生错误: {str(e)}\n"
        
        finally:
            # 结束和清理
            await self._finalize_query_processing(start_time)

    async def _execute_tool_loop_v2(
        self, 
        intention_tools: List[str],
        last_agent_response: str="",
    ) -> AsyncGenerator[str, None]:
        """
        执行工具调用循环
        
        Args:
            intention_tools: 意图判断得出的工具列表
            
        Yields:
            工具执行过程中的响应内容
        """
        current_response = last_agent_response
        tool_call_str = intention_tools[0]
        func_name = get_func_name(convert_outer_quotes(tool_call_str))
        print(f"func_name: {func_name}")
        if func_name == self.STOP_SIGNAL_V2:
            initial_response = ""
            for char in self.main_llm.generate_stream_conversation(
                self.state_manager.conversations
            ):
                initial_response += char
                yield char
                
            yield "\n"
            self.state_manager.add_message("assistant", initial_response)
            # 记录智能体回答的完整内容
            self.logger.info("\n======\n")            
            # 记录智能体回答的完整内容
            self.logger.info(
                "主模型最终回答完成，内容: \n%s\n======", 
                initial_response, 
                extra={
                    "event": "llm_answer_end", 
                    "tokens": len(initial_response)
                }
            )
        # 工具调用循环
        while func_name != self.STOP_SIGNAL_V2:
            try:
                if not intention_tools:
                    self.logger.error("意图工具列表为空，退出循环。")
                    break
                
                tool_call_str = intention_tools[0]
                func_name = get_func_name(convert_outer_quotes(tool_call_str))

                if not isinstance(func_name, str):
                    self.logger.error(
                        "无法从'%s'中解析出有效的工具名称，跳过。", 
                        tool_call_str
                    )
                    continue

                # 执行单个工具调用
                async for chunk in self._execute_single_tool(
                    tool_call_str, 
                    func_name, 
                    current_response
                ):
                    yield chunk

                # 工具执行+分析回复流结束后，使用最新的助手消息作为下一轮代码提取的来源
                try:
                    for _msg in reversed(self.state_manager.conversations):
                        if isinstance(_msg, dict) and _msg.get("role") == "assistant":
                            current_response = str(_msg.get("content", ""))
                            break
                    self.logger.debug(
                        "更新current_response用于下一轮工具：长度=%s", 
                        len(current_response) if isinstance(current_response, str) else 0
                    )
                except Exception as _upd_err:
                    self.logger.debug("更新current_response失败: %s", _upd_err)

                # 获取下一个意图
                intention_tools = await self._get_tool_intention_v2()
                self.logger.debug("下一个意图: %s", intention_tools[0] if intention_tools else "无")
                tool_call_str = intention_tools[0]
                func_name = get_func_name(convert_outer_quotes(tool_call_str))

                # 保存当前状态
                self.state_manager.save_all_conversations()
                await self._agent_reset()
                
            except Exception as loop_error:
                self.logger.exception("工具循环中发生错误: %s", loop_error)
                yield f"\n⚠️ 工具执行中发生错误: {str(loop_error)}\n"
                break

    async def _execute_tool_loop(
        self, 
        intention_tools: List[str], 
        last_agent_response: str
    ) -> AsyncGenerator[str, None]:
        """
        执行工具调用循环
        
        Args:
            intention_tools: 意图判断得出的工具列表
            last_agent_response: 上一次智能体的响应
            
        Yields:
            工具执行过程中的响应内容
        """
        current_response = last_agent_response
        
        # 工具调用循环
        while self.STOP_SIGNAL not in intention_tools:
            try:
                if not intention_tools:
                    self.logger.error("意图工具列表为空，退出循环。")
                    break
                
                tool_call_str = intention_tools[0]
                func_name = get_func_name(convert_outer_quotes(tool_call_str))

                if func_name == self.STOP_SIGNAL:
                    break

                # 添加类型检查以修复linter错误
                if not isinstance(func_name, str):
                    self.logger.error(
                        "无法从'%s'中解析出有效的工具名称，跳过。", 
                        tool_call_str
                    )
                    continue

                # 执行单个工具调用
                async for chunk in self._execute_single_tool(
                    tool_call_str, 
                    func_name, 
                    current_response
                ):
                    yield chunk

                # 工具执行+分析回复流结束后，使用最新的助手消息作为下一轮代码提取的来源
                try:
                    for _msg in reversed(self.state_manager.conversations):
                        if isinstance(_msg, dict) and _msg.get("role") == "assistant":
                            current_response = str(_msg.get("content", ""))
                            break
                    self.logger.debug(
                        "更新current_response用于下一轮工具：长度=%s", 
                        len(current_response) if isinstance(current_response, str) else 0
                    )
                except Exception as _upd_err:
                    self.logger.debug("更新current_response失败: %s", _upd_err)

                # 获取下一个意图
                intention_tools = await self._get_tool_intention()
                self.logger.debug("下一个意图: %s", intention_tools[0] if intention_tools else "无")
                
                # 保存当前状态
                self.state_manager.save_all_conversations()
                await self._agent_reset()
                
            except Exception as loop_error:
                self.logger.exception("工具循环中发生错误: %s", loop_error)
                yield f"\n⚠️ 工具执行中发生错误: {str(loop_error)}\n"
                break

    async def _execute_single_tool(
        self, 
        tool_call_str: str, 
        func_name: str, 
        last_response: str=""
    ) -> AsyncGenerator[str, None]:
        """
        执行单个工具调用
        
        Args:
            tool_call_str: 工具调用字符串
            func_name: 工具函数名
            last_response: 上一次的响应内容
            
        Yields:
            工具执行过程中的响应内容
        """
        try:
            # 解析工具参数
            params = self._parse_tool_params(tool_call_str, func_name, last_response)
            
            # 发送工具开始事件
            yield self._create_tool_event("tool_start", func_name, params)
            
            # 执行工具
            self.logger.info(
                "开始执行工具", 
                extra={
                    "event": "tool_start", 
                    "tool": func_name, 
                    "params": params
                }
            )
            
            tool_result = await self.tool_manager.execute_tool(func_name, **params)
            
            self.logger.info(
                "工具执行完成", 
                extra={
                    "event": "tool_end", 
                    "tool": func_name, 
                    "result_preview": str(tool_result)[:500]
                }
            )
            
            self.logger.debug(
                "工具 '%s' 返回结果长度: %s", 
                func_name, 
                len(str(tool_result))
            )
            
            # 记录工具结果
            self.state_manager.add_message(
                "tool", 
                str(tool_result), 
                stream_prefix=f"工具{func_name}返回结果:"
            )

            # 尝试从工具结果更新TeamContext
            try:
                self._maybe_update_team_context_from_tool_result(tool_result)
            except Exception as _tc_err:
                self.logger.debug("从工具结果更新TeamContext失败: %s", _tc_err)

            # 发送工具结果事件
            yield self._create_tool_event("tool_result", func_name, tool_result, "completed")
            
            # 生成基于工具结果的响应
            async for chunk in self._generate_tool_response():
                yield chunk
                
        except Exception as e:
            self.logger.exception("执行工具 '%s' 时发生错误: %s", func_name, e)
            # 发送工具错误事件
            yield self._create_tool_event("tool_error", func_name, str(e), "failed")

    def _maybe_update_team_context_from_tool_result(self, tool_result: Any) -> None:
        """根据工具返回内容尝试合并更新TeamContext。

        约定：
        - 若返回为dict且包含键 'team_context' 或 'tc_update' 或 'context_update'，且对应值为dict，则进行合并更新。
        - 若返回为可解析的JSON字符串，且其顶层或上述键对应为dict，则进行合并更新。
        """
        patch: Optional[Dict[str, Any]] = None
        if isinstance(tool_result, dict):
            for k in ("team_context", "tc_update", "context_update"):
                if k in tool_result and isinstance(tool_result[k], dict):
                    patch = tool_result[k]
                    break
            if patch is None:
                # 若直接返回就是扁平上下文字段，也允许合并小字典
                # 但避免将非小型结果误并入，这里做个简单限制：键数<=8
                if 0 < len(tool_result.keys()) <= 8:
                    patch = {k: v for k, v in tool_result.items() if isinstance(k, str)}
        elif isinstance(tool_result, str):
            try:
                parsed = get_json(tool_result)
                if isinstance(parsed, dict):
                    for k in ("team_context", "tc_update", "context_update"):
                        if k in parsed and isinstance(parsed[k], dict):
                            patch = parsed[k]
                            break
            except Exception:
                pass

        if patch:
            self.state_manager.update_team_context(patch)

    def _parse_tool_params(
        self, 
        tool_call_str: str, 
        func_name: str, 
        last_response: str
    ) -> Dict[str, Any]:
        """
        解析工具调用参数
        
        Args:
            tool_call_str: 工具调用字符串
            func_name: 工具函数名
            last_response: 上一次的响应内容
            
        Returns:
            解析出的参数字典
        """
        try:
            params = parse_function_call(tool_call_str)["params"]
        except Exception as e:
            self.logger.exception("解析工具参数失败: %s", e)
            params = {}

        # 如果是CodeRunner，代码从最近一次助手回复中提取
        if func_name == "CodeRunner":
            code_text = extract_python_code(last_response)
            params["code"] = code_text
            try:
                self.logger.debug(
                    "为CodeRunner提取代码：长度=%s", 
                    len(code_text) if isinstance(code_text, str) else 0
                )
            except Exception:
                pass
        
        return params

    def _create_tool_event(
        self, 
        event_type: str, 
        tool_name: str, 
        data: Any, 
        status: str = "running"
    ) -> str:
        """
        创建工具事件的JSON字符串
        
        Args:
            event_type: 事件类型
            tool_name: 工具名称
            data: 事件数据
            status: 事件状态
            
        Returns:
            格式化的工具事件字符串
        """
        try:
            # 使用 Pydantic 模型统一校验与序列化
            if event_type == "tool_start":
                ev = ToolEventModel(
                    type="tool_start", tool_name=tool_name, timestamp=time.time(), status=status,
                    tool_args=data if isinstance(data, dict) else None,
                    content=f"开始调用 {tool_name}"
                )
            elif event_type == "tool_result":
                ev = ToolEventModel(
                    type="tool_result", tool_name=tool_name, timestamp=time.time(), status=status,
                    result=data
                )
            elif event_type == "tool_error":
                ev = ToolEventModel(
                    type="tool_error", tool_name=tool_name, timestamp=time.time(), status=status,
                    error=str(data)
                )
            else:
                ev = ToolEventModel(type="tool_result", tool_name=tool_name, timestamp=time.time(), status=status)
            return ev.to_event_string()
        except Exception as e:
            self.logger.debug("工具事件创建失败: %s", e)
            # 兜底: 维持旧格式，避免前端解析失败
            tool_event = {
                "type": event_type,
                "tool_name": tool_name,
                "timestamp": time.time(),
                "status": status
            }
            if event_type == "tool_start":
                tool_event.update({"tool_args": data if isinstance(data, dict) else None, "content": f"开始调用 {tool_name}"})
            elif event_type == "tool_result":
                tool_event.update({"result": data})
            elif event_type == "tool_error":
                tool_event.update({"error": str(data)})
            return f"[[TOOL_EVENT]]{json.dumps(tool_event, ensure_ascii=False)}"

    async def _generate_tool_response(self) -> AsyncGenerator[str, None]:
        """
        根据工具结果生成智能体响应
        
        Yields:
            智能体对工具结果的分析响应
        """
        try:
            # 添加工具结果分析提示
            self.state_manager.add_message("react", TOOL_RESULT_ANA_PROMPT)

            # 重置智能体状态
            await self._agent_reset()
            
            # 生成响应
            next_response = ""
            self.logger.info(
                "主模型对工具结果进行分析", 
                extra={
                    "event": "llm_after_tool_start", 
                    "model": self.config.main_model
                }
            )
            
            for char in self.main_llm.generate_stream_conversation(
                self.state_manager.conversations
            ):
                next_response += char
                yield char
                
            self.state_manager.add_message("assistant", next_response)
            
            # 记录分析后的完整回答
            self.logger.info(
                "主模型分析完成，内容: %s", 
                next_response, 
                extra={
                    "event": "llm_after_tool_end", 
                    "tokens": len(next_response)
                }
            )
            
        except Exception as e:
            self.logger.exception("生成工具响应时发生错误: %s", e)
            yield f"\n⚠️ 生成响应时发生错误: {str(e)}\n"

    async def _finalize_query_processing(self, start_time: datetime) -> None:
        """
        完成查询处理的收尾工作
        
        Args:
            start_time: 查询开始时间
        """
        try:
            # 保存所有对话历史
            self.state_manager.save_all_conversations()
            
            # 计算和记录处理时间
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.info("流程处理完成，耗时: %.2f 秒", duration)
            self.logger.info(
                "流程处理完成", 
                extra={
                    "event": "query_done", 
                    "question_index": self.question_count, 
                    "duration_sec": duration
                }
            )
            
        except Exception as e:
            self.logger.exception("查询处理收尾时发生错误: %s", e)

    async def chat_loop(self) -> None:
        """
        启动交互式对话循环
        
        这个方法提供了一个完整的命令行交互界面，用户可以通过
        输入问题与智能体进行对话。
        
        Raises:
            KeyboardInterrupt: 用户按Ctrl+C中断
            EOFError: 输入流结束
            Exception: 其他处理异常
        """
        cli_logger = logging.getLogger("agent.cli")
        cli_logger.info("下一代智能体已启动！")
        
        # 打印欢迎信息
        self._print_welcome_message()
        
        while True:
            try:
                cli_logger.info("等待用户输入问题")
                print("\n" + "-"*40)
                query = input("🧑 您: ").strip()
        
                # 检查退出命令
                if self._should_exit(query):
                    cli_logger.info("用户选择退出")
                    print("👋 感谢使用，再见！")
                    break
                
                # 检查空输入
                if not query:
                    cli_logger.warning("空输入")
                    print("⚠️ 请输入一些内容")
                    continue
                    
                # 处理用户查询
                await self._handle_user_query(query)
                    
            except KeyboardInterrupt:
                cli_logger.info("检测到 Ctrl+C，正在退出…")
                print("\n\n👋 检测到 Ctrl+C，正在退出...")
                break
            except EOFError:
                cli_logger.info("检测到输入结束，正在退出…")
                print("\n\n👋 检测到输入结束，正在退出...")
                break
            except Exception as e:
                cli_logger.exception("处理查询时发生错误: %s", e)
                print(f"\n❌ 处理查询时发生错误: {str(e)}")
                print("请重试或输入 'quit' 退出")

    async def chat_loop_v2(self) -> None:
        """
        启动交互式对话循环
        
        这个方法提供了一个完整的命令行交互界面，用户可以通过
        输入问题与智能体进行对话。
        
        Raises:
            KeyboardInterrupt: 用户按Ctrl+C中断
            EOFError: 输入流结束
            Exception: 其他处理异常
        """
        cli_logger = logging.getLogger("agent.cli")
        cli_logger.info("下一代智能体已启动！")
        
        # 打印欢迎信息
        self._print_welcome_message()
        
        while True:
            try:
                cli_logger.info("等待用户输入问题")
                print("\n" + "-"*40)
                query = input("🧑 您: ").strip()
        
                # 检查退出命令
                if self._should_exit(query):
                    cli_logger.info("用户选择退出")
                    print("👋 感谢使用，再见！")
                    break
                
                # 检查空输入
                if not query:
                    cli_logger.warning("空输入")
                    print("⚠️ 请输入一些内容")
                    continue
                    
                # 处理用户查询
                await self._handle_user_query_v2(query)
                    
            except KeyboardInterrupt:
                cli_logger.info("检测到 Ctrl+C，正在退出…")
                print("\n\n👋 检测到 Ctrl+C，正在退出...")
                break
            except EOFError:
                cli_logger.info("检测到输入结束，正在退出…")
                print("\n\n👋 检测到输入结束，正在退出...")
                break
            except Exception as e:
                cli_logger.exception("处理查询时发生错误: %s", e)
                print(f"\n❌ 处理查询时发生错误: {str(e)}")
                print("请重试或输入 'quit' 退出")

    def _print_welcome_message(self) -> None:
        """打印欢迎信息"""
        print("\n" + "="*60)
        print("🤖 下一代智能体已启动！")
        print("="*60)
        print("💡 输入您的问题开始对话")
        print("💡 输入 'quit'、'exit' 或 'q' 退出")
        print("💡 按 Ctrl+C 也可以随时退出")
        print("="*60)

    def _should_exit(self, query: str) -> bool:
        """
        检查是否应该退出
        
        Args:
            query: 用户输入的查询
            
        Returns:
            是否应该退出
        """
        exit_commands = ['quit', 'exit', 'q', '退出', '结束']
        return query.lower() in exit_commands

    async def _handle_user_query(self, query: str) -> None:
        """
        处理用户查询并输出响应
        
        Args:
            query: 用户输入的查询
        """
        print("\n🤖 智能体:", end=" ", flush=True)
        
        async for response_chunk in self.process_query(query):
            # 过滤掉工具事件，只显示文本响应
            if not response_chunk.startswith("[[TOOL_EVENT]]"):
                print(response_chunk, end="", flush=True)
                
        print("\n")

    async def _handle_user_query_v2(self, query: str) -> None:
        """
        处理用户查询并输出响应
        
        Args:
            query: 用户输入的查询
        """
        print("\n🤖 智能体:", end=" ", flush=True)
        
        async for response_chunk in self.process_query_v2(query):
            # 过滤掉工具事件，只显示文本响应
            if not response_chunk.startswith("[[TOOL_EVENT]]"):
                print(response_chunk, end="", flush=True)
                
        print("\n")


# 工具注册示例
from pydantic import BaseModel, Field
from tools_agent.toolkit import tool
class SearchArxivArgs(BaseModel):
    keyword: str = Field(..., description="论文关键词")
    max_results: int = Field(..., description="最大返回论文篇数")

@tool
def search_arxiv(args: SearchArxivArgs):
    """基于关键词和论文篇数检索arxiv论文摘要"""
    # 【单一职责原则】【日志系统原则】【可扩展性原则】
    import requests
    import logging

    # 日志记录
    logger = logging.getLogger("tool.search_arxiv")
    logger.info(f"开始检索arxiv论文, 关键词: {args.keyword}")

    # 默认返回论文篇数
    max_results = args.max_results
    try:
        # 构造arXiv API查询
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{args.keyword}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        response = requests.get(url, params=params, timeout=10)
        logger.info(f"arXiv API请求URL: {response.url}")
        if response.status_code != 200:
            logger.error(f"arXiv API请求失败, 状态码: {response.status_code}")
            return {"answer": f"arXiv API请求失败，状态码: {response.status_code}"}

        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            link = entry.find("atom:id", ns).text.strip()
            authors = [author.find("atom:name", ns).text for author in entry.findall("atom:author", ns)]
            authors_str = ", ".join(authors)
            papers.append({
                "title": title,
                "summary": summary,
                "link": link,
                "authors": authors_str
            })

        if not papers:
            logger.info("未检索到相关论文")
            return {"answer": f"未检索到与“{args.keyword}”相关的arXiv论文。"}

        # 组装markdown格式
        md = f"### arXiv论文检索结果（关键词：{args.keyword}）\n\n"
        for idx, paper in enumerate(papers, 1):
            md += f"**{idx}. [{paper['title']}]({paper['link']})**  \n"
            md += f"作者: {paper['authors']}  \n"
            md += f"摘要: {paper['summary']}\n\n"

        logger.info(f"arXiv论文检索成功, 返回{len(papers)}条结果")
        # 操作日志
        print(f"[search_arxiv] 用户关键词: {args.keyword}, 返回{len(papers)}条论文摘要")
        return {"answer": md}
    except Exception as e:
        logger.exception(f"arXiv检索异常: {e}")
        return {"answer": f"arXiv检索失败: {e}"}
        
# 命令行聊天模式函数
async def agent_chat_loop() -> None:
    """
    主函数，启动交互式智能体对话
    
    这个函数初始化智能体配置和实例，然后启动交互式对话循环。
    包含完整的异常处理和资源清理逻辑。
    
    Raises:
        KeyboardInterrupt: 用户手动中断
        Exception: 其他运行时异常
    """

    agent: Optional[EchoAgent] = None  # 确保在finally中可用
    
    # workspaces
    user_id = "ada"
    workspace = "MAS-Data"
    agent_name = "test_agent_v5"
    # conversation_id = "test" 
    main_model = "doubao-seed-1-6-250615"
    tool_model = "doubao-seed-1-6-250615"
    tool_model = "google/gemini-2.5-flash"
    flash_model = "doubao-pro"
    tool_use_example = f"""
    当需要执行代码时，必须参考如下示例：
    {{"tools": ["CodeRunner()"]}}
    """
    user_system_prompt = "你是福余AI团队的Leader，负责拆解任务并分配出去，高效完成目标"

    try:
        # 1. 【配置外置】初始化配置和协调器，使用新的配置管理系统
        config = create_agent_config(
            user_id=user_id,
            main_model=main_model,
            tool_model=tool_model,
            flash_model=flash_model,
            # conversation_id=conversation_id,
            workspace=workspace,
            agent_name=agent_name,
            use_new_config=True,
            user_system_prompt=user_system_prompt,
            tool_use_example=tool_use_example
        )
        agent = EchoAgent(config)
        agent.tool_manager.register_tool_function(search_arxiv)
        # 2. 启动交互式对话循环
        # await agent.chat_loop()
        await agent.chat_loop_v2()

    except KeyboardInterrupt:
        logging.getLogger("agent.cli").info("用户手动退出智能体对话")
        print("\n\n👋 用户手动退出智能体对话")
    except Exception as e:
        logging.getLogger("agent.cli").exception("发生致命错误: %s", e)
        print(f"\n[FATAL ERROR] 发生致命错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 3. 清理资源 - 在事件循环关闭前进行
        logging.getLogger("agent.cli").info("正在关闭智能体…")
        print("\n正在关闭智能体...")
        
        # 额外的延迟，确保所有后台任务完成
        await asyncio.sleep(0.2)
        logging.getLogger("agent.cli").info("智能体已关闭，再见！👋")
        print("智能体已关闭，再见！👋")


# 程序入口点
if __name__ == "__main__":
    """
    程序主入口点
    
    当直接运行此模块时，启动智能体的交互式对话模式。
    包含完整的异常处理和优雅退出逻辑。
    """
    """
    测试问题：
    构建两只股票的虚拟数据，接近真实数据，画出走势图;
    设计电商领域的数据，展示全面的数据分析，图文并茂，让我学习。
    搜索10篇最新的LLM Agent相关的论文并总结创新之处
    """
    try:
        asyncio.run(agent_chat_loop())
    except KeyboardInterrupt:
        logging.getLogger("agent.cli").info("程序被用户中断")
        print("\n👋 程序被用户中断")
    except Exception as e:
        logging.getLogger("agent.cli").exception("程序异常退出: %s", e)
        print(f"\n💥 程序异常退出: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logging.getLogger("agent.cli").info("程序已退出")
        print("程序已退出")

        