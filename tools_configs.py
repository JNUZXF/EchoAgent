

# 处理论文需求          
PROCESS_DEMAND_TOOL = {
    "type": "function",
    "function": {"name": "process_demand", "description": "处理论文需求"},
    "example": '''
    用户：我的写作主题是：the rise of AI agents
    你的输出：save_theme()
    '''
}


# batch_process(requirements)
BATCH_PROCESS_TOOL = {
    "type": "function",
    "function": {"name": "batch_process", "description": "当我的需求涉及批量处理论文的时候，使用这个工具，比如：通读论文找到与方法相关的论文内容、找到所有论文方法论的不同"},
    "parameters": {
        "type": "object",
        "properties": {
            "requirements": {"type": "string", "description": "这里根据我的问题，总结我针对论文的需求，如果有多个需求，分点列举出来"}
        },
    },
    "example": '''
    用户：通读论文找到与方法相关的论文内容
    你的输出：batch_process(requirements='通读论文找到与方法相关的论文内容')
    '''
}


# 论文搜索get_arxiv_papers(keyword, max_results=5, sort_by='relevance')
ARXIV_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "get_arxiv_papers",
        "description": "搜索arXiv上的论文",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，必须是英文，例如：AI, Agents, Reinforcement Learning, etc.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大搜索结果数",
                },
                "sort_by": {
                    "type": "string",
                    "description": "排序方式",
                },
            },
            "required": ["keyword", "max_results", "sort_by"],
        },
    },
    "example": '''
    用户问题：请帮我搜索关于AI的最新论文
    你的输出：
    ```json
    {{
        "tools": ["get_arxiv_papers(keyword='AI', max_results=5, sort_by='relevance')"]
    }}
    '''
}

# chat(question)
CHAT_TOOL = {
    "type": "function",
    "function": {
        "name": "chat",
        "description": "当不需要使用到任何工具，仅仅是根据你的知识即可回答问题的时候调用这个工具",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "用户的问题",
                },
            },
            "required": ["question"],
        },
    },
    "example": '''
    用户问题：你好
    你的输出：chat(question='你好')
    '''
}

# END_CONVERSATION_TOOL
END_CONVERSATION_TOOL = {
    "type": "function",
    "function": {"name": "END()", "description": "当问题已经解决的时候，调用这个工具"},
    "example": '''
    用户问题：至此，问题已经解决，如果还有其他问题，请告诉我
    你的输出：END()
    '''
}


# 阅读pdf文件:read_pdf(pdf_path, chunk_size)
READ_PDF_TOOL = {
    "type": "function",
    "function": {
        "name": "read_pdf",
        "description": "阅读PDF文件并提取文本内容",
        "parameters": {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "PDF文件的完整路径",
                }
            },
            "required": ["pdf_path"],
        },
    },
    "example": '''
    用户问题：请阅读这个PDF文件的内容
    你的输出：read_pdf(pdf_path='agent/KnowledgeBase/2307.04345v3.pdf')
    '''
}


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


# fetch
"""
fetch - Fetches a URL from the internet and extracts its contents as markdown.
url (string, required): URL to fetch
max_length (integer, optional): Maximum number of characters to return (default: 5000)
start_index (integer, optional): Start content from this character index (default: 0)
raw (boolean, optional): Get raw content without markdown conversion (default: false)
"""
FETCH_TOOL = {
    "type": "function",
    "function": {"name": "fetch", "description": "获取网页内容"},
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum number of characters to return (default: 5000)",    
            },
            "start_index": {
                "type": "integer",
                "description": "Start content from this character index (default: 0)",
            },
            "raw": {    
                "type": "boolean",
                "description": "Get raw content without markdown conversion (default: False)",
            },
        },
        "required": ["url"],
    },  
    "example": '''
    用户问题：获取这个网站的全部内容:https://google.com
    你的输出：
    ```json
    {{
        "tools": ["fetch(url='https://google.com', max_length=5000, start_index=0, raw=False)"]
    }}
    ```
    '''
}

"""
write_file - Writes a file to the filesystem.
path (string): File location
content (string): File content
"""
WRITE_FILE_TOOL = {
    "type": "function",
    "function": {"name": "write_file", "description": "写入文件"},
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File location"},
            "content": {"type": "string", "description": "File content"},   
        },
        "required": ["path", "content"],
    },
    "example": '''
    用户问题：将这个内容写入文件:https://google.com
    你的输出：
    ```json
    {{
        "tools": ["write_file(path='path/to/file', content='https://google.com')"]
    }}
    ```
    '''
}



# BochaSearch(keyword, count=10)
BOCHA_SEARCH_TOOL = {
    "type": "function",
    "function": {"name": "bocha_search", "description": "使用BochaSearch搜索信息"},
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词"},
            "count": {"type": "integer", "description": "最大搜索结果数"},
        },
        "required": ["keyword", "count"],
    },
    "example": '''
    用户问题：请帮我搜索关于AI的最新论文
    你的输出：
    ```json
    {{
        "tools": ["bocha_search(keyword='AI', count=10)"]
    }}
    ``` 
    '''
}

# 巨潮搜索
CNINFO_ADVANCED_CRAWLER_TOOL = {
    "type": "function",
    "function": {"name": "cninfo_advanced_crawler", "description": "使用巨潮搜索"},
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词"},
            "max_results": {"type": "integer", "description": "最大搜索结果数"},
        },
        "required": ["keyword", "max_results"],
    },
    "example": '''
    用户问题：请帮我搜索关于腾讯控股的最新业绩报告
    你的输出：
    ```json
    {{
        "tools": ["cninfo_advanced_crawler(keyword='腾讯控股 业绩', max_results=10)"]
    }}
    ```
    '''
}



