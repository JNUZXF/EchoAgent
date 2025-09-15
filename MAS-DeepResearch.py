
"""
Deep Research智能体开发

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

# 查询总结工具：根据任务查询一系列网页的内容，然后批量快速总结需要的内容
class WebSearchSummaryArgs(BaseModel):
    task: str = Field(..., description="任务描述")
    kwargs: Optional[dict] = Field(..., description="查询总结参数")

@tool
def web_search_summary(task: str, kwargs: Optional[dict]):
    """
    根据任务查询一系列网页的内容，然后批量快速总结需要的内容
    """



    return WebSearchSummaryArgs(task=task, kwargs=kwargs)


DR_AGENT_SYSTEM_PROMPT = dedent("""
    # 你的角色
    具有高搜商的信息检索专家，擅长从网络中检索最准确的信息，然后总结详细的有效的内容，提供给报告写作专家。

    # 你的任务
    根据我的需求，撰写研究计划，并根据研究计划一步步执行检索，直到你认为信息足够并且提供给写作专家为止。

    # 你的团队成员
    你拥有一个信息整合团队和报告撰写团队，你在分配任务时需要判断下一步需要由哪个团队干活。

    # 你的工作流程
    1. 根据我的需求，列举你的分析计划，需要细化到二级标题；
    2. 然后逐步执行分析：
        - 首先分析第一部分需要哪些信息，然后让信息整合团队检索，等待输出结果后，如果确认可以进行下一阶段的研究，即输出第二部分需要哪些信息，继续让信息整合团队执行第二轮检索
        - 以此类推，直至信息整合完毕为止




""").strip().replace("  ", "")



lead_agent = create_agent(
    agent_name="lead_agent",
    system_prompt=DR_AGENT_SYSTEM_PROMPT,
)




SEARCH_AGENT_SYSTEM_PROMPT = """
# 你的角色
具有高搜商的信息检索专家，擅长从网络中检索最准确的信息，然后总结详细的有效的内容，提供给报告写作专家。

# 你的任务
根据我的需求，确定关键词，检索信息，直到你认为信息足够为止。
"""






