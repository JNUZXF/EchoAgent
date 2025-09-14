# EchoAgent 智能体框架 🤖

**中文** | [English](README.md)

下一代智能体框架，结合模块化架构与强大的工具集成能力，支持多种大模型和可扩展的工具生态系统。

## ✨ 核心特性

### 🏗️ 模块化架构
- **分层设计**：工具管理、状态管理、提示词管理的清晰分离
- **高内聚、低耦合**：每个模块具有明确的边界和接口
- **可扩展设计**：轻松添加新工具、模型和功能

### 🔧 多工具集成
- **内置工具**：代码执行、数据分析、文件操作
- **MCP协议**：完整支持模型上下文协议标准工具
- **自定义工具**：使用`@tool`装饰器轻松注册自定义工具
- **动态加载**：运行时工具发现和注册

### 🎯 多模型支持
- **OpenAI**：GPT-4、GPT-4o、GPT-4o-mini
- **Anthropic**：Claude Sonnet 4
- **Google**：Gemini 2.5 Flash/Pro
- **阿里巴巴**：通义千问 3 Next、通义千问 3 Max
- **字节跳动**：豆包 Pro/Seed
- **更多模型**：易于扩展支持新模型

### 💾 持久化会话
- **文件存储**：Markdown格式的结构化对话历史
- **SQLite后端**：可选的数据库存储，支持高级查询
- **会话恢复**：跨重启恢复对话
- **团队上下文**：多智能体间的共享上下文

### ⚙️ 灵活配置
- **Pydantic设置**：类型安全的配置验证
- **环境变量**：简化部署配置
- **多环境支持**：支持不同部署环境配置
- **热重载**：无需重启即可应用配置变更

