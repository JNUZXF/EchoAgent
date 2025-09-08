"""
智能体主框架
文件路径: agent/agent_frame.py
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

from utils.code_runner import CodeExecutor, extract_python_code
from utils.agent_tool_continue_analyze import ContinueAnalyze
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


class AgentConfig:
    """
    集中管理智能体的所有配置
    
    这个类负责管理智能体运行所需的所有配置参数，包括用户信息、
    模型配置、文件路径等。
    
    Attributes:
        user_id: 用户唯一标识符
        conversation_id: 对话会话ID，可选
        main_model: 主要LLM模型名称
        tool_model: 工具判断LLM模型名称  
        flash_model: 快速响应LLM模型名称
        agent_name: 智能体名称
        agent_dir: 智能体根目录路径
        user_folder: 用户文件存储目录
        server_config_path: 服务器配置文件路径
    """
    
    def __init__(
        self, 
        user_id: str, 
        main_model: str, 
        tool_model: str, 
        flash_model: str, 
        agent_name: str = "echo_agent", 
        conversation_id: Optional[str] = None,
        workspace: Optional[str] = None,
        user_system_prompt: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        初始化智能体配置
        
        Args:
            user_id: 用户唯一标识符
            main_model: 主要对话模型名称
            tool_model: 工具意图判断模型名称
            flash_model: 快速响应模型名称
            agent_name: 智能体名称，默认为"echo_agent"
            conversation_id: 对话会话ID，可选
            workspace: 工作空间名称，可选，默认为"default"
            user_system_prompt: 用户系统提示词，可选
            kwargs：其他参数，比如持久化变量
            
        Raises:
            ValueError: 当必需参数为空时抛出
        """
        if not user_id or not main_model or not tool_model or not flash_model:
            raise ValueError("user_id, main_model, tool_model, flash_model 不能为空")
            
        self.user_id = user_id
        self.main_model = main_model
        self.tool_model = tool_model
        self.flash_model = flash_model
        self.agent_name = agent_name
        self.conversation_id = conversation_id
        self.workspace = workspace
        self.user_system_prompt = user_system_prompt
        # 获取当前脚本所在目录（agent文件夹）
        self.agent_dir = Path(__file__).parent.absolute()
        
        # 基于agent目录构建路径，确保无论从哪里运行都能找到正确的文件
        if workspace:
            self.user_folder = self.agent_dir / "workspaces" / self.user_id / workspace / self.agent_name
        else:
            self.user_folder = self.agent_dir / "files" / self.user_id / self.agent_name
        self.server_config_path = self.agent_dir / "server_config.json"
        
        # 确保目录存在
        self.user_folder.mkdir(parents=True, exist_ok=True)
        
        # 记录配置初始化
        config_logger = logging.getLogger("agent.config")
        config_logger.debug(f"智能体配置初始化完成 - 用户: {user_id}, 文件夹: {self.user_folder}")


