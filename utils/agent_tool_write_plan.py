"""
agent/utils/agent_tool_write_plan.py
智能体写作计划工具

功能：为研究报告生成章节计划
路径：agent/utils/agent_tool_write_plan.py
"""

import sys
import os
import re
from pathlib import Path
from typing import Optional
import asyncio
from textwrap import dedent

# 添加项目根目录到Python路径
current_dir = Path(__file__).resolve().parent
agent_dir = current_dir.parent
project_root = agent_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(agent_dir))

# 现在可以安全导入项目模块
from tools_agent.llm_manager import LLMManager
from config.write_plan_config import WritePlanAgentConfig

class MethodologyManager:
    """方法论管理器 - 负责读取研究方法论文件"""
    
    def __init__(self, agent_dir: Path):
        self.methodology_path = agent_dir / "研究报告方法论" / "公司研究方法论-分章节"
        
    def get_method_by_chapter(self, chapter_num: int) -> Optional[str]:
        """根据章节号获取对应的方法论内容"""
        method_files = {
            1: "1. 公司概况.md",
            2: "2. 行业分析.md", 
            3: "3. 公司深度分析.md",
            4: "4. 财务分析.md",
            5: "5. 多维度估值体系.md",
            6: "6. 风险分析.md"
        }
        
        if chapter_num not in method_files:
            return None
            
        md_path = self.methodology_path / method_files[chapter_num]
        
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"⚠️  警告：方法论文件不存在: {md_path}")
            return None
        except Exception as e:
            print(f"❌ 错误：读取方法论文件失败: {e}")
            return None

def get_method_by_chapter(CHAPTER_NUM):
    """向后兼容的函数"""
    manager = MethodologyManager(agent_dir)
    return manager.get_method_by_chapter(CHAPTER_NUM)

SUMMARIZE_PLAN_PROMPT = dedent("""
    你是一个经验丰富的研究员，请你完整总结下面的聊天记录中提及的报告撰写方法，以markdown格式输出
    
    # 聊天记录
    {tool_judge_display_conversations}

   # 大纲撰写格式注意事项
   ## 大纲格式
   撰写大纲时，参考格式：
      # 1. XXX； （注释，引用了方法论中的什么内容）
      ## 1.1. XXX
      ...
   - 每一个二级标题下面都需要有明确的数据来源、分析分析方法
   - 每个一级标题下方都必须要有明确的输出要求、关键图标，让其他成员可以快速理解你的分析思路
   - 每个一级标题右侧都需要说明是参考了方法论的什么内容

    # 你的输出
    必须以```markdown开头，以```markdown结尾

    现在，请开始：
    
""").strip()

class WritePlanExecutor:
    """写作计划执行器 - 负责执行具体的计划生成任务"""
    
    def __init__(self):
        self.methodology_manager = MethodologyManager(agent_dir)
    
    async def execute(self, user_id: str, chapter_num: int, model: str, 
                     demand: str, stock_name: str) -> str:
        """执行写作计划生成任务"""
        
        # 使用延迟导入避免循环依赖
        from write_plan_agent import WritePlanAgentOrchestrator
        
        # 1. 获取方法论内容
        method = self.methodology_manager.get_method_by_chapter(chapter_num)
        if method is None:
            raise ValueError(f"无法获取第{chapter_num}章的方法论内容")
        folder_path = f"files/{user_id}/{stock_name}/write_plan_agent"
        print(f"计划保存路径：folder_path: {folder_path}")
        # 2. 确保输出文件夹存在
        Path(folder_path).mkdir(parents=True, exist_ok=True)
        
        # 3. 配置智能体
        config = WritePlanAgentConfig(
            user_id=user_id,
            main_model=model,
            tool_model=model,
            flash_model=model,
            method=method,
            save_file_path=folder_path
        )
        
        # 4. 初始化智能体
        write_plan_agent = WritePlanAgentOrchestrator(config)
        # await write_plan_agent.initialize()
        
        print(f"--- 用户问题: {demand} ---")
        
        # 5. 处理查询
        try:
            async for response_chunk in write_plan_agent.process_query(demand):
                print(response_chunk, end="", flush=True)
        except Exception as e:
            print(f"\n❌ 处理查询时发生错误: {e}")
            raise
        
        # 6. 获取对话记录并总结计划
        tool_judge_display_conversations = write_plan_agent.state_manager.get_full_tool_judge_display_conversations()
        
        # 7. 用正则提取最终的```markdown```内容
        final_plan = re.search(r"```markdown\n(.*)```", tool_judge_display_conversations, re.DOTALL).group(1)

        print("="*100)
        print(final_plan)
        print("\n--- 任务完成 ---")
        
        # 8. 保存计划
        save_plan_path = Path(folder_path) / f"{stock_name}_chapter_{chapter_num}.md"
        try:
            with open(save_plan_path, "w", encoding="utf-8") as f:
                f.write(final_plan)
            print(f"--- 计划保存到: {save_plan_path} ---")
        except Exception as e:
            print(f"❌ 保存计划文件时发生错误: {e}")
            raise
        
        return final_plan

class WritePlan:
    """写作计划工具类 - 对外提供统一接口"""
    
    def __init__(self):
        self.executor = WritePlanExecutor()
    
    async def execute(self, **kwargs) -> str:
        """执行写作计划生成
        
        Args:
            userID: 用户ID
            CHAPTER_NUM: 章节号
            model: 使用的模型
            demand: 用户需求
            folder_path: 保存路径
            
        Returns:
            生成的最终计划内容
        """
        required_params = ["userID", "CHAPTER_NUM", "model", "demand", "stock_name"]
        
        # 参数验证
        for param in required_params:
            if param not in kwargs:
                raise ValueError(f"缺少必需参数: {param}")
        print(f"准备执行计划，相关参数：kwargs: {kwargs}")
        return await self.executor.execute(
            user_id=kwargs["userID"],
            chapter_num=kwargs["CHAPTER_NUM"],
            model=kwargs["model"],
            demand=kwargs["demand"],
            stock_name=kwargs["stock_name"]
        )

class write_plan:
    """向后兼容的类"""
    
    @staticmethod
    async def execute(**kwargs):
        executor = WritePlan()
        return await executor.execute(**kwargs)

# 向后兼容的实例
write_plan_instance = WritePlan()

async def main():
    """主函数 - 用于测试和演示"""
    # 配置参数
    config = {
        "userID": "sam",
        "stock_name": "双鹭药业",
        "CHAPTER_NUM": 1,
        "model": "google/gemini-2.5-flash",
    }
    
    # 构建路径
    user_files_path = agent_dir / "files" / config["userID"]
    save_agent_files_path = user_files_path / config["stock_name"] / "write_plan_agent"
    
    # 执行参数
    kwargs = {
        "userID": config["userID"],
        "CHAPTER_NUM": config["CHAPTER_NUM"],
        "model": config["model"],
        "demand": f"深入分析{config['stock_name']}这家公司",
        "stock_name": config["stock_name"],
    }
    
    try:
        await write_plan.execute(**kwargs)
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return

if __name__ == "__main__":
    # 直接运行脚本
    asyncio.run(main())