######################
#####主智能体工具#####
######################

# SaveAndDeliverTasks
SAVE_AND_DELIVER_TASKS_TOOL = {
    "type": "function",
    "function": {"name": "save_and_deliver_tasks", "description": "保存任务并分发给子智能体"},
    "parameters": {
        "type": "object",
    },
    "example": '''
    场景：已经做好计划，可以将任务分发给子智能体的时候调用
    你的输出：
    ```json
    {{
        "tools": ["save_and_deliver_tasks()"]
    }}
    '''
}

# KBSearch(mdvec_path, keywords, top_n)
KB_SEARCH_TOOL = {
    "type": "function",
    "function": {"name": "kb_search", "description": "使用KBSearch搜索上市公司信息"},
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "用户的问题"},
            "keywords": {"type": "array", "description": "关键词列表"},
            "top_n": {"type": "integer", "description": "最大搜索结果数，默认5"},
            "mdvec_path": {"type": "string", "description": "向量数据库保存路径，必须是.pkl文件"},
            "md_path": {"type": "string", "description": "上市公司信息.md文件路径"},
            "keyword_search": {"type": "boolean", "description": "是否使用关键词搜索，默认True"},
        },
        "required": ["query", "keywords", "top_n", "mdvec_path", "md_path"],
    },
    "example": '''
    用户问题：请帮我搜索关于福耀玻璃的财务情况
    你的输出：
    ```json
    {{
        "tools": ["kb_search(query='商汤科技 客户类型 客户集中度', keywords=['客户类型', '客户集中度'], top_n=5, mdvec_path='mdvec_path', md_path='files/userid/商汤科技/announcements')"]
    }}
    '''
}

"""
kwargs = {
    "query": "利润表",
    "mdvec_path": "files/userid/商汤科技/vectors",
    "keywords": ["利润表", "现金流量表"],
    "top_n_per_file": 10,
    "final_top_n": 8,
    "embedding_model": "doubao-embedding-vision-250328",
    "model_type": "doubao",
    "max_workers": 4,
    "auto_generate_keywords": False,
    "llm_manager": None
}

MultiKBSearch(**kwargs)
"""
MULTI_KB_SEARCH_TOOL = {
    "type": "function",
    "function": {"name": "multi_kb_search", "description": "使用MultiKBSearch搜索上市公司信息"},
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "用户的问题"},
            "mdvec_path": {"type": "string", "description": "向量数据库保存路径，必须是.pkl文件"},
            "keywords": {"type": "array", "description": "关键词列表"},
            "top_n_per_file": {"type": "integer", "description": "每个文件返回结果"},
            "final_top_n": {"type": "integer", "description": "最终返回结果"},
            "embedding_model": {"type": "string", "description": "嵌入模型"},
            "model_type": {"type": "string", "description": "模型类型"},
            "max_workers": {"type": "integer", "description": "最大工作线程数，默认4"},
        },
        "required": ["query", "mdvec_path", "keywords", "top_n_per_file", "final_top_n"],
    },
    "example": '''
    用户问题：请帮我搜索关于福耀玻璃的财务情况(userid)
    你的输出：
    ```json
    {{
        "tools": ["multi_kb_search(query='贵州茅台的利润表', mdvec_path='files/userid/贵州茅台/vectors', keywords=['利润表'], top_n_per_file=10, final_top_n=8)"]
    }}
    '''
}



# get_stock_data(stock_name, indicator, start_year, folder_path)
GET_STOCK_DATA_TOOL = {
    "type": "function",
    "function": {"name": "get_stock_data", "description": "获取股票数据"},
    "parameters": {
        "type": "object",
        "properties": {
            "stock_name": {"type": "string", "description": "股票名称"},
            "indicator": {"type": "string", "description": "指标"},
            "start_year": {"type": "string", "description": "开始年份"},
            "folder_path": {"type": "string", "description": "文件夹路径"},
        },
        "required": ["stock_name", "indicator", "start_year", "folder_path"],
    },
    "example": '''
    用户问题：请帮我获取福耀玻璃的财务数据
    你的输出：
    ```json
    {{
        "tools": ["get_stock_data(stock_name='福耀玻璃', indicator='按年度', start_year='2020', folder_path='files/userid/福耀玻璃/data')"]
    }}
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


########################
####子智能体规划工具#####
########################

# 撰写计划
# write_plan(CHAPTER_NUM, demand)
WRITE_PLAN_TOOL = {
    "type": "function",
    "function": {"name": "write_plan", "description": "撰写计划"},
    "parameters": {
        "type": "object",
        "properties": {
            "CHAPTER_NUM": {"type": "integer", "description": "章节号，公司研究计划为1，行业研究计划为2，公司深度分析计划为3，财务分析计划为4，多维度估值体系计划为5，估值分析计划为6，投资建议计划为7"},
            "demand": {"type": "string", "description": "用户需求，必须包含股票名称"},
            "stock_name": {"type": "string", "description": "股票名称"},
        },
        "required": ["CHAPTER_NUM", "demand", "stock_name"],
    },
    "example": '''
    用户问题：接下来需要撰写第一部分的公司研究计划
    你的输出：
    ```json
    {{
        "tools": ["write_plan(CHAPTER_NUM=1, demand='请帮我撰写公司研究计划', stock_name='福耀玻璃')"]
    }}
    '''
}

