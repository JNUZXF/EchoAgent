
# 执行代码
CODE_EXECUTOR_TOOL = {
    "type": "function",
    "function": {"name": "CodeRunner", "description": "执行代码"},
    "description": "当需要执行代码的时候，使用此工具",
    "example": '''
    AI指引：我将尝试运行代码...
    你的输出：CodeRunner()
    '''
}


# ContinueAnalyze()
CONTINUE_ANALYZE_TOOL = {
    "type": "function",
    "function": {"name": "continue_analyze", "description": "当需要继续进行文本分析的时候，调用这个工具"},
    "parameters": {
        "type": "object",
    },
    "example": '''
    用户问题：继续分析
    你的输出：continue_analyze()
    ```json
    {{
        "tools": ["continue_analyze()"]
    }}
    '''
}