class AgentStateManager:
    """
    管理和持久化智能体的所有状态
    
    这个类负责管理智能体的所有状态信息，包括对话历史、工具执行记录、
    文件管理等。支持状态的持久化和恢复，确保对话的连续性。
    
    Attributes:
        config: 智能体配置对象
        session: 会话信息对象
        logger: 日志记录器
        conversations: 主要对话历史记录
        tool_conversations: 工具相关对话记录
        display_conversations: 用户可见的对话内容
        full_context_conversations: 包含工具结果的完整对话上下文
        tool_execute_conversations: 工具执行过程记录
    """
    
    def __init__(self, config: AgentConfig) -> None:
        """
        初始化状态管理器
        
        Args:
            config: 智能体配置对象
        """
        self.config = config
        # 向后兼容: 若外部未注入session/logger, 在EchoAgent中会重建
        self.session: Optional[SessionInfo] = None
        self.logger: logging.Logger = logging.getLogger("agent.session")
        
        # 对话历史相关
        self.conversations: ConversationHistory = []
        self.tool_conversations: ConversationHistory = []
        self.display_conversations: str = ""
        self.full_context_conversations: str = ""
        self.tool_execute_conversations: str = ""
        
        # 兼容旧逻辑，仍确保目录存在
        self.config.user_folder.mkdir(parents=True, exist_ok=True)
        
        # 会话文件路径集合占位
        self._conv_files: Dict[str, Any] = {}
        
        # 初始化对话历史
        self.init_conversations()

    def init_conversations(self, system_prompt: str = "") -> None:
        """
        初始化或重置对话历史，更新系统提示词
        
        Args:
            system_prompt: 系统提示词内容
            
        Raises:
            Exception: 写入系统提示词失败时记录异常但不中断流程
        """
        self.conversations = (
            [{"role": "system", "content": system_prompt}] 
            if system_prompt else []
        )
        
        # 保存系统提示词到当前会话(若session存在)
        try:
            if self.session is not None:
                if not self._conv_files:
                    self._conv_files = file_manager.conversation_files(self.session)
                self._conv_files["system_prompt"].write_text(
                    system_prompt, encoding="utf-8"
                )
        except Exception as e:
            self.logger.exception("写入系统提示词失败: %s", e)

    def restore_from_session_files(self) -> None:
        """
        从会话目录恢复历史对话可视与全量上下文，便于跨请求续聊
        
        恢复的内容包括：
        - display_conversations: 用户与助手可见的汇总（用于展示）
        - full_context_conversations: 包含工具结果在内的全量上下文（用于主系统判断）
        - tool_conversations: 工具意图评估与记录
        - conversations: 原始对话列表
        
        Raises:
            Exception: 恢复过程中的异常会被捕获并记录，但不会中断流程
        """
        try:
            if self.session is None:
                return
                
            if not self._conv_files:
                self._conv_files = file_manager.conversation_files(self.session)

            conv_paths = self._conv_files
            
            # 恢复 display_conversations
            try:
                display_path = conv_paths["display"]
                if display_path.exists():
                    self.display_conversations = display_path.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.debug("恢复display_conversations失败: %s", e)

            # 恢复 full_context_conversations
            try:
                full_path = conv_paths["full"]
                if full_path.exists():
                    self.full_context_conversations = full_path.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.debug("恢复full_context_conversations失败: %s", e)

            # 恢复 tool_conversations
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

            # 可选：恢复 conversations 列表
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
                
        except Exception as e:
            self.logger.exception("恢复历史会话失败: %s", e)

    def add_message(
        self, 
        role: str, 
        content: str, 
        stream_prefix: str = ""
    ) -> None:
        """
        向对话历史中添加消息
        
        Args:
            role: 消息角色 ("user", "assistant", "tool", "react")
            content: 消息内容
            stream_prefix: 流式输出的前缀信息
            
        Raises:
            ValueError: 当role不在支持的角色列表中时抛出
        """
        if role not in ["user", "assistant", "tool", "react"]:
            raise ValueError(f"不支持的消息角色: {role}")
            
        # 检查并处理可能的Base64编码内容
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
        """添加用户消息"""
        formatted_content = f"===user===: \n{content}\n"
        self.display_conversations += formatted_content
        self.full_context_conversations += formatted_content
        self.tool_execute_conversations += formatted_content
        self.conversations.append({"role": "user", "content": content})

    def _add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self.conversations.append({"role": "assistant", "content": content})
        formatted_content = f"===assistant===: \n{content}\n"
        self.display_conversations += formatted_content
        self.full_context_conversations += formatted_content

    def _add_tool_message(self, content: str, stream_prefix: str) -> None:
        """添加工具消息"""
        formatted_content = f"===tool===: \n{stream_prefix}{content}\n"
        self.full_context_conversations += formatted_content

    def _add_react_message(self, content: str, stream_prefix: str) -> None:
        """添加反思消息"""
        formatted_content = f"===react===: \n{stream_prefix}{content}\n"
        self.full_context_conversations += formatted_content

    def _decode_if_base64(self, content: str) -> str:
        """
        检查内容是否为Base64编码，如果是则尝试解码
        
        Args:
            content: 待检查的内容
            
        Returns:
            解码后的文本内容或原始内容
        """
        # 如果内容很短或包含正常文本特征，直接返回
        if len(content) < 50 or any(char in content for char in [' ', '。', '，', '？', '！', '\n']):
            return content
            
        # 检查是否可能是Base64编码（只包含Base64字符集）
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        if not base64_pattern.match(content.strip()):
            return content
            
        # 尝试Base64解码
        try:
            decoded_bytes = base64.b64decode(content.strip())
            decoded_text = decoded_bytes.decode('utf-8')
            self.logger.debug(f"检测到Base64编码内容，已解码为: {decoded_text[:100]}...")
            return decoded_text
        except Exception:
            # 解码失败，返回原内容
            return content

    def get_full_display_conversations(self) -> str:
        """
        获取完整的显示对话内容
        
        Returns:
            完整的可显示对话历史
        """
        return self.display_conversations

    def list_user_files(self, recursive: bool = False) -> str:
        """
        列出用户文件夹中的所有文件，返回格式化的文件列表
        
        Args:
            recursive: 是否递归列举子文件夹下的所有文件，默认为False（只列举一层）
            
        Returns:
            格式化的文件列表，按文件夹分组显示
            
        Raises:
            Exception: 扫描文件夹时的异常会被捕获并记录
        """
        try:
            # 优先扫描当前会话目录
            user_folder = (
                Path(self.session.session_dir) 
                if self.session is not None 
                else self.config.user_folder
            )
            
            self.logger.debug(
                f"正在扫描会话/用户文件夹: {user_folder}, 递归模式: {recursive}"
            )
            
            if not user_folder.exists():
                self.logger.debug(f"会话/用户文件夹不存在，正在创建: {user_folder}")
                user_folder.mkdir(parents=True, exist_ok=True)
                return "用户文件夹为空"
            
            # 使用字典来按文件夹分组存储文件
            folder_files: Dict[str, List[str]] = {}
            
            if recursive:
                folder_files = self._scan_files_recursive(user_folder)
            else:
                folder_files = self._scan_files_single_level(user_folder)
            
            if not folder_files:
                return "用户文件夹为空"
            
            return self._format_file_list(folder_files)
            
        except Exception as e:
            self.logger.exception("扫描用户文件夹时出错: %s", e)
            return f"扫描用户文件夹时出错: {e}"

    def _scan_files_recursive(self, user_folder: Path) -> Dict[str, List[str]]:
        """递归扫描文件夹"""
        folder_files: Dict[str, List[str]] = {}
        
        for root, dirs, filenames in os.walk(str(user_folder)):
            if filenames:  # 只记录有文件的文件夹
                # 计算相对于用户文件夹的路径
                relative_root = os.path.relpath(root, str(user_folder)).replace('\\', '/')
                if relative_root == '.':
                    relative_root = '根目录'
                
                folder_files[relative_root] = sorted(filenames)
                self.logger.debug(f"文件夹 {relative_root} 包含 {len(filenames)} 个文件")
                
        return folder_files

    def _scan_files_single_level(self, user_folder: Path) -> Dict[str, List[str]]:
        """扫描单层文件夹"""
        folder_files: Dict[str, List[str]] = {}
        
        filenames = [
            f.name for f in user_folder.iterdir() 
            if f.is_file()
        ]
        
        if filenames:
            folder_files['根目录'] = sorted(filenames)
            
        return folder_files

    def _format_file_list(self, folder_files: Dict[str, List[str]]) -> str:
        """格式化文件列表输出"""
        result_lines: List[str] = []
        
        for folder_name, files in sorted(folder_files.items()):
            result_lines.append(f"路径：{folder_name}")
            for file_name in files:
                result_lines.append(f"- {file_name}")
            result_lines.append("")  # 空行分隔不同文件夹
        
        # 移除最后的空行
        if result_lines and result_lines[-1] == "":
            result_lines.pop()
        
        total_files = sum(len(files) for files in folder_files.values())
        total_folders = len(folder_files)
        
        self.logger.debug(f"找到 {total_files} 个文件，分布在 {total_folders} 个文件夹中")
        
        return "\n".join(result_lines)

    def save_all_conversations(self) -> None:
        """
        将所有对话历史保存到文件
        
        Raises:
            Exception: 保存过程中的异常会被捕获并记录
        """
        try:
            if self.session is not None:
                self._save_with_session()
            else:
                self._save_without_session()
        except Exception as e:
            self.logger.exception("保存对话历史时出错: %s", e)

    def _save_with_session(self) -> None:
        """使用会话保存对话历史"""
        if not self._conv_files:
            self._conv_files = file_manager.conversation_files(self.session)
            
        files_to_save = [
            ("conversations", json.dumps(self.conversations, ensure_ascii=False, indent=2)),
            ("display", self.display_conversations),
            ("full", self.full_context_conversations),
            ("tools", json.dumps(self.tool_conversations, ensure_ascii=False, indent=2)),
            ("tool_execute", self.tool_execute_conversations)
        ]
        
        for file_key, content in files_to_save:
            try:
                self._conv_files[file_key].write_text(content, encoding="utf-8")
            except Exception as e:
                self.logger.error(f"保存{file_key}文件失败: {e}")

    def _save_without_session(self) -> None:
        """不使用会话保存对话历史"""
        files_to_save = [
            ("conversations.json", json.dumps(self.conversations, ensure_ascii=False, indent=2)),
            ("display_conversations.md", self.display_conversations),
            ("full_context_conversations.md", self.full_context_conversations),
            ("tool_conversations.json", json.dumps(self.tool_conversations, ensure_ascii=False, indent=2)),
            ("tool_execute_conversations.md", self.tool_execute_conversations)
        ]
        
        for filename, content in files_to_save:
            try:
                file_path = self.config.user_folder / filename
                file_path.write_text(content, encoding="utf-8")
            except Exception as e:
                self.logger.error(f"保存{filename}文件失败: {e}")


