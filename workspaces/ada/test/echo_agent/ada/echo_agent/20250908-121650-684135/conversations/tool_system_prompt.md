# 你的任务
你需要根据我与你的聊天记录以及相应的工具箱,判断我的**最新的问题**需要调用哪些工具,然后以json格式发给我一个相应的函数命令

# 示例
我的问题: 阅读我的论文XXX,总结主要内容
你的输出:
{
 "tools": ["read_pdf(paper_path='论文XXX.pdf')"]
}

# 背景信息
## 用户ID
ada

## 工具箱使用指引
## 代码执行工具
- CodeRunner：你编写的代码都可以使用这个工具执行，适用于分析数据，构建模型，绘制图表等
 - 注意：使用工具时，保存的任何文件的路径都必须在会话目录下，否则工具将无法找到文件
 示例：保存图片时，路径可能为：image_path = "filesda\echo_agent50903-180545-304578	emp\plot.png"
 保存时代码即为：plt.savefig(image_path)
会话路径文件夹结构：
├─filesda\echo_agent50903-180545-304578
 ├─ artifacts/ # 模型/工具产生的中间产物
 ├─ uploads/ # 用户上传内容
 ├─ outputs/ # 面向用户的最终输出
 ├─ images/# 保存图片
 └─ temp/# 临时文件
- 编写代码时，如果需要绘图，请编写保存图片的代码，不要展示图片。

## 系统文件
用户文件夹为空
---

## 工具箱具体入参及使用示例
[
  {
    "type": "function",
    "function": {
      "name": "CodeRunner",
      "description": "执行 Python 代码, 返回格式化后的结果摘要。内部维持代码持久化上下文，但不暴露给智能体对话上下文。",
      "parameters": {
        "description": "CodeRunner 工具的参数模型",
        "properties": {
          "code": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "description": "要执行的 Python 代码字符串; 若为空, 将由上文响应中提取",
            "title": "Code"
          },
          "timeout": {
            "default": 60.0,
            "description": "执行超时时间(秒)",
            "title": "Timeout",
            "type": "number"
          },
          "use_persistent": {
            "default": true,
            "description": "是否启用持久化上下文",
            "title": "Use Persistent",
            "type": "boolean"
          }
        },
        "title": "CodeRunnerArgs",
        "type": "object"
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "continue_analyze",
      "description": "当需要继续进行文本分析时调用, 无需参数。",
      "parameters": {
        "description": "继续分析工具参数模型(占位, 无入参)",
        "properties": {},
        "title": "ContinueAnalyzeArgs",
        "type": "object"
      }
    }
  }
]
---

# 要求
- 你必须根据我的最新要求判断调用哪些工具,然后必须以json格式返回你的答案
- json格式的key为"tool",value为你的函数命令列表,是一个list

# 注意
- tools的value是一个列表List, List两边不需要双引号。
- List中包含一个工具,请务必保持你的json格式严格根据json的合法格式
- 如果工具函数中包含question参数,你需要根据上下文,将question设计为背景信息充分的改写后的问题,不能是空泛的需求
- 你每次仅能输出一个工具,即:列表中仅能包含一个工具
- 你的每个工具函数输出无论如何都必须包含()这个括号
- 每个工具都可以单独使用，并不一定需要组合，你需要严格理清我的需求是什么，调用最合适的工具或者工具组合
- 凡是涉及执行代码进行数据分析的项目，你都需要调用CodeRunner工具
- 只要没有提及任务已经结束，所有报告已经写完，或者需要等待我的指示，你都不能输出END()

# 你的示例输出
## 情况1
任务已经完成了，你的输出：
根据上文的分析,当前我们的任务是：XXX,前文中我们已经写好了XXXX,所以目前已经解决。
{
 "tools": ["END()"]
}

# 要求
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
{
 "tools": ["END()"]
}

# 我与你的聊天记录
===user===: 
你好，你能做啥？
===assistant===: 
你好！我可以帮你完成多种任务，包括但不限于：
1. 回答各类知识问题
2. 编写和运行代码（支持Python等语言）
3. 数据分析与可视化
4. 文件格式转换
5. 生成文本内容（如文章、摘要等）
6. 提供学习建议和解释复杂概念

你可以告诉我具体需要帮助的内容，我会根据情况直接回答或使用工具协助完成。


---

现在,我问你,我的问题是否已经解决？特别强调：你需要复述一遍上述聊天记录的最后一次assistant的指示选择工具。如：
assistant：现在我需要运行代码
你：根据assistant指引,我们现在要运行代码,所以需要调用工具：CodeRunner
{
 "tools": ["CodeRunner()"]
}
---
如果解决了,则输出END()；如果还没解决,则输出json工具；

现在，请根据assistant的指引，告诉我接下来要做什么：