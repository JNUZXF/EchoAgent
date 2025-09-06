"""
示例：单文件定义并注册一个简单工具并运行智能体
文件路径: example_external_tool.py
功能: 1) 定义 @tool 工具 word_count 2) 演示如何注册到 EchoAgent 并发起一次对话请求
"""

import asyncio
from typing import Dict
from pydantic import BaseModel, Field

from tools_agent.toolkit import tool
from agent_frame import EchoAgent, AgentConfig


class WordCountArgs(BaseModel):
    """统计给定文本的词数与字符数"""
    text: str = Field(..., description="要统计的文本内容")


@tool
def word_count(args: WordCountArgs) -> Dict[str, int]:
    """统计文本中的字符数与空白分隔的“词”数量"""
    text = args.text.strip()
    words = [w for w in text.split() if w]
    return {"char_count": len(text), "word_count": len(words)}


async def main() -> None:
    # 1) 初始化智能体配置
    config = AgentConfig(
        user_id="demo_user",
        main_model="doubao-seed-1-6-250615",
        tool_model="doubao-pro",
        flash_model="doubao-pro",
        agent_name="echo_agent",
    )

    # 2) 创建智能体并注册自定义工具
    agent = EchoAgent(config)
    agent.tool_manager.register_tool_function(word_count)

    # 3) 触发一次对话(演示流式打印)。
    # 提示模型优先考虑调用我们刚注册的 word_count 工具。
    user_query = (
        "请帮我统计以下文本的词数和字符数，并使用 word_count 工具执行: \n"
        "Life is short, I use Python."
    )

    print("\n>>> Streaming answer start\n")
    async for chunk in agent.process_query(user_query):
        print(chunk, end="", flush=True)
    print("\n\n>>> Streaming answer end\n")


if __name__ == "__main__":
    asyncio.run(main())