class LocalToolManager:
    """
    本地工具的包装器
    
    这个类用于包装本地工具实例，提供统一的异步执行接口。
    
    Attributes:
        instance: 工具实例对象
        execute_method_name: 执行方法名称
    """
    
    def __init__(self, tool_instance: Any, execute_method: str = 'execute') -> None:
        """
        初始化本地工具管理器
        
        Args:
            tool_instance: 工具实例对象
            execute_method: 执行方法名称，默认为'execute'
        """
        self.instance = tool_instance
        self.execute_method_name = execute_method

    async def execute(self, **kwargs: Any) -> Any:
        """
        执行工具方法
        
        Args:
            **kwargs: 传递给工具方法的参数
            
        Returns:
            工具执行结果
            
        Raises:
            AttributeError: 当工具实例没有指定的执行方法时抛出
        """
        if not hasattr(self.instance, self.execute_method_name):
            raise AttributeError(
                f"工具实例 {type(self.instance).__name__} "
                f"没有方法 {self.execute_method_name}"
            )
            
        method = getattr(self.instance, self.execute_method_name)
        
        # 本地工具可能不是异步的，需要包装
        if asyncio.iscoroutinefunction(method):
            return await method(**kwargs)
        else:
            return method(**kwargs)


class AgentToolManager:
    """
    统一管理所有工具（本地和远程）
    
    这个类负责管理和执行各种类型的工具，包括本地Python工具
    和基于Pydantic的函数工具。
    
    Attributes:
        local_tools: 本地工具字典
        tool_prompt_config: 工具提示配置列表
        registry: 基于Pydantic的工具注册表
    """
    
    def __init__(self) -> None:
        """初始化工具管理器"""
        self.local_tools: Dict[str, LocalToolManager] = {}
        self.tool_prompt_config: List[ToolConfig] = []
        # 新增: 基于Pydantic的工具注册表
        self.registry: ToolRegistry = ToolRegistry()

    def register_local_tool(
        self, 
        name: str, 
        tool_instance: Any, 
        tool_config_for_prompt: ToolConfig
    ) -> None:
        """
        注册一个本地Python工具

        Args:
            name: 工具名称
            tool_instance: 工具实例，比如CodeExecutor()
            tool_config_for_prompt: 工具配置，用于格式化提示词
            
        Raises:
            ValueError: 当工具名称已存在时抛出
        """
        if name in self.local_tools:
            raise ValueError(f"工具 '{name}' 已经注册")
            
        self.local_tools[name] = LocalToolManager(tool_instance)
        self.tool_prompt_config.append(tool_config_for_prompt)

    def register_tool_function(self, func: Callable[..., Any]) -> None:
        """
        注册基于 @tool 装饰的函数工具
        
        Args:
            func: 被@tool装饰的函数
            
        Raises:
            Exception: 注册过程中的异常会被重新抛出
        """
        try:
            self.registry.register(func)
        except Exception as e:
            logging.getLogger("agent.tools").error(f"注册工具函数失败: {e}")
            raise

    def get_all_tool_configs_for_prompt(self) -> str:
        """
        获取所有工具的配置，用于格式化提示词
        
        Returns:
            JSON格式的工具配置字符串
        """
        # 优先返回注册表Schema，若为空再回退到旧配置
        schemas = self.registry.get_schemas_json()
        if schemas and schemas != '[]':
            return schemas
        return json.dumps(self.tool_prompt_config, ensure_ascii=False, indent=2)

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """
        执行指定工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 传递给工具的参数
            
        Returns:
            工具执行结果
            
        Raises:
            ValueError: 当工具未找到时抛出
            Exception: 工具执行过程中的异常会被重新抛出
        """
        # 优先走统一注册表执行
        if self.registry.has(tool_name):
            try:
                return self.registry.execute(
                    tool_name, 
                    json.dumps(kwargs, ensure_ascii=False)
                )
            except Exception as e:
                logging.getLogger("agent.tools").error(
                    f"执行注册表工具 '{tool_name}' 失败: {e}"
                )
                raise
                
        # 回退: 旧的本地工具机制
        if tool_name in self.local_tools:
            try:
                return await self.local_tools[tool_name].execute(**kwargs)
            except Exception as e:
                logging.getLogger("agent.tools").error(
                    f"执行本地工具 '{tool_name}' 失败: {e}"
                )
                raise
        else:
            raise ValueError(f"工具 '{tool_name}' 未找到")

    def list_available_tools(self) -> List[str]:
        """
        列出所有可用的工具名称
        
        Returns:
            可用工具名称列表
        """
        registry_tools = list(self.registry.get_all_tool_names()) if hasattr(self.registry, 'get_all_tool_names') else []
        local_tools = list(self.local_tools.keys())
        return registry_tools + local_tools


