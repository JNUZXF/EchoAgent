from agent_frame import *

# 命令行聊天模式函数
async def agent_chat_loop() -> None:
    agent: Optional[EchoAgent] = None 
    # workspaces
    user_id = "sam"
    # workspace = "MAS-Data"
    # 模型映射
    model_mapping = {
        "gemini": "google/gemini-2.5-flash",
        "doubao": "doubao-seed-1-6-250615",
        "claude": "anthropic/claude-sonnet-4",
    }

    agent_name = "FinAgentV3"
    conversation_id = "Conversation_FinAgent" 
    main_model = model_mapping["doubao"]
    tool_model = model_mapping["doubao"]
    flash_model = model_mapping["doubao"]
    tool_use_example = f"""
    当需要执行代码时，必须参考如下示例：
    {{"tools": ["CodeRunner()"]}}
    """
    USER_SYSTEM_PROMPT = """
# 你的核心任务
作为财务分析专家，编写python代码，分析财务数据，并给出分析报告。

# 要求
- 首先了解我提供的数据的基础信息，然后再深入到多个指标
- 你的分析必须是多维度的、带丰富表格的，你需要使用plotly画出研报级别的图表
- 你可以一步分析一个模块，直到你认为获取了丰富的数据之后，再开始编写财务分析报告
- 图片输出你需要用markdown格式：![图片标题](图片路径)，需要插入合适的位置

# 分析注意事项
- 你必须首先获取数据的字段名称等后续分析需要的基础信息，再执行深入的数据分析和建模

# 最终报告格式
你最终撰写的报告需要参考如下格式：
```markdown
# 报告标题（根据分析结果自拟，需要展现研报水平）
# 第一章节标题（自拟）
（正文）
## 二级标题
（正文）
### 三级标题
（正文）

# 第二章节标题（自拟）
（正文）
## 二级标题
（正文）
### 三级标题
（正文）
...

# 编写代码质量要求
- 编写高质量、生产级别的代码，必须是模块化、高水平团队级别的代码
- 每次撰写的代码必须是完整的，不能依赖之前写的代码
- 尽可能用函数、类等封装代码

```
"""

    try:
        config = create_agent_config(
            user_id=user_id,
            main_model=main_model,
            tool_model=tool_model,
            flash_model=flash_model,
            conversation_id=conversation_id,
            # workspace=workspace,
            agent_name=agent_name,
            use_new_config=True,
            user_system_prompt=USER_SYSTEM_PROMPT,
            tool_use_example=tool_use_example
        )
        agent = EchoAgent(config)
        agent.tool_manager.register_tool_function(search_arxiv)
        await agent.chat_loop()
        # await agent.chat_loop_v2()

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
    测试问题：
    请全面分析我的数据，然后输出高质量报告
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

        
