"""
支持的模型：
# Claude
anthropic/claude-sonnet-4

# OpenAI
openai/gpt-4o-2024-11-20
openai/gpt-4o-mini

# Gemini
google/gemini-2.5-flash
google/gemini-2.5-pro

# 通义千问
qwen/qwen3-next-80b-a3b-instruct
qwen/qwen3-max

# 美团
meituan/longcat-flash-chat

# 豆包
doubao-seed-1-6-250615

openrouter/sonoma-sky-alpha

"""

from abc import ABC, abstractmethod
import os
from typing import Generator, List, Dict, Any, Optional, Callable
import time
from functools import wraps

def retry_generator(max_retries: int = 3, delay: float = 1.0):
    """
    用于生成器函数的重试装饰器
    
    Args:
        max_retries (int): 最大重试次数
        delay (float): 重试之间的延迟时间（秒）
        
    Returns:
        Generator: 返回一个生成器对象
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Generator:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    yield from func(*args, **kwargs)
                    return  # 如果成功完成，直接返回
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:  # 如果不是最后一次尝试
                        time.sleep(delay)
                        continue
                    else:
                        yield f"\n[错误] 生成失败: {str(e)}"  # 在最后一次失败时输出错误信息
                        raise last_exception
            
        return wrapper
    return decorator

# 火山引擎模型端点配置
ARK_MODEL_ENDPOINTS = {
    "deepseek-v3": "DEEPSEEK_V3_ENDPOINT",
    "doubao-pro": "DOUBAO_PRO_ENDPOINT",
    "doubao-pro-256k": "DOUBAO_1_5_PRO_256K_ENDPOINT",
    "doubao-1.5-lite": "DOUBAO_1_5_LITE_32K_ENDPOINT",
}


# --- Helper function to get config value ---
def get_api_config(key: str) -> Optional[str]:
    """安全获取API Key/endpoint，优先从Flask应用配置获取，其次从环境变量获取。"""
    value = None
    
    try:
        # 1. 首先尝试从Flask app.config获取（懒加载Flask）
        try:
            from flask import current_app
            if current_app:
                config_value = current_app.config.get('API_KEYS', {}).get(key)
                if config_value:
                    value = config_value
        except (ImportError, RuntimeError):
            # Flask不可用或应用上下文不可用，这是正常的
            pass
        except Exception as e:
            print(f"尝试从Flask config获取API Key时出错: {e}")
        
        # 2. 如果从Flask配置未获取到，尝试从环境变量获取
        if not value:
            # 懒加载dotenv
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass
            
            env_value = os.getenv(key)
            if env_value:
                value = env_value
    
    except Exception as e:
        print(f"获取API配置时出错: {e}")
        # 最后尝试直接从环境变量获取
        value = os.getenv(key)

    return value

class BaseLLMProvider(ABC):
    """所有LLM提供者的基类"""
    
    @abstractmethod
    @retry_generator(max_retries=3, delay=1.0)
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        """单轮对话流式生成"""
        pass
    
    @abstractmethod
    @retry_generator(max_retries=3, delay=1.0)
    def generate_stream_conversation(self, conversations: List[Dict[str, Any]], temperature: float = 0.95) -> Generator[str, None, None]:
        """多轮对话流式生成"""
        pass
    
    def char_level_stream(self, generator: Generator[str, None, None]) -> Generator[str, None, None]:
        """将模型的块级响应转换为字符级的流式响应
        
        这个方法会将任何LLM Provider返回的块级响应拆分为单个字符，以获得更平滑的输出体验。
        
        Args:
            generator: 原始块级生成器
            
        Yields:
            str: 单个字符
        """
        for chunk in generator:
            if not chunk:
                continue
            # 一个字符一个字符地产出
            for char in chunk:
                yield char

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model: str):
        self.api_key = get_api_config('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API Key not found in configuration.")
        self.model = model
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": question}
            ],
            stream=True,
            temperature=temperature
        )
        for chunk in completion:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
                
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=conversations, # type: ignore
            stream=True,
            temperature=temperature
        ) # type: ignore
        for chunk in completion:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class ZhipuProvider(BaseLLMProvider):
    def __init__(self, model: str):
        self.api_key = get_api_config('ZHIPU_API_KEY')
        if not self.api_key:
            raise ValueError("Zhipu API Key not found in configuration.")
        self.model = model
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from zhipuai import ZhipuAI
            self._client = ZhipuAI(api_key=self.api_key)
        return self._client
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        response = self.client.chat.completions.create( # type: ignore
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个人工智能助手"},
                {"role": "user", "content": question}
            ],
            stream=True,
            temperature=temperature
        )
        for chunk in response:
            if chunk.choices[0].delta.content: # type: ignore
                yield chunk.choices[0].delta.content # type: ignore
                
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        response = self.client.chat.completions.create( # type: ignore
            model=self.model,
            messages=conversations, # type: ignore
            stream=True,
            temperature=temperature
        )
        for chunk in response:
            if chunk.choices[0].delta.content: # type: ignore
                yield chunk.choices[0].delta.content # type: ignore

class GroqProvider(BaseLLMProvider):
    def __init__(self, model: str):
        self.api_key = get_api_config('GROQ_API_KEY')
        if not self.api_key:
             raise ValueError("Groq API Key not found in configuration.")
        self.model = model
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        completion = self.client.chat.completions.create( # type: ignore
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": question}
            ],
            model=self.model,
            temperature=temperature,
            stream=True
        )
        for chunk in completion:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content # type: ignore
                
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        completion = self.client.chat.completions.create(
            messages=conversations, # type: ignore
            model=self.model,
            temperature=temperature,
            stream=True
        )
        for chunk in completion:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content # type: ignore

class DeepseekProvider(BaseLLMProvider):
    def __init__(self, model: str):
        self.api_key = get_api_config('DEEPSEEK_API_KEY')
        if not self.api_key:
             raise ValueError("Deepseek API Key not found in configuration.")
        self.model = model
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
        return self._client
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": question}
            ],
            stream=True,
            temperature=temperature
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content # type: ignore
                
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=conversations, # type: ignore
            stream=True,
            temperature=temperature
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content # type: ignore

class GeminiProvider(BaseLLMProvider):
    def __init__(self, model: str):
        self.api_key = get_api_config('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API Key not found in configuration.")
        self.model = model
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
        return self._client
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": question}
            ],
            temperature=temperature,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content # type: ignore
            
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        # 转换conversations格式以适配OpenAI API格式
        messages = []
        for conv in conversations:
            messages.append({
                "role": conv["role"],
                "content": conv["content"]
            })
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content # type: ignore

class QwenProvider(BaseLLMProvider):
    def __init__(self, model: str):
        self.api_key = get_api_config('QWEN_API_KEY')
        if not self.api_key:
            raise ValueError("Qwen API Key not found in configuration.")
        self.model = model
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        from dashscope import Generation
        from http import HTTPStatus
        responses = Generation.call(
            self.model,
            messages=[{'role': 'user', 'content': question}], # type: ignore
            result_format='message',
            stream=True,
            incremental_output=True,
            api_key=self.api_key, # type: ignore
            temperature=temperature
        )
        for response in responses:
            if response.status_code == HTTPStatus.OK:
                yield response.output.choices[0]['message']['content'] # type: ignore
                
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        from dashscope import Generation
        from http import HTTPStatus
        responses = Generation.call(
            self.model,
            messages=conversations, # type: ignore
            result_format='message',
            stream=True,
            incremental_output=True,
            api_key=self.api_key, # type: ignore
            temperature=temperature
        )
        for response in responses:
            if response.status_code == HTTPStatus.OK:
                yield response.output.choices[0]['message']['content'] # type: ignore

class OllamaProvider(BaseLLMProvider):
    """Ollama开源模型提供者"""
    def __init__(self, model: str):
        self.model = model.split("/")[-1]
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url='http://localhost:11434/v1',
                api_key='ollama'
            )
        return self._client
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个人工智能助手，请尽可能详细全面地回答问题。"},
                {"role": "user", "content": question}
            ],
            stream=True,
            temperature=temperature
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content # type: ignore
                
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=conversations, # type: ignore
            stream=True,
            temperature=temperature
        )
        for chunk in response:
            if chunk.choices[0].delta.content: # type: ignore
                yield chunk.choices[0].delta.content # type: ignore 

class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API提供者，支持OpenAI、Anthropic和Google等模型"""
    def __init__(self, model: str):
        self.api_key = get_api_config('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OpenRouter API Key not found in configuration.")
        self.model = model
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key
            )
        return self._client
        
    @retry_generator(max_retries=3, delay=2.0)  # 增加重试次数和延迟时间
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": question}
                ],
                stream=True,
                temperature=temperature,
                max_tokens=2000000 if "claude" in self.model else 131072
            )
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"OpenRouter API调用失败: {str(e)}")
            raise  # 重新抛出异常以触发重试机制
                
    @retry_generator(max_retries=3, delay=2.0)  # 增加重试次数和延迟时间
    def generate_stream_conversation(self, conversations: List[Dict[str, str]], temperature: float = 0.95) -> Generator[str, None, None]:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=conversations, # type: ignore
                stream=True,
                temperature=temperature
            )
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"OpenRouter API调用失败: {str(e)}")
            raise  # 重新抛出异常以触发重试机制