class AgentPromptManager:
    """
    负责根据当前状态和工具动态生成提示词
    
    这个类管理智能体所需的各种提示词模板，并根据当前上下文
    动态生成完整的提示词内容。
    """
    
    def get_system_prompt(self, **kwargs: Any) -> str:
        """
        生成系统提示词
        
        Args:
            **kwargs: 用于格式化提示词的参数
            
        Returns:
            格式化后的系统提示词
        """
        user_system_prompt = kwargs.get("user_system_prompt", "")
        try:
            return AGENT_SYSTEM_PROMPT.format(
                AGENT_TOOLS_GUIDE=AGENT_TOOLS_GUIDE, 
                FRAMEWORK_RUNNING_CHARACTER=FRAMEWORK_RUNNING_CHARACTER,
                user_system_prompt=user_system_prompt
            )
        except KeyError as e:
            logging.getLogger("agent.prompt").error(f"系统提示词格式化失败: {e}")
            return AGENT_SYSTEM_PROMPT

    def get_judge_prompt(
        self, 
        full_context_conversations: str, 
        **kwargs: Any
    ) -> str:
        """
        生成判断提示词
        
        Args:
            full_context_conversations: 完整的对话上下文
            **kwargs: 其他格式化参数
            
        Returns:
            格式化后的判断提示词
        """
        try:
            return AGENT_JUDGE_PROMPT.format(
                full_context_conversations=full_context_conversations,
                session_dir=kwargs.get("session_dir", ""),
                files=kwargs.get("files", ""),
                agent_name=kwargs.get("agent_name", ""),
                current_date=datetime.now().strftime("%Y-%m-%d"),
                tools=kwargs.get("tool_configs", "")
            )
        except KeyError as e:
            logging.getLogger("agent.prompt").error(f"判断提示词格式化失败: {e}")
            return AGENT_JUDGE_PROMPT

    def get_intention_prompt(self, **kwargs: Any) -> str:
        """
        生成意图识别提示词
        
        Args:
            **kwargs: 格式化参数
            
        Returns:
            格式化后的意图识别提示词
        """
        try:
            return AGENT_INTENTION_RECOGNITION_PROMPT.format(
                AGENT_TOOLS_GUIDE=AGENT_TOOLS_GUIDE,
                tools=kwargs.get("tool_configs", ""),
                files=kwargs.get("files", ""),
                userID=kwargs.get("user_id", ""),
                conversation=kwargs.get("display_conversations", "")
            )
        except KeyError as e:
            logging.getLogger("agent.prompt").error(f"意图识别提示词格式化失败: {e}")
            return AGENT_INTENTION_RECOGNITION_PROMPT


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
    """

    # 类常量
    STOP_SIGNAL: str = "END()"
    
    def __init__(self, config: AgentConfig, **kwargs: Any) -> None:
        """
        初始化智能体核心框架
        
        Args:
            config: 智能体配置对象
            **kwargs: 其他初始化参数
            
        Raises:
            Exception: 初始化过程中的异常会被记录并重新抛出
        """
        try:
            self.config = config
            self.user_id = config.user_id
            self.conversation_id = config.conversation_id
            
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
            
        except Exception as e:
            logging.getLogger("agent.init").exception("智能体初始化失败: %s", e)
            raise

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
                "tool_configs": self.tool_manager.get_all_tool_configs_for_prompt()
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
                
            self.logger.debug(f"解析出工具列表: {tools}")
            return tools
            
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
            kwargs = {
                "userID": self.user_id,
                "session_dir": str(self.session.session_dir),
                "files": self.state_manager.list_user_files(),
                "agent_name": self.config.agent_name,
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "tool_configs": self.tool_manager.get_all_tool_configs_for_prompt(),
                "user_system_prompt": self.config.user_system_prompt
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
                "开始主模型流式回答", 
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
            self.logger.info(
                "主模型初次回答完成，内容: %s", 
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
                    if isinstance(chunk, str) and "===assistant===" in chunk:
                        current_response = chunk

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
        last_response: str
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

            # 发送工具结果事件
            yield self._create_tool_event("tool_result", func_name, tool_result, "completed")
            
            # 生成基于工具结果的响应
            async for chunk in self._generate_tool_response():
                yield chunk
                
        except Exception as e:
            self.logger.exception("执行工具 '%s' 时发生错误: %s", func_name, e)
            # 发送工具错误事件
            yield self._create_tool_event("tool_error", func_name, str(e), "failed")

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

        # 如果是CodeRunner，代码从上一次的回复中提取
        if func_name == "CodeRunner":
            params["code"] = extract_python_code(last_response)
        
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
            tool_event = {
                "type": event_type,
                "tool_name": tool_name,
                "timestamp": time.time(),
                "status": status
            }
            
            if event_type == "tool_start":
                tool_event.update({
                    "tool_args": data,
                    "content": f"开始调用 {tool_name}"
                })
            elif event_type == "tool_result":
                tool_event.update({
                    "result": data
                })
            elif event_type == "tool_error":
                tool_event.update({
                    "error": data
                })
            
            return f"[[TOOL_EVENT]]{json.dumps(tool_event, ensure_ascii=False)}"
            
        except Exception as e:
            self.logger.debug("工具事件创建失败: %s", e)
            return f"[[TOOL_EVENT]]{{'type': 'error', 'message': 'Event creation failed'}}"

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

    try:
        # 1. 初始化配置和协调器
        config = AgentConfig(
            user_id="ada",
            main_model="doubao-seed-1-6-250615",
            tool_model="doubao-pro",
            flash_model="doubao-pro"
        )
        agent = EchoAgent(config)

        # 2. 启动交互式对话循环
        await agent.chat_loop()

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

        