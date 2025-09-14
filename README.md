# EchoAgent Framework 🤖

[中文文档](README_CN.md) | **English**

A next-generation intelligent agent framework that combines modular architecture with powerful tool integration capabilities, supporting multiple LLMs and extensible tool ecosystems.

## ✨ Key Features

### 🏗️ Modular Architecture
- **Layered Design**: Clean separation of tool management, state management, and prompt management
- **High Cohesion, Low Coupling**: Each module has clear boundaries and interfaces
- **Extensible by Design**: Easy to add new tools, models, and features

### 🔧 Multi-Tool Integration
- **Built-in Tools**: Code execution, data analysis, file operations
- **MCP Protocol**: Full support for Model Context Protocol standard tools
- **Custom Tools**: Easy registration of custom tools with `@tool` decorator
- **Dynamic Loading**: Runtime tool discovery and registration

### 🎯 Multi-Model Support
- **OpenAI**: GPT-4, GPT-4o, GPT-4o-mini
- **Anthropic**: Claude Sonnet 4
- **Google**: Gemini 2.5 Flash/Pro
- **Alibaba**: Qwen 3 Next, Qwen 3 Max
- **ByteDance**: Doubao Pro/Seed
- **And more**: Easily extensible to new models

### 💾 Persistent Sessions
- **File-based Storage**: Structured conversation history in markdown
- **SQLite Backend**: Optional database storage for advanced queries
- **Session Recovery**: Resume conversations across restarts
- **Team Context**: Shared context between multiple agents

