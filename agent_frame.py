
"""
智能体主框架
文件路径: agent/agent_frame.py
功能: 根据用户的需求，自主调用工具（1轮/多轮）/直接回答问题
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator

from tools_agent.code_interpreter import extract_python_code
from tools_agent.function_call_toolbox import get_func_name, convert_outer_quotes
from tools_agent.parse_function_call import parse_function_call
from tools_agent.json_tool import get_json
from tools_agent.llm_manager import LLMManager

from utils.code_runner import CodeExecutor
from utils.agent_tool_continue_analyze import ContinueAnalyze

from prompts.agent_prompts import (
    AGENT_SYSTEM_PROMPT,
    AGENT_JUDGE_PROMPT,
    AGENT_INTENTION_RECOGNITION_PROMPT,
    AGENT_TOOLS_GUIDE,
    TOOL_RESULT_ANA_PROMPT
)
from tools_configs import (
    CODE_EXECUTOR_TOOL,
    CONTINUE_ANALYZE_TOOL
)

os.environ["NUMEXPR_MAX_THREADS"] = "32" 

print("AgentCoder模块加载完成")

# --- 配置管理 ---
class AgentConfig:
    """集中管理智能体的所有配置"""
    def __init__(
        self, user_id: str, main_model: str, tool_model: str, flash_model: str, agent_name: str = "agent_coder"
    ):
        self.user_id = user_id
        self.main_model = main_model
        self.tool_model = tool_model
        self.flash_model = flash_model
        self.agent_name = agent_name

        # 获取当前脚本所在目录（agent文件夹）
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 基于agent目录构建路径，确保无论从哪里运行都能找到正确的文件
        self.user_folder = os.path.join(self.agent_dir, "files", self.user_id, self.agent_name)
        print(f"[DEBUG] 子智能体文件夹: {self.user_folder}")
        self.server_config_path = os.path.join(self.agent_dir, "server_config.json")
        
        # 确保路径使用正确的分隔符
        self.user_folder = self.user_folder.replace('\\', '/')
        self.server_config_path = self.server_config_path.replace('\\', '/')

# --- 状态管理: 管理对话历史、显示对话历史、工具判断对话历史、工具判断显示对话历史 ---
class AgentStateManager:
    """管理和持久化智能体的所有状态，包括对话历史和用户文件。"""
    def __init__(self, config: AgentConfig):
        self.config = config
        self.conversations: List[Dict[str, str]] = []
        self.tool_conversations: List[Dict[str, str]] = []
        # 用户看到的信息+AI展示的信息，也是用于判断工具的信息
        self.display_conversations: str = ""
        # 所有的上下文，即包含agent推理需要的所有信息 = 用户看到的信息 + 工具执行的结果 + AI展示的信息，用于给主系统判断信息是否充分，下一步需要做什么
        self.full_context_conversations: str = ""
        os.makedirs(self.config.user_folder, exist_ok=True)
        self.init_conversations()

    def init_conversations(self, system_prompt: str = ""):
        """初始化或重置对话历史 更新系统提示词"""
        self.conversations = [{"role": "system", "content": system_prompt}] if system_prompt else []
        # 保存系统提示词到.md
        with open(f"files/{self.config.user_id}/{self.config.agent_name}/agent_coder_system_prompt.md", "w", encoding="utf-8") as f:
            f.write(system_prompt)

    def add_message(self, role: str, content: str, stream_prefix: str = ""):
        """向对话历史中添加消息"""
        # 检查并处理可能的Base64编码内容
        processed_content = self._decode_if_base64(content)
        
        if role == "user":
            self.display_conversations += f"===user===: \n{processed_content}\n"
            self.full_context_conversations += f"===user===: \n{processed_content}\n"
            self.conversations.append({"role": "user", "content": processed_content})
        elif role == "assistant":
            self.conversations.append({"role": "assistant", "content": processed_content})
            self.display_conversations += f"===assistant===: \n{processed_content}\n"
            self.full_context_conversations += f"===assistant===: \n{processed_content}\n"
        elif role == "tool":
            self.full_context_conversations += f"===tool===: \n{stream_prefix}{processed_content}\n"

    def _decode_if_base64(self, content: str) -> str:
        """检查内容是否为Base64编码，如果是则尝试解码"""
        # 如果内容很短或包含正常文本特征，直接返回
        if len(content) < 50 or any(char in content for char in [' ', '。', '，', '？', '！', '\n']):
            return content
            
        # 检查是否可能是Base64编码（只包含Base64字符集）
        import re
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
        if not base64_pattern.match(content.strip()):
            return content
            
        # 尝试Base64解码
        try:
            import base64
            decoded_bytes = base64.b64decode(content.strip())
            decoded_text = decoded_bytes.decode('utf-8')
            print(f"[DEBUG] 检测到Base64编码内容，已解码为: {decoded_text[:100]}...")
            return decoded_text
        except Exception:
            # 解码失败，返回原内容
            return content

    def get_full_display_conversations(self) -> str:
        return self.display_conversations

    def list_user_files(self, recursive: bool = False) -> str:
        """
        列出用户文件夹中的所有文件，返回格式化的文件列表。
        
        Args:
            recursive (bool): 是否递归列举子文件夹下的所有文件，默认为False（只列举一层）
            
        Returns:
            str: 格式化的文件列表，按文件夹分组显示
        """
        try:
            user_folder = self.config.user_folder
            print(f"[DEBUG] 正在扫描用户文件夹: {user_folder}, 递归模式: {recursive}")
            
            if not os.path.exists(user_folder):
                print(f"[DEBUG] 用户文件夹不存在，正在创建: {user_folder}")
                os.makedirs(user_folder, exist_ok=True)
                return "用户文件夹为空"
            
            # 使用字典来按文件夹分组存储文件
            folder_files = {}
            
            if recursive:
                # 递归遍历所有子文件夹
                for root, dirs, filenames in os.walk(user_folder):
                    if filenames:  # 只记录有文件的文件夹
                        # 计算相对于用户文件夹的路径
                        relative_root = os.path.relpath(root, user_folder).replace('\\', '/')
                        if relative_root == '.':
                            relative_root = '根目录'
                        
                        folder_files[relative_root] = sorted(filenames)
                        print(f"[DEBUG] 文件夹 {relative_root} 包含 {len(filenames)} 个文件")
            else:
                # 只列举当前文件夹下的文件
                filenames = [
                    f for f in os.listdir(user_folder) 
                    if os.path.isfile(os.path.join(user_folder, f))
                ]
                if filenames:
                    folder_files['根目录'] = sorted(filenames)
            
            if not folder_files:
                return "用户文件夹为空"
            
            # 格式化输出
            result_lines = []
            for folder_name, files in sorted(folder_files.items()):
                result_lines.append(f"路径：{folder_name}")
                for file_name in files:
                    result_lines.append(f"- {file_name}")
                result_lines.append("")  # 空行分隔不同文件夹
            
            # 移除最后的空行
            if result_lines and result_lines[-1] == "":
                result_lines.pop()
            
            print(f"[DEBUG] 找到 {sum(len(files) for files in folder_files.values())} 个文件，分布在 {len(folder_files)} 个文件夹中")
            return "\n".join(result_lines)
            
        except Exception as e:
            print(f"[ERROR] 扫描用户文件夹时出错: {e}")
            return f"扫描用户文件夹时出错: {e}"

    def save_all_conversations(self):
        """将所有对话历史保存到文件"""
        try:
            with open(os.path.join(self.config.user_folder, "conversations.json"), "w", encoding="utf-8") as f:
                json.dump(self.conversations, f, ensure_ascii=False, indent=2)
            with open(os.path.join(self.config.user_folder, "display_conversations.md"), "w", encoding="utf-8") as f:
                f.write(self.display_conversations)
            with open(os.path.join(self.config.user_folder, "full_context_conversations.md"), "w", encoding="utf-8") as f:
                f.write(self.full_context_conversations)
            with open(os.path.join(self.config.user_folder, "tool_conversations.json"), "w", encoding="utf-8") as f:
                json.dump(self.tool_conversations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 保存对话历史时出错: {e}")

# --- 工具管理 ---
class LocalToolManager:
    """本地工具的包装器"""
    def __init__(self, tool_instance, execute_method='execute'):
        self.instance = tool_instance
        self.execute_method_name = execute_method

    async def execute(self, **kwargs):
        method = getattr(self.instance, self.execute_method_name)
        # 本地工具可能不是异步的，需要包装
        if asyncio.iscoroutinefunction(method):
            return await method(**kwargs)
        else:
            return method(**kwargs)


class AgentToolManager:
    """统一管理所有工具（本地）"""
    def __init__(self):
        self.local_tools: Dict[str, LocalToolManager] = {}
        self.tool_prompt_config: List[Dict] = []

    def register_local_tool(self, name: str, tool_instance: Any, tool_config_for_prompt: Dict):
        """注册一个本地Python工具"""
        self.local_tools[name] = LocalToolManager(tool_instance)
        self.tool_prompt_config.append(tool_config_for_prompt)

    def get_all_tool_configs_for_prompt(self) -> str:
        """获取所有工具的配置，用于格式化提示词"""
        return json.dumps(self.tool_prompt_config, ensure_ascii=False, indent=2)

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """执行指定工具"""
        if tool_name in self.local_tools:
            return await self.local_tools[tool_name].execute(**kwargs)
        else:
            raise ValueError(f"工具 '{tool_name}' 未找到")


# --- 提示词管理 ---
class AgentPromptManager:
    """负责根据当前状态和工具动态生成提示词"""
    def get_system_prompt(self, files_list: str, **kwargs) -> str:
        return AGENT_SYSTEM_PROMPT.format(
            AGENT_TOOLS_GUIDE=AGENT_TOOLS_GUIDE, 
            files=files_list,
            userID=kwargs.get("userID", ""),
            agent_name=kwargs.get("agent_name", ""),
            current_date=datetime.now().strftime("%Y-%m-%d")
        )

    def get_judge_prompt(self, full_context_conversations: str) -> str:
        return AGENT_JUDGE_PROMPT.format(full_context_conversations=full_context_conversations)

    def get_intention_prompt(self, tool_configs: str, files_list: str, user_id: str, display_conversations: str) -> str:
        return AGENT_INTENTION_RECOGNITION_PROMPT.format(
            tools=tool_configs,
            files=files_list,
            userID=user_id,
            AGENT_TOOLS_GUIDE=AGENT_TOOLS_GUIDE,
            conversation=display_conversations
        )

# --- 核心框架 ---
class EchoAgent:

    def __init__(self, config: AgentConfig, **kwargs):
        self.config = config
        self.user_id = config.user_id
        self.state_manager = AgentStateManager(config)
        self.tool_manager = AgentToolManager()
        self.prompt_manager = AgentPromptManager()

        self.main_llm = LLMManager(config.main_model)
        self.tool_llm = LLMManager(config.tool_model)
        self.flash_llm = LLMManager(config.flash_model)
        # 记录用户问题的次数
        self.question_count = 0
        self._register_local_tools()

        self.STOP_SIGNAL = "END()"

    def _register_local_tools(self):
        """注册所有本地工具"""
        self.tool_manager.register_local_tool("CodeRunner", CodeExecutor(), CODE_EXECUTOR_TOOL)
        self.tool_manager.register_local_tool("continue_analyze", ContinueAnalyze(), CONTINUE_ANALYZE_TOOL)
    
    async def _get_tool_intention(self) -> List[str]:
        self.state_manager.tool_conversations = []
        """使用LLM判断用户的意图，并返回建议的工具列表"""
        prompt = self.prompt_manager.get_intention_prompt(
            tool_configs=self.tool_manager.get_all_tool_configs_for_prompt(),
            files_list=self.state_manager.list_user_files(),
            user_id=self.config.user_id,
            display_conversations=self.state_manager.display_conversations
        )
        self.state_manager.tool_conversations.append({"role": "user", "content": prompt})
        intention_history = [{"role": "user", "content": prompt}]
        
        ans = ""
        for char in self.tool_llm.generate_stream_conversation(intention_history):
            ans += char
        print(f"[INTENTION RAW]: {ans}")
        self.state_manager.tool_conversations.append({"role": "assistant", "content": ans})

        try:
            json_result = get_json(ans)
            if not isinstance(json_result, dict):
                print(f"[ERROR] 解析后的JSON不是一个字典: {json_result}")
                return ["END_CONVERSATION()"]

            tools = json_result.get("tools", ["END_CONVERSATION()"])
            if not isinstance(tools, list):
                print(f"[ERROR] 'tools' 字段不是一个列表: {tools}")
                return ["END_CONVERSATION()"]
            return tools
        except Exception as e:
            print(f"[ERROR] 解析意图JSON时发生未知错误: {e}")
            return ["END_CONVERSATION()"]
 
    async def _agent_reset(self):
        kwargs = {
            "userID": self.user_id,
            "agent_name": self.config.agent_name,
            "current_date": datetime.now().strftime("%Y-%m-%d")
        }
        system_prompt = self.prompt_manager.get_system_prompt(
            files_list=self.state_manager.list_user_files(),
            **kwargs
        )
        self.state_manager.init_conversations(system_prompt)
        judge_prompt = self.prompt_manager.get_judge_prompt(self.state_manager.full_context_conversations)
        # 保存judge_prompt到md文件
        with open(f"files/{self.user_id}/{self.config.agent_name}/judge_prompt.md", "w", encoding="utf-8") as f:
            f.write(judge_prompt)
        self.state_manager.conversations.append({"role": "user", "content": judge_prompt})

    async def process_query(self, question: str) -> AsyncGenerator[str, None]:
        """处理单个用户查询的完整工作流"""
        start_time = datetime.now()
        self.question_count += 1
        self.state_manager.add_message("user", question)

        # 初始化对话状态
        await self._agent_reset()

        initial_response = ""
        for char in self.main_llm.generate_stream_conversation(self.state_manager.conversations):
            initial_response += char
            yield char
        yield "\n"
        self.state_manager.add_message("assistant", initial_response)

        # 获取工具调用意图
        intention_tools = await self._get_tool_intention()
        last_agent_response = initial_response

        # 工具调用循环
        while self.STOP_SIGNAL not in intention_tools:
            try:
                if not intention_tools:
                    print("[ERROR] 意图工具列表为空，退出循环。")
                    break
                
                tool_call_str = intention_tools[0]
                func_name = get_func_name(convert_outer_quotes(tool_call_str))

                if func_name == self.STOP_SIGNAL:
                    break

                # 添加类型检查以修复linter错误
                if not isinstance(func_name, str):
                    print(f"[ERROR] 无法从'{tool_call_str}'中解析出有效的工具名称，跳过。")
                    continue

                # 解析参数
                try:
                    params = parse_function_call(tool_call_str)["params"]
                except Exception as e:
                    print(f"[ERROR] 解析工具参数失败: {e}")
                    params = {}

                # 如果是CodeRunner，代码从上一次的回复中提取
                if func_name == "CodeRunner":
                    params["code"] = extract_python_code(last_agent_response)
                
                # 执行工具
                self.params = params
                print(f"[DEBUG] 执行工具: {func_name}")
                tool_result = await self.tool_manager.execute_tool(func_name, **params)
                print(f"[DEBUG] 工具 '{func_name}' 返回结果长度: {len(str(tool_result))}")
                self.state_manager.add_message("tool", str(tool_result), stream_prefix=f"工具{func_name}返回结果:")
                # 根据工具结果生成下一步响应
                self.state_manager.add_message("user", TOOL_RESULT_ANA_PROMPT)
                # 新增聊天记录并重置聊天轮数
                await self._agent_reset()
                next_response = ""
                for char in self.main_llm.generate_stream_conversation(self.state_manager.conversations):
                    next_response += char
                    yield char
                yield "\n"
                self.state_manager.add_message("assistant", next_response)
                last_agent_response = next_response
                # 获取下一个意图
                intention_tools = await self._get_tool_intention()
                tool_call_str = intention_tools[0]
                print(f"[DEBUG] 下一个意图: {tool_call_str}")
                self.state_manager.save_all_conversations()

                await self._agent_reset()
            except Exception as loop_error:
                print(f"[ERROR] 工具循环中发生错误: {loop_error}")
                break
        
        # 结束和清理
        self.state_manager.save_all_conversations()
        end_time = datetime.now()
        print(f"[DEBUG] 流程处理完成，耗时: {(end_time - start_time).total_seconds():.2f}秒")

    async def chat_loop(self):
        """启动交互式对话循环"""
        print("\n" + "="*60)
        print("🤖 下一代智能体已启动！")
        print("="*60)
        print("💡 输入您的问题开始对话")
        print("💡 输入 'quit'、'exit' 或 'q' 退出")
        print("💡 按 Ctrl+C 也可以随时退出")
        print("="*60)
        
        while True:
            try:
                print("\n" + "-"*40)
                query = input("🧑 您: ").strip()
        
                if query.lower() in ['quit', 'exit', 'q', '退出', '结束']:
                    print("👋 感谢使用，再见！")
                    break
                
                if not query:
                    print("⚠️ 请输入一些内容")
                    continue
                    
                print("\n🤖 智能体:", end=" ", flush=True)
                async for response_chunk in self.process_query(query):
                    print(response_chunk, end="", flush=True)
                print("\n")
                    
            except KeyboardInterrupt:
                print("\n\n👋 检测到 Ctrl+C，正在退出...")
                break
            except EOFError:
                print("\n\n👋 检测到输入结束，正在退出...")
                break
            except Exception as e:
                print(f"\n❌ 处理查询时发生错误: {str(e)}")
                print("请重试或输入 'quit' 退出")


# 命令行聊天模式
async def agent_chat_loop():
    """主函数，启动交互式智能体对话"""
    agent = None  # 确保在finally中可用

    try:
        # 1. 初始化配置和协调器
        config = AgentConfig(
            user_id="ada",
            main_model="doubao-pro",
            tool_model="doubao-pro",
            flash_model="doubao-pro"
        )
        agent = EchoAgent(config)

        # 2. 启动交互式对话循环
        await agent.chat_loop()

    except KeyboardInterrupt:
        print("\n\n👋 用户手动退出智能体对话")
    except Exception as e:
        print(f"\n[FATAL ERROR] 发生致命错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 3. 清理资源 - 在事件循环关闭前进行
        print("\n正在关闭智能体...")
        
        
        # 额外的延迟，确保所有后台任务完成
        await asyncio.sleep(0.2)
        print("智能体已关闭，再见！👋")


if __name__ == "__main__":

    try:
        asyncio.run(agent_chat_loop())
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
    except Exception as e:
        print(f"\n💥 程序异常退出: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("程序已退出") 


