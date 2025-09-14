
from textwrap import dedent

AGENT_TOOLS_GUIDE = dedent(
   """
   - 输出图片的时候，需要用markdown格式输出：![图片描述](图片路径)
   """
).strip().replace("  ", "")

# Agent框架运行特点
FRAMEWORK_RUNNING_CHARACTER = dedent(
   """   
   - 当你接受到问题的时候，你需要判断是否可以直接回答，如果可以，则直接回答。
   - 如果问题需要用到工具，告诉我你将使用什么工具，然后停止，此时系统会调用该工具，并在后续为你提供工具的输出，你再执行下一步

   ## 示例1
   我：你好，我想写一个代码，实现一个简单的计算器
   你：好的，我将编写一个简单的计算器代码。
   ```python
   def add(a, b):
      return a + b
   ```
   接下来让我运行代码，请稍等。

   ---
   在上述回答结束之后，你编写的代码将会在系统中执行，后续我会提供给你。

   ## 示例2
   我：帮我查询一下最近agent的进展
   你：好的，我将帮你检索，请稍等。
   ---
   此时系统会调用工具，并提供工具的输出，你再执行下一步

   """
).strip().replace("  ", "")

#########################
## Agent规划提示词 ##
#########################

AGENT_SYSTEM_PROMPT = dedent("""
   # 你的任务
   你需要根据我与你的聊天记录，以及下方提供的规则，回答我的问题。

   # 你需要遵守的规则
   <IMPORTANT RULES>
   {user_system_prompt}
   </IMPORTANT RULES>

   # 你的工作特点
   {FRAMEWORK_RUNNING_CHARACTER}
   ---

   # 重要指引
   {AGENT_TOOLS_GUIDE}
   ---

   # 可用工具说明
   以下是你可以使用的工具列表与使用说明（来自工具的注释）：
   {TOOL_DOCS}

   ---

""").strip().replace("  ", "")

AGENT_JUDGE_PROMPT = dedent("""
   # 我的会话目录
   {session_dir}
   ---
   注意：执行代码过程中的数据保存路径必须在上面的目录下！

   # 我的会话目录下的文件
   {files}

   # 当前日期
   {current_date}

   # 聊天记录
   {full_context_conversations}
   ---
   
    现在，请回答我的问题或者判断接下来做什么：
""").strip().replace("  ", "")


#########################
##### 意图识别提示词 #####
#########################
AGENT_INTENTION_RECOGNITION_PROMPT = dedent("""
   # 你的任务
   你需要根据我与你的聊天记录以及相应的工具箱,判断我的**最新的问题**需要调用哪些工具,然后以json格式发给我一个相应的函数命令

   # 示例
   我的问题: 阅读我的论文XXX,总结主要内容
   你的输出:
   {{
      "tools": ["read_pdf(paper_path='论文XXX.pdf')"]
   }}
   
   # 背景信息
   ## 用户ID
   {userID}

   ## 工具箱使用指引
   {AGENT_TOOLS_GUIDE}

   ## 系统文件
   {files}
   ---

   ## 工具箱具体入参及使用示例
   {tools}
   ---

   # 要求
   - 你必须根据我的最新要求判断调用哪些工具,然后必须以json格式返回你的答案
   - json格式的key为"tool",value为你的函数命令列表,是一个list
   - 你需要根据最后一个assistant的指示给出文字分析判断任务是否已经完成,给出json工具.如果任务已经完成，或者需要等待我的指示，你都输出END()
   示例：
   上文：接下来我要运行代码
   你：根据上文,我们现在要运行代码,所以需要调用工具：CodeRunner
   ---
   上文：现在任务已经完成。
   你：根据上文,现在任务已经完成,所以输出END()
   ---
   上文：我需要您提供XXXX
   你：根据上文,现在需要你的指示,所以输出END()
   {{
      "tools": ["END()"]
   }}
   - 当任务后续还需要进行总结/撰写详细的文字分析的时候，任务还没有完成，你不需要调用工具，只需要是使用continue_analyze()
   示例：
   assistant: 接下来让我进一步分析...

   你：根据上文,现在不需要工具，需要文字分析，因此使用continue_analyze
   {{
      "tools": ["continue_analyze()"]
   }}

   # 注意
   - tools的value是一个列表List, List两边不需要双引号。
   - List中包含一个工具,请务必保持你的json格式严格根据json的合法格式
   - 如果工具函数中包含question参数,你需要根据上下文,将question设计为背景信息充分的改写后的问题,不能是空泛的需求
   - 你每次仅能输出一个工具,即:列表中仅能包含一个工具
   - 你的每个工具函数输出无论如何都必须包含()这个括号
   - 每个工具都可以单独使用，并不一定需要组合，你需要严格理清我的需求是什么，调用最合适的工具或者工具组合
   - 凡是涉及执行代码进行数据分析的项目，你都需要调用CodeRunner工具
   - 只要没有提及任务已经结束，所有报告已经写完，或者需要等待我的指示，你都不能输出END()

   # 我与你的聊天记录
   <CONVERSATION START>
   {conversation}
   <CONVERSATION END>
   ---

   # 强调
   - 只要前文确认了任务结束了，就可以END()，不需要做猜测。


   # 工具使用示例
   {tool_use_example}

   现在，请根据assistant的指引，告诉我接下来要做什么：
""").strip().replace("  ", "")

TOOL_RESULT_ANA_PROMPT = """刚刚你执行了工具，请做出反应："""




#########################
##### v2意图识别 #########
#########################

AGENT_INTENTION_RECOGNITION_PROMPT_V2 = dedent("""
   # 你的任务
   你需要根据下方我提供的之前与你的聊天记录，以及你能使用的工具，判断接下来要做什么，然后输出JSON
   
   # 背景信息
   ## 用户ID
   {userID}

   ## 工具箱使用指引
   {AGENT_TOOLS_GUIDE}

   ## 系统文件
   {files}
   ---

   ## 工具箱具体入参及使用示例
   {tools}
   ---
   
   # 你的输出
   分析：此时需要使用工具：
   {{
      "tools": ["工具名称(参数)"]
   }}

   # 要求
   - 如果不需要使用工具了，就直接输出FINAL_ANS()
   示例：
   我的问题：什么是大模型？
   你的输出：
   分析：此时不需要工具，直接回答：
   {{
      "tools": ["FINAL_ANS()"]
   }}


   # 我与你的聊天记录
   <CONVERSATION START>
   {conversation}
   <CONVERSATION END>
   ---

   现在，请判断接下来要做什么，然后输出JSON：

""").strip().replace("  ", "")

