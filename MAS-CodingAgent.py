
"""

测试由一个智能体调用Coding Agent完成任务的MAS系统

"""

from agent_frame import *

from textwrap import dedent
from pydantic import BaseModel, Field
from tools_agent.toolkit import tool
from tools_agent.builtin_tools import CodeRunner


def create_agent(
    user_id: str = "simmons",
    agent_name: str = "SubAgent",
    workspace: str = None,
    main_model: str = "qwen/qwen3-next-80b-a3b-instruct",
    tool_model: str = "qwen/qwen3-next-80b-a3b-instruct",
    flash_model: str = "doubao-pro",
    conversation_id: str = "ConstructingAgent",
    user_system_prompt: str = "简单问题直接回答，复杂问题请拆解多个步骤，逐步完成。",
    tool_use_example: str = "",
    code_runner_session_id: str = "code_runner_session_id",
    enable_mcp: bool = False,
    mcp_config_path: str = "custom_server_config.json",
) -> EchoAgent:
    try:
        config = create_agent_config(
            user_id=user_id,
            main_model=main_model,
            tool_model=tool_model,
            flash_model=flash_model,
            conversation_id=conversation_id,
            workspace=workspace,
            agent_name=agent_name,
            use_new_config=True,
            user_system_prompt=user_system_prompt,
            tool_use_example=tool_use_example,
            code_runner_session_id=code_runner_session_id,
            enable_mcp=enable_mcp, 
            mcp_config_path=mcp_config_path,  
        )
        agent = EchoAgent(config)
        
        return agent
    except Exception as e:
        print(f"⚠️ 初始化失败: {e}")
        return None

class CodingAgentArgs(BaseModel):
    kwargs: dict = Field(..., description="代码任务参数")


CODING_AGENT_TASK_PROMPT = dedent("""
    # 你的任务
    你正在帮我完成一个编程任务，请你根据以下我跟你的对话，完成任务。

    # 我跟你的对话
    {contexts}

    # 我的任务
    {task}
    """
).strip().replace("  ", "")

CODING_AGENT_RESULT_SUMMARY_PROMPT = dedent("""
    请你将我下面的聊天记录总结成两个关键信息：代码和运行结果。

    # 我的聊天记录
    {sub_agent_conversation}

    # 输出格式
    <code>
    这里是最终成功运行的代码
    </code>

    <result>
    这里是代码的运行结果
    </result>
""").strip().replace("  ", "")

@tool
async def coding_agent(**kwargs):
    """
    当需要执行代码任务时，使用这个工具Agent

    输入：
        空，不需要参数
    输出：
        代码及运行结果
    """

    # 日志记录
    logger = logging.getLogger("tool.coding_agent")

    user_id = kwargs.get("user_id", "simmons")
    contexts = kwargs.get("display_conversations", [])
    task = kwargs.get("task", "")
    conversation_id = "test"
    try:
        
        user_system_prompt = CODING_AGENT_TASK_PROMPT.format(contexts=contexts, task=task)
        agent = create_agent(
            user_id=user_id,
            user_system_prompt=user_system_prompt,
            conversation_id=conversation_id,
        )
        agent.tool_manager.register_tool_function(CodeRunner)

        question = "开始吧！"
        async for char in agent.process_query(question, version="v1"):
            print(char, end="", flush=True)

        # 所有的聊天记录
        sub_agent_conversation = agent.state_manager.display_conversations

        # 任务总结 - 用小模型快速总结关键代码及运行结果
        prompt = CODING_AGENT_RESULT_SUMMARY_PROMPT.format(
            sub_agent_conversation=sub_agent_conversation
        )
        llm = LLMManager(model="qwen/qwen3-next-80b-a3b-instruct")
        summary = ""
        for char in llm.generate_char_stream(prompt):
            print(char, end="", flush=True)
            summary += char
        return summary

    except Exception as e:
        logger.exception(f"代码任务执行异常: {e}")


# 命令行聊天模式函数
async def agent_chat_loop(
    version: VersionLiteral = "v1"
) -> None:
    """
    主智能体
    """
    user_id = "ada"
    agent_name = "test_agent_v6"
    # workspace = "MAS-Data"
    # conversation_id = "test" 
    model_mapping_v1 = {
        "main_model": "qwen/qwen3-next-80b-a3b-instruct",
        "tool_model": "qwen/qwen3-next-80b-a3b-instruct",
        "flash_model": "doubao-pro",
    }
    model_mapping_v2 = {
        "main_model": "doubao-seed-1-6-250615",
        "tool_model": "doubao-seed-1-6-250615",
        "flash_model": "doubao-seed-1-6-250615",
    }
    main_model = model_mapping_v2["main_model"]
    tool_model = model_mapping_v2["tool_model"]
    flash_model = model_mapping_v2["flash_model"]
    tool_use_example = ""
    user_system_prompt = "当你需要编程时，调用coding_agent完成任务"
    # code_runner session_id
    code_runner_session_id = "code_runner_session_id"
    try:
        config = create_agent_config(
            user_id=user_id,
            main_model=main_model,
            tool_model=tool_model,
            flash_model=flash_model,
            # conversation_id=conversation_id,
            # workspace=workspace,
            agent_name=agent_name,
            use_new_config=True,
            user_system_prompt=user_system_prompt,
            tool_use_example=tool_use_example,
            code_runner_session_id=code_runner_session_id,
            enable_mcp=False,  # 默认启用MCP，可通过环境变量ENABLE_MCP=false禁用
            # mcp_config_path="custom_server_config.json",  # 可选：自定义MCP配置文件路径
        )
        agent = EchoAgent(config)
        agent.tool_manager.register_tool_function(coding_agent)
        await agent.chat_loop_common(version=version)

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
        
        # 【资源管理】清理MCP连接
        if agent and hasattr(agent, 'tool_manager'):
            try:
                await agent.tool_manager.cleanup_mcp_connections()
            except Exception as cleanup_error:
                logging.getLogger("agent.cli").warning(f"清理MCP连接时发生错误: {cleanup_error}")
        
        # 额外的延迟，确保所有后台任务完成
        await asyncio.sleep(0.2)
        logging.getLogger("agent.cli").info("智能体已关闭，再见！👋")
        print("智能体已关闭，再见！👋")


def test_coding_agent():
    task = "构建两只股票的虚拟数据，接近真实数据，画出走势图"
    kwargs = {
        "task": "构建两只股票的虚拟数据，接近真实数据，画出走势图",
        "user_id": "simmons",
        "display_conversations": """
    用户：你好，我想构建两只股票的虚拟数据，接近真实数据，画出走势图
    我：好的，请稍等。
    """,
    }
    asyncio.run(coding_agent(**kwargs))

# 程序入口点
if __name__ == "__main__":
    """
    测试问题：
    构建两只股票的虚拟数据，接近真实数据，画出走势图;
    设计电商领域的数据，展示全面的数据分析，图文并茂，让我学习。必须使用高级封装代码，比如class等高级抽象
    搜索10篇最新的LLM Agent相关的论文并总结创新之处
    """
    asyncio.run(agent_chat_loop())

