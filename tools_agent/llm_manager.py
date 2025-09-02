"""
支持的模型：
anthropic/claude-3.7-sonnet
anthropic/claude-3.7-sonnet:thinking
anthropic/claude-3.5-haiku-20241022
anthropic/claude-3.5-sonnet
openai/gpt-4o-2024-11-20
openai/gpt-4o-mini

google/gemini-2.0-flash-001
google/gemini-2.5-pro-preview-03-25


"""

from abc import ABC, abstractmethod
import os
from openai import OpenAI
from groq import Groq
from zhipuai import ZhipuAI
import google.generativeai as genai
from dashscope import Generation
from http import HTTPStatus
from typing import Generator, List, Dict, Any, Optional, Callable, Union
import time
from functools import wraps
import threading
import queue
from flask import current_app

from dotenv import load_dotenv
from volcenginesdkarkruntime import Ark

# 加载环境变量
load_dotenv()

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

class StreamBuffer:
    """流式输出缓冲器，提供平滑的逐字输出体验"""
    
    def __init__(self, speed: float = 0.01, batch_size: int = 1):
        """
        初始化流式缓冲器
        
        Args:
            speed: 字符输出的延迟（秒）
            batch_size: 一次输出多少个字符
        """
        self.speed = speed
        self.batch_size = batch_size
        self.buffer = queue.Queue()
        self.stop_event = threading.Event()
        self.output_thread = None
    
    def start(self):
        """启动输出线程"""
        if self.output_thread is None or not self.output_thread.is_alive():
            self.stop_event.clear()
            self.output_thread = threading.Thread(target=self._output_worker)
            self.output_thread.daemon = True
            self.output_thread.start()
    
    def stop(self):
        """停止输出线程"""
        if self.output_thread and self.output_thread.is_alive():
            self.stop_event.set()
            self.output_thread.join(timeout=1.0)
    
    def add_text(self, text: str):
        """添加文本到缓冲区"""
        if not text:
            return
        for char in text:
            self.buffer.put(char)
    
    def _output_worker(self):
        """输出工作线程"""
        while not self.stop_event.is_set():
            # 获取一批字符
            batch = []
            for _ in range(self.batch_size):
                try:
                    char = self.buffer.get(block=True, timeout=0.1)
                    batch.append(char)
                    self.buffer.task_done()
                except queue.Empty:
                    break
            
            # 输出这一批字符
            if batch:
                print(''.join(batch), end='', flush=True)
                time.sleep(self.speed)
            elif self.buffer.empty():
                time.sleep(0.1)  # 缓冲区为空时，短暂休眠

