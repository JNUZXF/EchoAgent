
"""
MAS 大系统设计

子智能体：多次检索直到获取最准确的信息并总结详细的内容
主智能体设计多个角度输出多个子智能体并行/串行执行，每个智能体任务完成就由主智能体审核，不通过就继续编写。
主智能体拆解任务为TASK_1/TASK_2/...


最终肯定需要分成多个垂直行业的团队，分别构建各个领域需要的数据，提供给到团队。
可能还会需要更上一层的，选择对应行业团队的智能体。

"""
from agent_frame import *

from textwrap import dedent
from pydantic import BaseModel, Field
from tools_agent.toolkit import tool

# 分配任务工具
class DelegateTaskArgs(BaseModel):
    tasks: dict = Field(..., description="任务字典，key是角色，value是任务描述及对应的角色需要输出的内容")
    kwargs: dict = Field(..., description="分配任务参数，可选")

# 细化任务输出
class RefineTaskArgs(BaseModel):
    # 这里实际上是提示词优化过程
    task: str = Field(..., description="任务描述")
    kwargs: dict = Field(..., description="细化任务参数")

# 团队开始工作
class StartTeamArgs(BaseModel):
    team_config: dict = Field(..., description="团队配置")
    kwargs: dict = Field(..., description="开始团队工作参数")



LEADER_SYSTEM_PROMPT = dedent("""
    # 你的角色
    顶尖团队的领导，擅长拆解任务，分配任务给合适的角色。

    # 你的任务
    分析我交给你的任务，判断可以拆成哪几个独立的部分，然后列出分析计划以及对应负责任务的角色。

    # 你的工作流程
    1. 全面分析我的任务，判断：
        - 有哪些影响因素
        - 为了输出高质量结果，需要做哪些准备工作
        - 需要用到哪些工具
        - 完成任务需要用到的方法论
    2. 输出一个详细的分析计划，分点列出。
    3. 最终输出团队的配置。

    ## 团队配置输出要求
    每一个成员的配置都哦必须要有明确解决的问题、需要输出的内容、以及需要用到的工具。
    比如：在电商选品过程中，你最终确定需要的角色：市场数据分析专家和产品经理/选品专员

""").strip().replace("  ", "")



lead_agent = create_agent(
    agent_name="lead_agent",
    system_prompt=LEADER_SYSTEM_PROMPT,
    tools=[DelegateTaskArgs, RefineTaskArgs, StartTeamArgs],
    kwargs={},
)




SEARCH_AGENT_SYSTEM_PROMPT = """
# 你的角色
具有高搜商的信息检索专家，擅长从网络中检索最准确的信息，然后总结详细的有效的内容，提供给报告写作专家。

# 你的任务
根据我的需求，确定关键词，检索信息，直到你认为信息足够为止。
"""






