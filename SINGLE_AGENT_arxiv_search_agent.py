


from textwrap import dedent
from typing import Optional, List
from agent_frame import *
from pydantic import BaseModel, Field
import arxiv

from tools_agent.builtin_tools import CodeRunner
from tools_agent.toolkit import tool
from utils.academic_search.arxiv_search import *

def create_agent(
    user_id: str = "simmons",
    agent_name: str = "SubAgent",
    workspace: str = None,
    main_model: str = "qwen/qwen3-next-80b-a3b-instruct",
    tool_model: str = "qwen/qwen3-next-80b-a3b-instruct",
    flash_model: str = "doubao-pro",
    conversation_id: str = "Constructing Agent",
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

class ArxivSearchAgentArgs(BaseModel):
    query: str = Field(..., description="论文关键词")
    search_num: int = Field(default=10, description="最大返回论文篇数")
    kwargs: Optional[dict] = Field(default_factory=dict, description="")


@tool
def search_arxiv(args: ArxivSearchAgentArgs):
    """
    你可以搜索Arxiv论文，需要确定关键词和搜索篇数
    """
    searcher = ArxivSearcher()
    
    # 【参数优先级】【可扩展性原则】支持kwargs参数覆盖，kwargs中的参数优先级更高
    kwargs = args.kwargs or {}
    
    # 获取最终参数值，kwargs中的值优先
    final_query = kwargs.get("query", args.query)
    final_search_num = kwargs.get("search_num", args.search_num)
    
    try:
        formatted_info = searcher.get_formatted_papers_info(
            query=final_query,
            search_num=final_search_num
        )
        
        # 【扩展性原则】如果kwargs中有额外的处理需求，可以在这里添加
        if kwargs.get("include_metadata", False):
            # 可以添加额外的元数据信息
            result = {
                "papers": formatted_info,
                "search_params": {
                    "query": final_query,
                    "search_num": final_search_num,
                    "sort_by": arxiv.SortCriterion.Relevance,
                    "sort_order": arxiv.SortOrder.Descending
                },
                "user_id": kwargs.get("user_id"),
                "timestamp": kwargs.get("timestamp")
            }
            return result
        
        return formatted_info
    except Exception as e:
        error_msg = f"搜索arxiv论文时发生错误: {str(e)}"
        return {"error": error_msg}

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
    tool_use_example = "当你需要搜索论文时，调用search_arxiv完成任务"
    user_system_prompt = "你要严格遵守我的指示。"
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
        agent.tool_manager.register_tool_function(search_arxiv)
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


def test():
    """
    测试search_arxiv工具的不同调用方式
    """
    print("=== 测试1：使用基础参数 ===")
    args1 = ArxivSearchAgentArgs(
        query="LLM Agent",
        search_num=5
    )
    result1 = search_arxiv(args1)
    print(f"结果1类型: {type(result1)}")
    
    print("\n=== 测试2：使用kwargs扩展参数 ===")
    args2 = ArxivSearchAgentArgs(
        query="AI Agent",
        search_num=3,
        kwargs={
            "user_id": "simmons",
            "display_conversations": "用户：搜索论文\n我：好的，请稍等。",
            "timestamp": "2025-09-15",
            "include_metadata": True,
            # 也可以通过kwargs覆盖主参数
            "search_num": 8,  # 这会覆盖上面的search_num=3
            "sort_by": "SubmittedDate"
        }
    )
    result2 = search_arxiv(args2)
    print(f"结果2类型: {type(result2)}")
    
    print("\n=== 测试3：Agent调用示例格式 ===")
    # 模拟Agent会传递的参数格式
    import json
    agent_params = {
        "query": "LLM Agent",
        "search_num": 10,
        "kwargs": {
            "user_id": "ada",
            "display_conversations": "===user===:\n搜索10篇最新的LLM Agent相关的论文并总结创新之处\n===assistant===:\n好的，我将使用search_arxiv工具搜索10篇最新的LLM Agent相关论文。请稍等。\n\n"
        }
    }
    
    # 验证这个格式可以被正确解析
    try:
        args3 = ArxivSearchAgentArgs(**agent_params)
        print("✅ Agent参数格式验证成功")
        result3 = search_arxiv(args3)
        print(f"结果3类型: {type(result3)}")
    except Exception as e:
        print(f"❌ Agent参数格式验证失败: {e}")

# 测试异步版本
async def test_async():
    """
    异步测试函数
    """
    print("=== 异步测试 ===")
    args = ArxivSearchAgentArgs(
        query="LLM Agent",
        search_num=2,
        kwargs={
            "user_id": "test_user",
            "timestamp": "2025-09-15"
        }
    )
    result = search_arxiv(args)
    print(f"异步测试结果类型: {type(result)}")
    return result

# 程序入口点
if __name__ == "__main__":
    """
    测试问题：
    搜索5篇最新的Agent相关的论文并总结创新之处
    """
    asyncio.run(agent_chat_loop())