## 📋 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用示例](#使用示例)
- [工具开发](#工具开发)
- [API参考](#api参考)
- [高级功能](#高级功能)
- [贡献指南](#贡献指南)
- [许可证](#许可证)
- [联系方式](#联系方式)

## 🚀 安装

### 环境要求

- Python 3.8+
- pip 或 conda 包管理器

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/yourusername/my_agent_frame.git
cd my_agent_frame

# 安装所需包
pip install -r requirements.txt
```

### 环境设置

在项目根目录创建 `.env` 文件：

```bash
# 复制示例配置
cp config.env.example .env

# 编辑配置文件
# 添加您的API密钥和模型配置
```

示例 `.env` 配置：

```env
# 基础配置
AGENT_USER_ID=your_user_id
AGENT_NAME=my_agent
MAIN_MODEL=openai/gpt-4o-2024-11-20
TOOL_MODEL=openai/gpt-4o-mini
FLASH_MODEL=openai/gpt-4o-mini

# API密钥（添加您需要的）
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# 可选：MCP工具
ENABLE_MCP=true
MCP_CONFIG_PATH=server_config.json

# 可选：高级设置
MAX_HISTORY=100
MAX_TOKENS=8000
LOG_LEVEL=INFO
```

## 🎯 快速开始

### 基础使用

```python
import asyncio
from agent_frame import EchoAgent, create_agent_config

async def main():
    # 创建配置
    config = create_agent_config(
        user_id="demo_user",
        main_model="openai/gpt-4o-2024-11-20",
        tool_model="openai/gpt-4o-mini", 
        flash_model="openai/gpt-4o-mini",
        agent_name="my_assistant"
    )
    
    # 初始化智能体
    agent = EchoAgent(config)
    
    # 交互式聊天循环
    await agent.chat_loop_common(version="v2")

if __name__ == "__main__":
    asyncio.run(main())
```

### 命令行界面

```bash
# 使用默认配置运行智能体
python agent_frame.py

# 或使用特定模型
MAIN_MODEL="anthropic/claude-sonnet-4" python agent_frame.py
```

## ⚙️ 配置说明

### 配置方法

1. **环境变量**（生产环境推荐）
2. **`.env` 文件**（开发环境推荐）
3. **程序化配置**（嵌入式使用）

### 主要配置选项

| 参数 | 描述 | 默认值 | 示例 |
|------|------|--------|------|
| `user_id` | 用户唯一标识符 | 必需 | `"john_doe"` |
| `main_model` | 主要对话模型 | `"doubao-seed-1-6-250615"` | `"openai/gpt-4o"` |
| `tool_model` | 工具意图识别模型 | `"doubao-pro"` | `"openai/gpt-4o-mini"` |
| `flash_model` | 快速响应模型 | `"doubao-pro"` | `"openai/gpt-4o-mini"` |
| `max_conversation_history` | 保留的最大对话轮数 | `100` | `50` |
| `enable_mcp` | 启用MCP工具集成 | `true` | `false` |
| `log_level` | 日志详细程度 | `"INFO"` | `"DEBUG"` |

### 模型配置示例

```python
# OpenAI配置
config = create_agent_config(
    user_id="user",
    main_model="openai/gpt-4o-2024-11-20",
    tool_model="openai/gpt-4o-mini",
    flash_model="openai/gpt-4o-mini"
)

# Anthropic配置  
config = create_agent_config(
    user_id="user",
    main_model="anthropic/claude-sonnet-4",
    tool_model="anthropic/claude-haiku-3",
    flash_model="anthropic/claude-haiku-3"
)

# 混合提供商配置
config = create_agent_config(
    user_id="user", 
    main_model="anthropic/claude-sonnet-4",
    tool_model="openai/gpt-4o-mini",
    flash_model="google/gemini-2.5-flash"
)
```

## 📚 使用示例

### 示例1：数据分析智能体

```python
import asyncio
from agent_frame import EchoAgent, create_agent_config

async def data_analysis_example():
    config = create_agent_config(
        user_id="analyst",
        agent_name="data_analyst",
        main_model="anthropic/claude-sonnet-4",
        tool_model="openai/gpt-4o-mini",
        flash_model="openai/gpt-4o-mini",
        user_system_prompt="你是一个数据分析专家。总是为数据洞察提供可视化展示。"
    )
    
    agent = EchoAgent(config)
    
    # 处理查询并获得流式响应
    query = "为AAPL和MSFT创建模拟股票数据，然后分析它们的相关性并创建可视化图表"
    
    async for response_chunk in agent.process_query(query, version="v2"):
        print(response_chunk, end="", flush=True)

asyncio.run(data_analysis_example())
```

### 示例2：带自定义工具的研究智能体

```python
from pydantic import BaseModel, Field
from tools_agent.toolkit import tool
from agent_frame import EchoAgent, create_agent_config

# 定义自定义工具
class SearchArgs(BaseModel):
    query: str = Field(..., description="搜索查询")
    max_results: int = Field(10, description="最大结果数")

@tool
def search_papers(args: SearchArgs):
    """搜索学术论文并返回摘要"""
    # 您的搜索实现
    return {"papers": f"找到与以下内容相关的论文：{args.query}"}

async def research_agent_example():
    config = create_agent_config(
        user_id="researcher",
        agent_name="research_assistant", 
        main_model="anthropic/claude-sonnet-4",
        tool_model="openai/gpt-4o-mini",
        flash_model="google/gemini-2.5-flash",
        user_system_prompt="你是一个专门从事学术文献综述的研究助手。"
    )
    
    agent = EchoAgent(config)
    
    # 注册自定义工具
    agent.tool_manager.register_tool_function(search_papers)
    
    # 使用智能体
    query = "搜索关于LLM智能体的最新论文并总结关键创新点"
    async for response in agent.process_query(query, version="v2"):
        print(response, end="", flush=True)

asyncio.run(research_agent_example())
```

### 示例3：团队上下文共享

```python
import asyncio
from agent_frame import EchoAgent, create_agent_config

async def team_context_example():
    # 创建两个具有共享上下文的智能体
    config1 = create_agent_config(
        user_id="team_user",
        agent_name="agent_1",
        main_model="openai/gpt-4o",
        tool_model="openai/gpt-4o-mini",
        flash_model="openai/gpt-4o-mini"
    )
    
    config2 = create_agent_config(
        user_id="team_user", 
        agent_name="agent_2",
        main_model="anthropic/claude-sonnet-4",
        tool_model="openai/gpt-4o-mini", 
        flash_model="openai/gpt-4o-mini"
    )
    
    agent1 = EchoAgent(config1)
    agent2 = EchoAgent(config2)
    
    # 设置共享上下文路径
    shared_context_path = "shared_team_context.json"
    agent1.set_team_context_override_path(shared_context_path)
    agent2.set_team_context_override_path(shared_context_path)
    
    # 智能体1设置团队目标
    agent1.set_team_goal("开发一个具有React前端和Python后端的Web应用程序")
    
    # 智能体2可以访问共享上下文
    team_context = agent2.get_team_context()
    print(f"共享团队目标：{team_context.get('team_goal', '无')}")

asyncio.run(team_context_example())
```

## 🔧 工具开发

### 创建自定义工具

框架使用基于装饰器的方法进行工具注册：

```python
from pydantic import BaseModel, Field
from tools_agent.toolkit import tool
from typing import Optional

# 定义工具的输入模式
class WebScrapingArgs(BaseModel):
    url: str = Field(..., description="要抓取的URL")
    selector: Optional[str] = Field(None, description="特定内容的CSS选择器")
    max_length: int = Field(5000, description="最大内容长度")

@tool
def web_scraper(args: WebScrapingArgs):
    """
    从网页抓取内容
    
    此工具获取并提取网页内容。
    
    使用示例：
    {"tools": ["web_scraper(url='https://example.com', selector='article', max_length=3000)"]}
    """
    import requests
    from bs4 import BeautifulSoup
    
    try:
        response = requests.get(args.url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if args.selector:
            content = soup.select_one(args.selector)
            text = content.get_text(strip=True) if content else ""
        else:
            text = soup.get_text(strip=True)
        
        # 如果太长则截断
        if len(text) > args.max_length:
            text = text[:args.max_length] + "..."
        
        return {
            "content": text,
            "url": args.url,
            "length": len(text)
        }
        
    except Exception as e:
        return {"error": f"抓取 {args.url} 失败：{str(e)}"}

# 注册工具
agent.tool_manager.register_tool_function(web_scraper)
```

### 工具开发最佳实践

1. **清晰的输入模式**：使用带有描述性字段的Pydantic模型
2. **全面的文档字符串**：包括目的、参数和示例
3. **错误处理**：始终优雅地处理异常
4. **返回结构化数据**：使用具有一致键的字典
5. **性能考虑**：设置超时和限制

### MCP工具集成

对于模型上下文协议工具，创建 `server_config.json`：

```json
{
  "research_server": {
    "command": "python",
    "args": ["research_server.py"],
    "env": {
      "PYTHONPATH": "."
    }
  },
  "file_server": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/files"]
  }
}
```

## 📖 API参考

### EchoAgent类

#### 初始化
```python
agent = EchoAgent(config: AgentSettings)
```

#### 核心方法
- `process_query(question: str, version: str) -> AsyncGenerator[str, None]`
  - 处理用户查询并提供流式响应
- `chat_loop_common(version: str) -> None`
  - 启动交互式CLI聊天会话
- `reset_chat(preserve_session_id: bool = False) -> None`
  - 重置对话状态

#### 团队上下文管理
- `set_team_context_override_path(path: str) -> None`
  - 设置共享上下文文件路径
- `update_team_context(patch: Dict[str, Any]) -> None`
  - 更新团队上下文
- `get_team_context() -> Dict[str, Any]`
  - 获取当前团队上下文

### 配置工厂

```python
config = create_agent_config(
    user_id: str,
    main_model: str,
    tool_model: str,
    flash_model: str,
    agent_name: str = "echo_agent",
    conversation_id: Optional[str] = None,
    workspace: Optional[str] = None,
    user_system_prompt: Optional[str] = None,
    use_new_config: bool = True,
    enable_mcp: bool = True,
    **kwargs
) -> AgentSettings
```

## 🚀 高级功能

### 自定义工具执行上下文

```python
# 具有上下文访问的自定义工具
@tool
def context_aware_tool(args: MyArgs):
    """访问对话上下文的工具"""
    # 访问当前会话信息
    session_info = get_current_session()
    return {"result": "使用上下文感知处理"}
```

### 异步工具支持

```python
from tools_agent.toolkit import tool

@tool
async def async_api_call(args: APIArgs):
    """用于API调用的异步工具"""
    async with aiohttp.ClientSession() as session:
        async with session.get(args.url) as response:
            return await response.json()
```

### 多智能体协调

```python
async def multi_agent_workflow():
    # 创建专门的智能体
    researcher = EchoAgent(research_config)
    analyst = EchoAgent(analysis_config)
    writer = EchoAgent(writing_config)
    
    # 设置共享上下文
    shared_path = "project_context.json"
    for agent in [researcher, analyst, writer]:
        agent.set_team_context_override_path(shared_path)
    
    # 研究阶段
    research_query = "研究AI的最新趋势"
    research_result = await researcher.process_query(research_query, "v2")
    
    # 分析阶段  
    analysis_query = "分析研究发现"
    analysis_result = await analyst.process_query(analysis_query, "v2")
    
    # 写作阶段
    writing_query = "创建综合报告"
    final_report = await writer.process_query(writing_query, "v2")
```

## 🏗️ 项目结构

```
my_agent_frame/
├── agent_core/                 # 核心框架模块
│   ├── __init__.py            # 模块导出
│   ├── mcp_manager.py         # MCP协议集成
│   ├── models.py              # Pydantic数据模型
│   ├── prompts.py             # 提示词管理
│   ├── state_manager.py       # 对话状态管理
│   └── tools.py               # 工具管理系统
├── config/                     # 配置管理
│   ├── __init__.py
│   └── agent_config.py        # 基于Pydantic的配置
├── tools_agent/               # 工具系统实现
│   ├── builtin_tools.py       # 内置工具（CodeRunner等）
│   ├── function_call_toolbox.py # 函数解析工具
│   ├── llm_manager.py         # 多提供商LLM管理
│   ├── parse_function_call.py # 函数调用解析
│   └── toolkit.py             # 工具注册系统
├── utils/                     # 工具模块
│   ├── conversation_store.py  # SQLite对话存储
│   ├── file_manager.py        # 文件系统管理
│   └── code_runner.py         # 代码执行工具
├── prompts/                   # 提示词模板
│   └── agent_prompts.py       # 系统和工具提示词
├── files/                     # 会话存储目录
├── workspaces/                # 用户工作空间目录
├── agent_frame.py             # 主框架入口点
├── requirements.txt           # Python依赖
├── config.env.example         # 环境配置模板
└── README_CN.md               # 本文档
```

## 🤝 贡献指南

我们欢迎贡献！请查看我们的[贡献指南](CONTRIBUTING.md)了解详情。

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/yourusername/my_agent_frame.git
cd my_agent_frame

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install black flake8 mypy pytest pytest-asyncio

# 运行测试
pytest tests/

# 格式化代码
black .

# 类型检查
mypy agent_core/ tools_agent/
```

### 指导原则

- 遵循PEP 8代码风格指南
- 为所有函数添加类型提示
- 编写全面的文档字符串
- 为新功能包含单元测试
- 为API变更更新文档

## 📄 许可证

本项目采用MIT许可证 - 详见[LICENSE](LICENSE)文件。

## 📞 联系方式

### 开发者

**您的姓名**  
📧 邮箱：your.email@example.com  
🐙 GitHub：[@yourusername](https://github.com/yourusername)  

### 微信联系

扫描二维码添加微信：

![微信二维码](images/wechatID.jpg)

### 支持

- 🐛 **错误报告**：[GitHub Issues](https://github.com/yourusername/my_agent_frame/issues)
- 💡 **功能请求**：[GitHub Discussions](https://github.com/yourusername/my_agent_frame/discussions)
- 📖 **文档**：[Wiki](https://github.com/yourusername/my_agent_frame/wiki)

---

**由EchoAgent团队用❤️构建**

*让AI智能体对每个人都更易于访问、扩展和强大。*