### ⚙️ Flexible Configuration
- **Pydantic Settings**: Type-safe configuration with validation
- **Environment Variables**: Easy deployment configuration
- **Multiple Profiles**: Support for different deployment environments
- **Hot Reload**: Configuration changes without restart

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Tool Development](#tool-development)
- [API Reference](#api-reference)
- [Advanced Features](#advanced-features)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## 🚀 Installation

### Prerequisites

- Python 3.8+
- pip or conda package manager

### Install Dependencies

```bash
# Clone the repository
git clone https://github.com/JNUZXF/EchoAgent.git
cd EchoAgent

# Install required packages
pip install -r requirements.txt
```

### Environment Setup

Create a `.env` file in the project root:

```bash
# Copy the example configuration
cp config.env.example .env

# Edit the configuration file
# Add your API keys and model configurations
```

Example `.env` configuration:

```env
# Basic Configuration
AGENT_USER_ID=your_user_id
AGENT_NAME=my_agent
MAIN_MODEL=openai/gpt-4o-2024-11-20
TOOL_MODEL=openai/gpt-4o-mini
FLASH_MODEL=openai/gpt-4o-mini

# API Keys (add the ones you need)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Optional: MCP Tools
ENABLE_MCP=true
MCP_CONFIG_PATH=server_config.json

# Optional: Advanced Settings
MAX_HISTORY=100
MAX_TOKENS=8000
LOG_LEVEL=INFO
```

## 🎯 Quick Start

### Basic Usage

```python
import asyncio
from agent_frame import EchoAgent, create_agent_config

async def main():
    # Create configuration
    config = create_agent_config(
        user_id="demo_user",
        main_model="openai/gpt-4o-2024-11-20",
        tool_model="openai/gpt-4o-mini", 
        flash_model="openai/gpt-4o-mini",
        agent_name="my_assistant"
    )
    
    # Initialize agent
    agent = EchoAgent(config)
    
    # Interactive chat loop
    await agent.chat_loop_common(version="v2")

if __name__ == "__main__":
    asyncio.run(main())
```

### Command Line Interface

```bash
# Run the agent with default configuration
python agent_frame.py

# Or use specific models
MAIN_MODEL="anthropic/claude-sonnet-4" python agent_frame.py
```

## ⚙️ Configuration

### Configuration Methods

1. **Environment Variables** (Recommended for production)
2. **`.env` File** (Good for development)
3. **Programmatic Configuration** (For embedded usage)

### Key Configuration Options

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `user_id` | Unique user identifier | Required | `"john_doe"` |
| `main_model` | Primary conversation model | `"doubao-seed-1-6-250615"` | `"openai/gpt-4o"` |
| `tool_model` | Tool intention recognition model | `"doubao-pro"` | `"openai/gpt-4o-mini"` |
| `flash_model` | Quick response model | `"doubao-pro"` | `"openai/gpt-4o-mini"` |
| `max_conversation_history` | Max conversation turns to keep | `100` | `50` |
| `enable_mcp` | Enable MCP tool integration | `true` | `false` |
| `log_level` | Logging verbosity | `"INFO"` | `"DEBUG"` |
| `AGENT_PROJECT_ROOT` | Project root directory path | Auto-detected | `"/path/to/project"` |

### 🗂️ Project Root Configuration

The framework uses an intelligent project root detection mechanism that supports multiple strategies:

**1. Environment Variable (Recommended for production)**
```bash
export AGENT_PROJECT_ROOT=/path/to/your/project
```

**2. Project Marker Files**
Create a `.project-root` file in your project root:
```bash
touch .project-root
```

**3. Automatic Detection**
The framework automatically detects project root based on:
- `agent_frame.py` presence (highest priority)
- Python project files (`pyproject.toml`, `requirements.txt`)
- Version control (`.git`)
- Documentation (`README.md`) (lowest priority)

**Configuration Examples:**
```python
from utils.project_root_finder import configure_project_root, create_project_marker

# Programmatic configuration
configure_project_root("/path/to/project")

# Create marker file
create_project_marker(Path("/path/to/project"))
```

See [config/project_root_examples.md](config/project_root_examples.md) for detailed examples.

### Model Configuration Examples

```python
# OpenAI Configuration
config = create_agent_config(
    user_id="user",
    main_model="openai/gpt-4o-2024-11-20",
    tool_model="openai/gpt-4o-mini",
    flash_model="openai/gpt-4o-mini"
)

# Anthropic Configuration  
config = create_agent_config(
    user_id="user",
    main_model="anthropic/claude-sonnet-4",
    tool_model="anthropic/claude-haiku-3",
    flash_model="anthropic/claude-haiku-3"
)

# Mixed Provider Configuration
config = create_agent_config(
    user_id="user", 
    main_model="anthropic/claude-sonnet-4",
    tool_model="openai/gpt-4o-mini",
    flash_model="google/gemini-2.5-flash"
)
```

## 📚 Usage Examples

### Example 1: Data Analysis Agent

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
        user_system_prompt="You are a data analysis expert. Always show visualizations for data insights."
    )
    
    agent = EchoAgent(config)
    
    # Process a query with streaming response
    query = "Create synthetic stock data for AAPL and MSFT, then analyze their correlation and create visualizations"
    
    async for response_chunk in agent.process_query(query, version="v2"):
        print(response_chunk, end="", flush=True)

asyncio.run(data_analysis_example())
```

### Example 2: Research Agent with Custom Tools

```python
from pydantic import BaseModel, Field
from tools_agent.toolkit import tool
from agent_frame import EchoAgent, create_agent_config

# Define custom tool
class SearchArgs(BaseModel):
    query: str = Field(..., description="Search query")
    max_results: int = Field(10, description="Maximum results")

@tool
def search_papers(args: SearchArgs):
    """Search academic papers and return summaries"""
    # Your search implementation here
    return {"papers": f"Found papers related to: {args.query}"}

async def research_agent_example():
    config = create_agent_config(
        user_id="researcher",
        agent_name="research_assistant", 
        main_model="anthropic/claude-sonnet-4",
        tool_model="openai/gpt-4o-mini",
        flash_model="google/gemini-2.5-flash",
        user_system_prompt="You are a research assistant specializing in academic literature review."
    )
    
    agent = EchoAgent(config)
    
    # Register custom tool
    agent.tool_manager.register_tool_function(search_papers)
    
    # Use the agent
    query = "Find recent papers on LLM agents and summarize key innovations"
    async for response in agent.process_query(query, version="v2"):
        print(response, end="", flush=True)

asyncio.run(research_agent_example())
```

### Example 3: Team Context Sharing

```python
import asyncio
from agent_frame import EchoAgent, create_agent_config

async def team_context_example():
    # Create two agents with shared context
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
    
    # Set shared context path
    shared_context_path = "shared_team_context.json"
    agent1.set_team_context_override_path(shared_context_path)
    agent2.set_team_context_override_path(shared_context_path)
    
    # Agent 1 sets team goal
    agent1.set_team_goal("Develop a web application with React frontend and Python backend")
    
    # Agent 2 can access the shared context
    team_context = agent2.get_team_context()
    print(f"Shared team goal: {team_context.get('team_goal', 'None')}")

asyncio.run(team_context_example())
```

## 🔧 Tool Development

### Creating Custom Tools

The framework uses a decorator-based approach for tool registration:

```python
from pydantic import BaseModel, Field
from tools_agent.toolkit import tool
from typing import Optional

# Define the tool's input schema
class WebScrapingArgs(BaseModel):
    url: str = Field(..., description="URL to scrape")
    selector: Optional[str] = Field(None, description="CSS selector for specific content")
    max_length: int = Field(5000, description="Maximum content length")

@tool
def web_scraper(args: WebScrapingArgs):
    """
    Scrape content from a web page
    
    This tool fetches and extracts content from web pages.
    
    Example usage:
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
        
        # Truncate if too long
        if len(text) > args.max_length:
            text = text[:args.max_length] + "..."
        
        return {
            "content": text,
            "url": args.url,
            "length": len(text)
        }
        
    except Exception as e:
        return {"error": f"Failed to scrape {args.url}: {str(e)}"}

# Register the tool
agent.tool_manager.register_tool_function(web_scraper)
```

### Tool Best Practices

1. **Clear Input Schema**: Use Pydantic models with descriptive fields
2. **Comprehensive Docstrings**: Include purpose, parameters, and examples
3. **Error Handling**: Always handle exceptions gracefully
4. **Return Structured Data**: Use dictionaries with consistent keys
5. **Performance Considerations**: Set timeouts and limits

### MCP Tool Integration

For Model Context Protocol tools, create a `server_config.json`:

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

## 📖 API Reference

### EchoAgent Class

#### Initialization
```python
agent = EchoAgent(config: AgentSettings)
```

#### Core Methods
- `process_query(question: str, version: str) -> AsyncGenerator[str, None]`
  - Process user query with streaming response
- `chat_loop_common(version: str) -> None`
  - Start interactive CLI chat session
- `reset_chat(preserve_session_id: bool = False) -> None`
  - Reset conversation state

#### Team Context Management
- `set_team_context_override_path(path: str) -> None`
  - Set shared context file path
- `update_team_context(patch: Dict[str, Any]) -> None`
  - Update team context
- `get_team_context() -> Dict[str, Any]`
  - Get current team context

### Configuration Factory

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

## 🚀 Advanced Features

### Custom Tool Execution Context

```python
# Custom tool with context access
@tool
def context_aware_tool(args: MyArgs):
    """Tool that accesses conversation context"""
    # Access current session information
    session_info = get_current_session()
    return {"result": "Processed with context awareness"}
```

### Async Tool Support

```python
from tools_agent.toolkit import tool

@tool
async def async_api_call(args: APIArgs):
    """Asynchronous tool for API calls"""
    async with aiohttp.ClientSession() as session:
        async with session.get(args.url) as response:
            return await response.json()
```

### Multi-Agent Coordination

```python
async def multi_agent_workflow():
    # Create specialized agents
    researcher = EchoAgent(research_config)
    analyst = EchoAgent(analysis_config)
    writer = EchoAgent(writing_config)
    
    # Set shared context
    shared_path = "project_context.json"
    for agent in [researcher, analyst, writer]:
        agent.set_team_context_override_path(shared_path)
    
    # Research phase
    research_query = "Research latest trends in AI"
    research_result = await researcher.process_query(research_query, "v2")
    
    # Analysis phase  
    analysis_query = "Analyze the research findings"
    analysis_result = await analyst.process_query(analysis_query, "v2")
    
    # Writing phase
    writing_query = "Create a comprehensive report"
    final_report = await writer.process_query(writing_query, "v2")
```

## 🏗️ Project Structure

```
my_agent_frame/
├── agent_core/                 # Core framework modules
│   ├── __init__.py            # Module exports
│   ├── mcp_manager.py         # MCP protocol integration
│   ├── models.py              # Pydantic data models
│   ├── prompts.py             # Prompt management
│   ├── state_manager.py       # Conversation state management
│   └── tools.py               # Tool management system
├── config/                     # Configuration management
│   ├── __init__.py
│   └── agent_config.py        # Pydantic-based configuration
├── tools_agent/               # Tool system implementation
│   ├── builtin_tools.py       # Built-in tools (CodeRunner, etc.)
│   ├── function_call_toolbox.py # Function parsing utilities
│   ├── llm_manager.py         # Multi-provider LLM management
│   ├── parse_function_call.py # Function call parsing
│   └── toolkit.py             # Tool registration system
├── utils/                     # Utility modules
│   ├── conversation_store.py  # SQLite conversation storage
│   ├── file_manager.py        # File system management
│   └── code_runner.py         # Code execution utilities
├── prompts/                   # Prompt templates
│   └── agent_prompts.py       # System and tool prompts
├── files/                     # Session storage directory
├── workspaces/                # User workspace directories
├── agent_frame.py             # Main framework entry point
├── requirements.txt           # Python dependencies
├── config.env.example         # Environment configuration template
└── README.md                  # This documentation
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone https://github.com/JNUZXF/EchoAgent.git
cd EchoAgent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install black flake8 mypy pytest pytest-asyncio

# Run tests
pytest tests/

# Format code
black .

# Type checking
mypy agent_core/ tools_agent/
```

### Guidelines

- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write comprehensive docstrings
- Include unit tests for new features
- Update documentation for API changes

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Contact

### Developer

**Xinfu Zhang**  
📧 Email: JNUZXF@163.com  
🐙 GitHub: [@JNUZXF](https://github.com/JNUZXF)  

### WeChat

For Chinese users, scan the QR code to add on WeChat:

![WeChat QR Code](images/wechatID.jpg)

### Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/JNUZXF/EchoAgent/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/JNUZXF/EchoAgent/discussions)
- 📖 **Documentation**: [Wiki](https://github.com/JNUZXF/EchoAgent/wiki)

---

**Built with ❤️ by the EchoAgent Team**

*Making AI agents more accessible, extensible, and powerful for everyone.*