# --- Helper function to get config value ---
def get_api_config(key: str) -> Optional[str]:
    """安全获取API Key/endpoint，优先从Flask应用配置获取，其次从环境变量获取。"""
    value = None
    source = None
    
    try:
        # 1. 首先尝试从Flask app.config获取
        if current_app:
            config_value = current_app.config.get('API_KEYS', {}).get(key)
            if config_value:
                value = config_value
                source = "Flask app.config"
        
    except RuntimeError:
        # Flask应用上下文不可用，这是正常的，当在应用上下文之外使用该函数时
        pass
    except Exception as e:
        print(f"尝试从Flask config获取API Key时出错: {e}")
    
    # 2. 如果从Flask配置未获取到，尝试从环境变量获取
    if not value:
        env_value = os.getenv(key)
        if env_value:
            value = env_value
            source = "环境变量"
    
    # 记录密钥获取结果

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
        self.client = OpenAI(api_key=self.api_key)
        
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
        self.client = ZhipuAI(api_key=self.api_key)
        self.model = model
        
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
        self.client = Groq(api_key=self.api_key)
        self.model = model
        
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
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
        self.model = model
        
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
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        
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
        self.client = OpenAI(
            base_url='http://localhost:11434/v1',
            api_key='ollama'
        )
        
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
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )
        self.model = model
        
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

        if self.is_seed:
            self.client = Ark(
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=self.api_key,
            )
            self.model = model 
        else:
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

            self.client = OpenAI(
                base_url="https://ark.cn-beijing.volces.com/api/v3", 
                api_key=self.api_key
            )
            self.model = self.model_endpoint 
        self.is_doubao = "doubao" in model
        
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
        elif model.startswith(("llama", "mixtral")):
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
        
    def generate_with_buffer(self, question: str, temperature: float = 0.95, 
                         speed: float = 0.01, batch_size: int = 1) -> None:
        """使用缓冲器进行更平滑的流式输出
        
        Args:
            question: 输入的问题
            temperature: 温度参数
            speed: 输出速度（字符间延迟，秒）
            batch_size: 一次输出多少个字符
        """
        buffer = StreamBuffer(speed=speed, batch_size=batch_size)
        buffer.start()
        
        try:
            # 获取标准的流式响应
            response_stream = self.generate_stream(question, temperature)
            
            # 添加到缓冲区
            for chunk in response_stream:
                if chunk:
                    buffer.add_text(chunk)
            
            # 等待缓冲区清空
            while not buffer.buffer.empty():
                time.sleep(0.1)
        finally:
            buffer.stop()
        
        print()  # 最后换行

    def generate_conversation_with_buffer(self, conversations: List[Dict[str, Any]], 
                                     temperature: float = 0.95, 
                                     speed: float = 0.01, 
                                     batch_size: int = 1) -> None:
        """使用缓冲器进行更平滑的对话流式输出
        
        Args:
            conversations: 对话历史
            temperature: 温度参数
            speed: 输出速度（字符间延迟，秒）
            batch_size: 一次输出多少个字符
        """
        buffer = StreamBuffer(speed=speed, batch_size=batch_size)
        buffer.start()
        
        try:
            # 获取标准的流式响应
            response_stream = self.generate_stream_conversation(conversations, temperature)
            
            # 添加到缓冲区
            for chunk in response_stream:
                if chunk:
                    buffer.add_text(chunk)
            
            # 等待缓冲区清空
            while not buffer.buffer.empty():
                time.sleep(0.1)
        finally:
            buffer.stop()
        
        print()  # 最后换行
    
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
        
    def print_char_stream(self, question: str, temperature: float = 0.95, delay: float = 0.01) -> None:
        """打印字符级流式输出，带有打字效果
        
        Args:
            question: 输入的问题
            temperature: 温度参数
            delay: 字符间的延迟（秒）
        """
        char_stream = self.generate_char_stream(question, temperature)
        for char in char_stream:
            print(char, end="", flush=True)
            time.sleep(delay)
        print()  # 最后换行
        
    def print_char_conversation(self, conversations: List[Dict[str, Any]], temperature: float = 0.95, delay: float = 0.01) -> None:
        """打印字符级对话流式输出，带有打字效果
        
        Args:
            conversations: 对话历史
            temperature: 温度参数
            delay: 字符间的延迟（秒）
        """
        char_stream = self.generate_char_conversation(conversations, temperature)
        for char in char_stream:
            print(char, end="", flush=True)
            time.sleep(delay)
        print()  # 最后换行

# 使用示例
if __name__ == "__main__":
    # 示例1：使用缓冲区的平滑输出 (doubao-seed)
    print("\n=== 使用缓冲区的平滑输出示例 (doubao-seed) ===")
    llm_seed = LLMManager("doubao-seed-1-6-250615")
    llm_seed.generate_with_buffer("你好，请做个自我介绍", speed=0.01, batch_size=2)

    # 示例2：使用缓冲区的平滑输出 (gemini)
    print("\n=== 使用缓冲区的平滑输出示例 (gemini) ===")
    llm = LLMManager("gemini-2.0-flash")
    llm.generate_with_buffer("解释一下量子力学的基本原理", speed=0.01, batch_size=2)
    
    # 示例3：字符级流式输出
    print("\n=== 字符级流式输出示例 ===")
    llm = LLMManager("gemini-2.0-flash")
    llm.print_char_stream("简要介绍人工智能的发展历史", delay=0.02)
    
    # 示例4：多轮对话
    print("\n=== 多轮对话示例 ===")
    conversations = [
        {"role": "system", "content": "你是一个专业的科学顾问。"},
        {"role": "user", "content": "解释一下黑洞的霍金辐射"}
    ]
    llm = LLMManager("gemini-2.0-flash")
    llm.print_char_conversation(conversations, delay=0.015) 