class ArkProvider(BaseLLMProvider):
    """火山引擎Ark API提供者，支持Deepseek和豆包模型"""
    def __init__(self, model: str):
        self.api_key = get_api_config('DOUBAO_API_KEY')
        if not self.api_key:
            raise ValueError("Doubao (Ark) API Key not found in configuration.")

        self.original_model_name = model 
        self.is_seed = "seed" in model 
        self._client = None

        if not self.is_seed:
            endpoint_key_map = {
                "deepseek-v3": "DEEPSEEK_V3_ENDPOINT",
                "doubao-pro": "DOUBAO_PRO_ENDPOINT",
                "doubao-1.5-lite-32k": "DOUBAO_1_5_LITE_32K_ENDPOINT",
                "doubao-1.5-pro-256k": "DOUBAO_1_5_PRO_256K_ENDPOINT",
                "doubao-1.5-thinking-pro": "DOUBAO_1_5_THINKING_PRO_ENDPOINT",
                "doubao-1.5-thinking-pro-256k": "DOUBAO_1_5_THINKING_PRO_256K_ENDPOINT",
            }
            endpoint_key = endpoint_key_map.get(model)
            self.model_endpoint = get_api_config(endpoint_key) if endpoint_key else None
            if not self.model_endpoint:
                 print(f"Endpoint for Ark model '{model}' (key: {endpoint_key}) not found in config. Using model name as endpoint.")
                 self.model_endpoint = model
            self.model = self.model_endpoint 
        else:
            self.model = model 
        self.is_doubao = "doubao" in model
        
    @property
    def client(self):
        if self._client is None:
            if self.is_seed:
                from volcenginesdkarkruntime import Ark
                self._client = Ark(
                    base_url="https://ark.cn-beijing.volces.com/api/v3",
                    api_key=self.api_key,
                )
            else:
                from openai import OpenAI
                self._client = OpenAI(
                    base_url="https://ark.cn-beijing.volces.com/api/v3", 
                    api_key=self.api_key
                )
        return self._client
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        if self.is_seed:
            system_content = "你需要仔细全面回答我的问题。"
            conversations: List[Dict[str, Any]] = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": [{"type": "text", "text": question}]}
            ]
        else:
            system_content = "你是豆包，是由字节跳动开发的 AI 人工智能助手" if self.is_doubao else "你需要尽可能全面地回答我的问题"
            conversations = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": question}
            ]
        return self.generate_stream_conversation(conversations, temperature)
                
    def generate_stream_conversation(self, conversations: List[Dict[str, Any]], temperature: float = 0.95) -> Generator[str, None, None]:
        if self.is_seed:
            stream = self.client.chat.completions.create(
                model=self.original_model_name,
                messages=conversations, # type: ignore
                stream=True,
                temperature=temperature,
                thinking={"type":"disabled"}, # type: ignore
                top_p=0.7, 
                max_tokens=16384
            )
        else:
            stream = self.client.chat.completions.create(
                model=self.model, 
                messages=conversations, # type: ignore
                stream=True,
                temperature=temperature 
            )

        for chunk in stream:
            if not chunk.choices: # type: ignore
                continue
            delta = chunk.choices[0].delta # type: ignore
            reasoning = getattr(delta, 'reasoning_content', None)
            content = getattr(delta, 'content', None)
            
            if reasoning:
                yield reasoning
            if content:
                yield content
        yield "\n"

