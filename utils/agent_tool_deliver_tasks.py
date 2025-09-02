# type: ignore

from prompts.fin_agent_prompts import TASK_EXTRACT_PROMPT, TASK_ALLOCATION_PROMPT, COMPANY_ANALYSIS_METHOD_PROMPT
from tools_agent.llm_manager import *
from tools_agent.json_tool import *
import os
import json

class SaveAndDeliverTasks:
    def execute(self, **kwargs):
        """
        首先保存任务；
        然后编写任务分配提示词，分发给子智能体
        """
        display_conversations = kwargs.get("display_conversations")
        userID = kwargs.get("userID")
        stock_name = kwargs.get("stock_name")
        model = kwargs.get("model")
        llm = LLMManager(model) # type: ignore

        plan_save_path = f"{userID}/{stock_name}/plan.md"
        
        prompt = TASK_EXTRACT_PROMPT.format(display_conversations=display_conversations)
        plan_md = ""
        for char in llm.generate_stream(prompt):
            plan_md += char
            print(char, end="", flush=True)
        print()

        # 创建路径
        if not os.path.exists(plan_save_path):
            os.makedirs(os.path.dirname(plan_save_path), exist_ok=True)

        # 保存任务
        with open(plan_save_path, "w", encoding="utf-8") as f:
            f.write(plan_md)
        print(f"任务已保存到{plan_save_path}")

        
        prompt = TASK_ALLOCATION_PROMPT.format(
            COMPANY_ANALYSIS_METHOD_PROMPT=COMPANY_ANALYSIS_METHOD_PROMPT, 
            plan_md=plan_md
        )
        task_allocation_json = ""
        for char in llm.generate_stream(prompt, temperature=0):
            task_allocation_json += char
            print(char, end="", flush=True)
        print()
        task_allocation_json = get_json(task_allocation_json)
        task_allocation_save_path = f"{userID}/{stock_name}/task_allocation.json"
        # 保存prompt到.md
        task_allocation_prompt_save_path = f"{userID}/{stock_name}/task_allocation_prompt.md"
        with open(task_allocation_prompt_save_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        with open(task_allocation_save_path, "w", encoding="utf-8") as f:
            json.dump(task_allocation_json, f)  
        return plan_md, task_allocation_json
