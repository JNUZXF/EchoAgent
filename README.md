# EchoAgent - 智能体框架

<div align="center">

![EchoAgent Logo](https://img.shields.io/badge/EchoAgent-智能体框架-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)
![GitHub Stars](https://img.shields.io/github/stars/JNUZXF/EchoAgent?style=for-the-badge)

**先回答，再决策的智能体框架**

[快速开始](#快速开始) • [特性](#核心特性) • [架构](#架构设计) • [文档](#使用文档) • [贡献](#贡献指南)

</div>

## 📖 项目简介

EchoAgent 是一个创新的智能体框架，采用独特的"**先回答-再判断-工具调用-END()终止**"机制。与传统的先调用工具再回答的模式不同，EchoAgent 让主模型首先基于已有知识直接回答用户问题，然后由决策模型判断是否需要调用工具进行进一步处理。

### 🌟 核心特性

- **🔄 双模型协同**: 主模型负责回答，决策模型负责判断工具调用
- **⚡ 快速响应**: 先给出直接回答，再根据需要深入处理
- **🛡️ 安全执行**: 内置代码执行器，支持安全的 Python 代码运行
- **🔧 工具生态**: 丰富的工具集，支持文档处理、数据分析、网络搜索等
- **📊 持久化上下文**: 跨对话的变量保持，支持连续的数据分析任务
- **🎯 智能终止**: 通过 `END()` 信号实现智能的任务完成判断

## 🏗️ 架构设计

```mermaid
graph TD
    A[用户问题] --> B[主模型直接回答]
    B --> C[决策模型判断]
    C --> D{需要工具?}
    D -->|是| E[调用工具]
    D -->|否| F[输出 END()]
    E --> G[工具执行结果]
    G --> H[更新上下文]
    H --> I[主模型分析结果]
    I --> C
    F --> J[任务完成]
```

### 核心组件

- **AgentConfig**: 配置管理，支持多用户、多模型
- **AgentStateManager**: 状态管理，处理对话历史和文件存储
- **AgentToolManager**: 工具管理，统一注册和调用本地/远程工具
- **LLMManager**: 大模型管理，支持多种 LLM 提供商
- **CodeExecutor**: 安全代码执行器，支持持久化上下文

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 支持的 LLM 提供商 API 密钥（豆包、OpenAI、Claude 等）

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/JNUZXF/EchoAgent.git
cd EchoAgent
```

2. **安装依赖**
```bash
pip install -r requirements.txt  # 需要创建此文件
```

3. **配置环境变量**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，添加你的 API 密钥
DOUBAO_API_KEY=your_doubao_api_key
OPENAI_API_KEY=your_openai_api_key
# 更多配置...
```

4. **运行示例**
```bash
python agent_frame.py
```

### 基础使用

```python
from agent_frame import Agent, AgentConfig

# 创建配置
config = AgentConfig(
    user_id="demo_user",
    main_model="doubao-pro",
    tool_model="doubao-pro", 
    flash_model="doubao-pro"
)

# 初始化智能体
agent = Agent(config)

# 启动对话
await agent.chat_loop()
```

## 📚 使用文档

### 工具系统

EchoAgent 内置多种工具：

#### CodeRunner - 代码执行器
```python
# 用户: 帮我计算斐波那契数列的前10项
# AI会直接回答，然后自动调用CodeRunner执行代码
```

#### 文档处理工具
- PDF 阅读和转换
- 文档向量化和检索
- 图像处理和OCR

#### 数据分析工具
- 股票数据获取
- 财务报表分析
- 数据可视化

### 扩展开发

#### 添加自定义工具

1. **创建工具类**
```python
class MyTool:
    def execute(self, **kwargs):
        # 工具逻辑
        return result
```

2. **注册工具**
```python
agent.tool_manager.register_local_tool(
    "my_tool", 
    MyTool(), 
    tool_config_for_prompt
)
```

3. **更新工具配置**
在 `tools_configs.py` 中添加工具描述。

## 🔧 配置说明

### 模型配置

支持多种 LLM 提供商：

```python
# 豆包系列
"doubao-pro", "doubao-1.5-lite", "doubao-1.5-pro-256k"

# OpenAI 系列  
"gpt-4o", "gpt-4o-mini"

# Claude 系列
"anthropic/claude-3.5-sonnet"

# 开源模型
"opensource/llama-3.1-8b"
```

### 安全配置

CodeExecutor 支持三种安全级别：
- `strict`: 仅允许基本标准库
- `medium`: 允许常用科学计算库（默认）
- `permissive`: 允许大部分库，仅禁止危险操作

## 📁 项目结构

```
EchoAgent/
├── agent_frame.py          # 主框架入口
├── prompts/               # 提示词管理
│   └── agent_prompts.py
├── tools_agent/           # 工具集合
│   ├── llm_manager.py     # LLM 管理
│   ├── code_interpreter.py
│   └── ...
├── utils/                 # 工具实现
│   ├── code_runner.py     # 代码执行器
│   └── ...
├── tools_configs.py       # 工具配置
├── ToDo.md               # 优化清单
└── files/                # 用户数据存储
```

## 🤝 贡献指南

我们欢迎所有形式的贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 获取详细指南。

### 贡献方式

1. **报告问题**: 使用 [Issue 模板](.github/ISSUE_TEMPLATE/) 报告 bug
2. **功能建议**: 提交功能请求和改进建议  
3. **代码贡献**: Fork 项目，创建分支，提交 PR
4. **文档改进**: 完善文档和示例

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/

# 代码格式化
black agent_frame.py
```

## 📋 待办事项

查看 [ToDo.md](ToDo.md) 了解当前的优化计划和可认领的任务。

## 🐛 问题排查

### 常见问题

**Q: 工具调用失败怎么办？**
A: 检查 `files/{user_id}/{agent_name}/tool_conversations.json` 中的详细日志。

**Q: 代码执行超时？**
A: 调整 `CodeExecutor` 的 `timeout` 参数，或检查代码复杂度。

**Q: API 调用失败？**
A: 确认 `.env` 文件中的 API 密钥配置正确。

### 日志查看

```bash
# 查看完整对话历史
cat files/{user_id}/{agent_name}/full_context_conversations.md

# 查看工具执行日志
cat files/{user_id}/{agent_name}/tool_conversations.json
```

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

## 🙏 致谢

感谢以下项目和社区的支持：
- [LangChain](https://github.com/langchain-ai/langchain) - 启发了工具链设计
- [OpenAI](https://openai.com/) - API 支持
- [字节跳动](https://www.volcengine.com/) - 豆包模型支持

## 📞 联系我们

- 提交 Issue: [GitHub Issues](https://github.com/JNUZXF/EchoAgent/issues)
- 邮箱: [请添加你的邮箱]
- 微信群: [请添加二维码]

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给我们一个星标！**

[⬆ 回到顶部](#echoagent---智能体框架)

</div>