class LLMFactory:
    """LLM工厂类，负责创建不同的LLM提供者实例"""
    
    @staticmethod
    def create_provider(model: str) -> BaseLLMProvider:
        if model.startswith(("gpt", "chatgpt")):
            return OpenAIProvider(model)
        elif model.startswith("glm"):
            return ZhipuProvider(model)
        elif model.startswith(("groq#")):
            model = model.split("#")[-1]
            return GroqProvider(model)
        elif model.startswith("deepseek-v3") or model.startswith("deepseek-r1"): 
            return ArkProvider(model)
        elif model.startswith("doubao-"):
            return ArkProvider(model)
        elif model.startswith("deepseek-chat"):
            return DeepseekProvider(model)
        elif model.startswith("gemini"):
            return GeminiProvider(model)
        elif model.startswith("opensource/"):
            return OllamaProvider(model)
        elif model.startswith(("openai/", "anthropic/", "google/", "openrouter/", "moonshotai/", "qwen/", "z-ai")):
            return OpenRouterProvider(model)
        else:
            raise ValueError(f"Unsupported model: {model}")

class LLMManager:
    """
    LLM管理类，负责与不同的LLM提供者交互
    可使用的模型：
    - doubao-seed-1-6-250615
    - google/gemini-2.5-flash
    """
    
    def __init__(self, model: str):
        self.model = model
        self.provider = LLMFactory.create_provider(model)
        
    def generate_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        return self.provider.generate_stream(question, temperature)
    
    def generate_stream_conversation(self, conversations: List[Dict[str, Any]], temperature: float = 0.5) -> Generator[str, None, None]:
        return self.provider.generate_stream_conversation(conversations, temperature)
           
    def generate_char_stream(self, question: str, temperature: float = 0.95) -> Generator[str, None, None]:
        """生成字符级的流式响应，每次只产出一个字符
        
        Args:
            question: 输入的问题
            temperature: 温度参数
            
        Returns:
            生成器，每次产出一个字符
        """
        # 获取原始流
        response_stream = self.generate_stream(question, temperature)
        # 使用Provider基类提供的字符级处理
        return self.provider.char_level_stream(response_stream)
        
    def generate_char_conversation(self, conversations: List[Dict[str, Any]], temperature: float = 0.95) -> Generator[str, None, None]:
        """生成字符级的对话流式响应，每次只产出一个字符
        
        Args:
            conversations: 对话历史
            temperature: 温度参数
            
        Returns:
            生成器，每次产出一个字符
        """
        # 获取原始流
        response_stream = self.generate_stream_conversation(conversations, temperature)
        # 使用Provider基类提供的字符级处理
        return self.provider.char_level_stream(response_stream)
        
# 使用示例
if __name__ == "__main__":
    # 简单测试
    llm = LLMManager("gemini-2.5-flash")
    response = llm.generate_stream("你好")
    for chunk in response:
        print(chunk, end='', flush=True) 