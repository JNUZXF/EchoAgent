"""
智能体配置管理模块
文件路径: config/agent_config.py
功能: 使用Pydantic BaseSettings管理智能体配置，支持环境变量和配置文件

这个模块实现了完整的配置管理功能，包括：
- 基础配置：用户信息、工作空间等
- 模型配置：主模型、工具模型、快速模型
- 性能配置：对话历史限制、令牌限制、超时设置
- 重试配置：重试次数、退避因子
- 路径配置：自动生成文件路径

Author: Your Name
Version: 1.0.0
Date: 2024-01-01
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union

try:
    # Pydantic v2: BaseSettings 在 pydantic-settings 包中
    from pydantic_settings import BaseSettings
    from pydantic import Field, field_validator, model_validator
except ImportError:
    try:
        # Pydantic v1: BaseSettings 在 pydantic 包中  
        from pydantic import BaseSettings, Field, validator as field_validator, root_validator as model_validator
    except ImportError:
        # 如果都无法导入，使用基础实现
        print("警告: 无法导入 pydantic 或 pydantic-settings，将使用基础配置实现")
        BaseSettings = object
        Field = lambda *args, **kwargs: None
        field_validator = lambda *args, **kwargs: lambda func: func
        model_validator = lambda *args, **kwargs: lambda func: func

logger = logging.getLogger("agent.config")


class AgentSettings(BaseSettings):
    """
    【配置外置】【开闭原则】使用Pydantic BaseSettings管理Agent配置
    
    支持通过环境变量和.env文件进行配置，提高部署灵活性。
    所有配置项都有合理的默认值，确保开箱即用。
    """
    
    # ========== 基础配置 ==========
    user_id: str = Field(..., env='AGENT_USER_ID', description="用户唯一标识符")
    agent_name: str = Field('echo_agent', env='AGENT_NAME', description="智能体名称")
    conversation_id: Optional[str] = Field(None, env='CONVERSATION_ID', description="对话会话ID")
    workspace: Optional[str] = Field(None, env='AGENT_WORKSPACE', description="工作空间名称")
    user_system_prompt: Optional[str] = Field(None, env='USER_SYSTEM_PROMPT', description="用户自定义系统提示词")
    tool_use_example: Optional[str] = Field(None, env='TOOL_USE_EXAMPLE', description="工具使用示例提示词")
    code_runner_session_id: Optional[str] = Field(None, env='CODE_RUNNER_SESSION_ID', description="代码执行器会话ID")
    # ========== 模型配置 ==========
    main_model: str = Field('doubao-seed-1-6-250615', env='MAIN_MODEL', description="主要对话模型")
    tool_model: str = Field('doubao-pro', env='TOOL_MODEL', description="工具判断模型")
    flash_model: str = Field('doubao-pro', env='FLASH_MODEL', description="快速响应模型")
    
    # ========== 性能配置 ==========
    max_conversation_history: int = Field(100, env='MAX_HISTORY', description="最大对话历史条数")
    max_tokens_per_conversation: int = Field(8000, env='MAX_TOKENS', description="每次对话最大令牌数")
    tool_execution_timeout: float = Field(30.0, env='TOOL_TIMEOUT', description="工具执行超时时间(秒)")
    
    # ========== 重试配置 ==========
    max_retry_attempts: int = Field(3, env='MAX_RETRIES', description="最大重试次数")
    retry_backoff_factor: float = Field(2.0, env='RETRY_BACKOFF', description="重试退避因子")
    
    # ========== 日志配置 ==========
    log_level: str = Field('INFO', env='LOG_LEVEL', description="日志级别")
    enable_file_logging: bool = Field(True, env='ENABLE_FILE_LOGGING', description="是否启用文件日志")
    log_rotation_size: str = Field('10MB', env='LOG_ROTATION_SIZE', description="日志文件轮转大小")
    
    # ========== 路径配置（运行时计算） ==========
    agent_dir: Optional[Path] = None
    user_folder: Optional[Path] = None
    server_config_path: Optional[Path] = None
    
    class Config:
        """【配置外置】Pydantic配置类，支持环境变量和.env文件"""
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        # 允许额外字段，保持向后兼容
        extra = "allow"
        
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """【单一职责原则】验证用户ID格式"""
        if not v or not v.strip():
            raise ValueError("user_id不能为空")
        if len(v.strip()) < 2:
            raise ValueError("user_id长度至少为2个字符")
        return v.strip()
    
    @field_validator('max_conversation_history')
    @classmethod
    def validate_max_history(cls, v: int) -> int:
        """验证对话历史限制"""
        if v <= 0:
            raise ValueError("max_conversation_history必须大于0")
        if v > 1000:
            logger.warning("max_conversation_history设置过大(%s)，建议不超过1000", v)
        return v
    
    @field_validator('tool_execution_timeout')
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        """验证超时设置"""
        if v <= 0:
            raise ValueError("tool_execution_timeout必须大于0")
        if v > 300:  # 5分钟
            logger.warning("tool_execution_timeout设置过长(%s秒)，建议不超过300秒", v)
        return v
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level必须是{valid_levels}中的一个")
        return v_upper
    
    @model_validator(mode='before')
    @classmethod
    def validate_models(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """【测试策略】验证模型配置的一致性"""
        if isinstance(values, dict):
            main_model = values.get('main_model')
            tool_model = values.get('tool_model')
            flash_model = values.get('flash_model')
            
            if not all([main_model, tool_model, flash_model]):
                raise ValueError("main_model, tool_model, flash_model都必须配置")
            
            # 如果所有模型都一样，给出警告（可能影响性能）
            if main_model == tool_model == flash_model:
                logger.info("所有模型使用相同配置: %s", main_model)
        
        return values
    
    def __init__(self, **data: Any) -> None:
        """【单一职责原则】初始化配置并计算路径"""
        super().__init__(**data)
        self._setup_paths()
        self._ensure_directories()
        logger.debug("AgentSettings初始化完成 - 用户: %s, 工作空间: %s", 
                    self.user_id, self.workspace or "默认")
    
    def _setup_paths(self) -> None:
        """【单一职责原则】设置文件路径"""
        # 获取agent框架根目录（config目录的父目录）
        self.agent_dir = Path(__file__).parent.parent.absolute()
        
        # 设置用户文件夹路径
        if self.workspace:
            self.user_folder = (
                self.agent_dir / "workspaces" / self.user_id / 
                self.workspace / self.agent_name
            )
        else:
            self.user_folder = (
                self.agent_dir / "files" / self.user_id / self.agent_name
            )
        
        # 服务器配置文件路径
        self.server_config_path = self.agent_dir / "server_config.json"
    
    def _ensure_directories(self) -> None:
        """【测试策略】确保必要的目录存在"""
        try:
            if self.user_folder:
                self.user_folder.mkdir(parents=True, exist_ok=True)
                logger.debug("创建用户目录: %s", self.user_folder)
        except Exception as e:
            logger.error("创建用户目录失败: %s", e)
            raise
    
    def get_session_info(self) -> Dict[str, Any]:
        """【开闭原则】获取会话相关信息，便于扩展"""
        return {
            "user_id": self.user_id,
            "agent_name": self.agent_name,
            "conversation_id": self.conversation_id,
            "workspace": self.workspace,
            "user_folder": str(self.user_folder) if self.user_folder else None,
            "agent_dir": str(self.agent_dir) if self.agent_dir else None
        }
    
    def get_model_config(self) -> Dict[str, str]:
        """【单一职责原则】获取模型配置"""
        return {
            "main_model": self.main_model,
            "tool_model": self.tool_model,
            "flash_model": self.flash_model
        }
    
    def get_performance_config(self) -> Dict[str, Union[int, float]]:
        """【单一职责原则】获取性能配置"""
        return {
            "max_conversation_history": self.max_conversation_history,
            "max_tokens_per_conversation": self.max_tokens_per_conversation,
            "tool_execution_timeout": self.tool_execution_timeout,
            "max_retry_attempts": self.max_retry_attempts,
            "retry_backoff_factor": self.retry_backoff_factor
        }
    
    def to_legacy_config(self) -> 'LegacyAgentConfig':
        """【开闭原则】转换为旧版AgentConfig格式，保持向后兼容"""
        return LegacyAgentConfig(
            user_id=self.user_id,
            main_model=self.main_model,
            tool_model=self.tool_model,
            flash_model=self.flash_model,
            agent_name=self.agent_name,
            conversation_id=self.conversation_id,
            workspace=self.workspace,
            user_system_prompt=self.user_system_prompt,
            # 添加新增的配置项
            max_conversation_history=self.max_conversation_history,
            max_tokens_per_conversation=self.max_tokens_per_conversation,
            tool_execution_timeout=self.tool_execution_timeout,
            max_retry_attempts=self.max_retry_attempts,
            retry_backoff_factor=self.retry_backoff_factor,
        )


class LegacyAgentConfig:
    """
    【开闭原则】向后兼容的AgentConfig类
    
    保持与原有代码的兼容性，同时支持新的配置功能。
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
        """【开闭原则】初始化兼容配置，支持额外参数"""
        # 基础配置
        self.user_id = user_id
        self.main_model = main_model
        self.tool_model = tool_model
        self.flash_model = flash_model
        self.agent_name = agent_name
        self.conversation_id = conversation_id
        self.workspace = workspace
        self.user_system_prompt = user_system_prompt
        
        # 新增配置项（带默认值）
        self.max_conversation_history = kwargs.get('max_conversation_history', 100)
        self.max_tokens_per_conversation = kwargs.get('max_tokens_per_conversation', 8000)
        self.tool_execution_timeout = kwargs.get('tool_execution_timeout', 30.0)
        self.max_retry_attempts = kwargs.get('max_retry_attempts', 3)
        self.retry_backoff_factor = kwargs.get('retry_backoff_factor', 2.0)
        
        # 路径配置
        self.agent_dir = Path(__file__).parent.parent.absolute()
        
        if workspace:
            self.user_folder = self.agent_dir / "workspaces" / self.user_id / workspace / self.agent_name
        else:
            self.user_folder = self.agent_dir / "files" / self.user_id / self.agent_name
            
        self.server_config_path = self.agent_dir / "server_config.json"
        
        # 确保目录存在
        self.user_folder.mkdir(parents=True, exist_ok=True)
        
        logger.debug("LegacyAgentConfig初始化完成 - 用户: %s, 文件夹: %s", 
                    user_id, self.user_folder)


def create_agent_config(
    user_id: str,
    main_model: str,
    tool_model: str,
    flash_model: str,
    agent_name: str = "echo_agent",
    conversation_id: Optional[str] = None,
    workspace: Optional[str] = None,
    user_system_prompt: Optional[str] = None,
    use_new_config: bool = True,
    code_runner_session_id: Optional[str] = None,
    **kwargs: Any
) -> Union[AgentSettings, LegacyAgentConfig]:
    """
    建议使用的模型：
    #### Claude
    anthropic/claude-sonnet-4\n  

    #### OpenAI
    openai/gpt-4o-2024-11-20\n    
    openai/gpt-4o-mini\n   

    #### Gemini
    google/gemini-2.5-flash\n   
    google/gemini-2.5-pro\n   

    #### 通义千问
    qwen/qwen3-next-80b-a3b-instruct\n   
    qwen/qwen3-max\n   

    #### 美团
    meituan/longcat-flash-chat\n   

    #### 豆包
    doubao-seed-1-6-250615\n 

    openrouter/sonoma-sky-alpha\n 

    ---
    【工厂模式】创建Agent配置的统一工厂函数
    
    Args:
        user_id: 用户ID
        main_model: 主模型名称
        tool_model: 工具模型名称
        flash_model: 快速模型名称
        agent_name: Agent名称
        conversation_id: 对话ID
        workspace: 工作空间
        user_system_prompt: 用户系统提示词
        use_new_config: 是否使用新版配置（默认True）
        code_runner_session_id: 代码执行器会话ID
        **kwargs: 其他配置参数
        
    Returns:
        配置对象（新版或兼容版）
    """
    config_data = {
        "user_id": user_id,
        "main_model": main_model,
        "tool_model": tool_model,
        "flash_model": flash_model,
        "agent_name": agent_name,
        "conversation_id": conversation_id,
        "workspace": workspace,
        "user_system_prompt": user_system_prompt,
        "code_runner_session_id": code_runner_session_id,
        **kwargs
    }
    
    if use_new_config:
        try:
            return AgentSettings(**config_data)
        except Exception as e:
            logger.warning("创建新版配置失败，回退到兼容版本: %s", e)
            return LegacyAgentConfig(**config_data)
    else:
        return LegacyAgentConfig(**config_data)


def load_config_from_env() -> AgentSettings:
    """
    【配置外置】从环境变量加载配置
    
    Returns:
        从环境变量加载的配置对象
        
    Raises:
        ValueError: 必需的环境变量未设置时
    """
    try:
        return AgentSettings()
    except Exception as e:
        logger.error("从环境变量加载配置失败: %s", e)
        raise ValueError(f"配置加载失败，请检查环境变量设置: {e}")
