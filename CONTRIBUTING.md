# 贡献指南

感谢您对 EchoAgent 项目的关注！我们欢迎所有形式的贡献，包括但不限于：

- 🐛 报告和修复 bug
- ✨ 提出和实现新功能
- 📝 改进文档
- 🧪 编写测试
- 💡 提供使用建议

## 🚀 快速开始

### 开发环境设置

1. **Fork 并克隆项目**
```bash
git clone https://github.com/YOUR_USERNAME/EchoAgent.git
cd EchoAgent
```

2. **创建开发分支**
```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-number
```

3. **安装开发依赖**
```bash
pip install -r requirements-dev.txt  # 需要创建此文件
```

4. **设置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，添加必要的 API 密钥
```

## 📋 贡献类型

### 🐛 Bug 报告

使用 [Bug Report 模板](.github/ISSUE_TEMPLATE/bug_report.yml) 报告问题，请包括：

- 详细的问题描述
- 复现步骤
- 期望的行为 vs 实际行为
- 环境信息
- 错误日志

### ✨ 功能请求

使用 [Feature Request 模板](.github/ISSUE_TEMPLATE/feature_request.yml) 提出新功能，请包括：

- 功能的使用场景
- 详细的功能描述
- 可能的实现方案
- 对现有功能的影响

### 🔧 代码贡献

#### 添加新工具

1. **在 `tools_agent/` 或 `utils/` 下创建工具文件**
```python
# tools_agent/my_new_tool.py
class MyNewTool:
    def execute(self, **kwargs):
        """工具执行逻辑"""
        return result
```

2. **在 `tools_configs.py` 中添加工具配置**
```python
MY_NEW_TOOL = {
    "type": "function",
    "function": {"name": "my_new_tool", "description": "工具描述"},
    # 详细配置...
}
```

3. **在主框架中注册工具**
```python
# 在 Agent._register_local_tools() 中添加
self.tool_manager.register_local_tool("my_new_tool", MyNewTool(), MY_NEW_TOOL)
```

4. **更新文档和测试**

#### 修改核心逻辑

如果需要修改 `agent_frame.py` 中的核心逻辑：

1. 先提出 Issue 讨论设计方案
2. 确保向后兼容性
3. 添加充分的测试覆盖
4. 更新相关文档

## 📝 编码规范

### Python 代码风格

- 遵循 PEP 8 规范
- 使用 4 个空格缩进
- 行长度不超过 88 字符（Black 默认）
- 使用类型提示

```python
from typing import List, Dict, Any, Optional

def process_data(
    input_data: List[str], 
    config: Dict[str, Any],
    timeout: Optional[int] = None
) -> Dict[str, Any]:
    """
    处理输入数据
    
    Args:
        input_data: 输入数据列表
        config: 配置字典
        timeout: 超时时间（秒）
        
    Returns:
        处理结果字典
    """
    pass
```

### 文档字符串

使用 Google 风格的文档字符串：

```python
def example_function(param1: str, param2: int) -> bool:
    """
    函数简要描述
    
    详细描述函数的功能和用法。
    
    Args:
        param1: 参数1的描述
        param2: 参数2的描述
        
    Returns:
        返回值的描述
        
    Raises:
        ValueError: 当参数无效时抛出
        
    Example:
        >>> result = example_function("test", 123)
        >>> print(result)
        True
    """
    pass
```

### 提交规范

使用约定式提交格式：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**类型说明：**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

**示例：**
```
feat(tools): 添加 PDF 处理工具

- 支持 PDF 文本提取
- 支持 PDF 转图片
- 添加相关配置选项

Closes #123
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试文件
python -m pytest tests/test_agent_frame.py

# 运行特定测试并显示覆盖率
python -m pytest tests/ --cov=agent_frame --cov-report=html
```

### 编写测试

为新功能添加测试：

```python
# tests/test_my_new_tool.py
import pytest
from tools_agent.my_new_tool import MyNewTool

class TestMyNewTool:
    def test_basic_functionality(self):
        tool = MyNewTool()
        result = tool.execute(input_data="test")
        assert result["success"] is True
        
    def test_error_handling(self):
        tool = MyNewTool()
        with pytest.raises(ValueError):
            tool.execute(invalid_param="test")
```

## 📋 Pull Request 流程

1. **创建分支**
```bash
git checkout -b feature/your-feature-name
```

2. **进行修改**
- 编写代码
- 添加测试
- 更新文档

3. **测试修改**
```bash
# 运行测试
python -m pytest

# 代码格式化
black .

# 类型检查
mypy agent_frame.py
```

4. **提交更改**
```bash
git add .
git commit -m "feat: 添加新功能"
```

5. **推送分支**
```bash
git push origin feature/your-feature-name
```

6. **创建 Pull Request**
- 使用 [PR 模板](.github/pull_request_template.md)
- 详细描述修改内容
- 链接相关 Issue
- 等待代码审查

## 🔍 代码审查

### 审查标准

- **功能正确性**: 代码是否正确实现了预期功能
- **代码质量**: 是否遵循编码规范，代码是否清晰易懂
- **测试覆盖**: 是否有充分的测试覆盖
- **文档完整性**: 是否更新了相关文档
- **向后兼容性**: 是否破坏了现有功能

### 审查流程

1. 自动化检查（CI/CD）
2. 维护者审查
3. 社区反馈
4. 修改和完善
5. 合并到主分支

## 🎯 优先贡献领域

查看 [ToDo.md](ToDo.md) 了解当前的优化计划。特别欢迎以下方面的贡献：

- **工具扩展**: 新的实用工具
- **LLM 支持**: 新的模型提供商
- **性能优化**: 提升执行效率
- **安全性**: 增强代码执行安全
- **文档改进**: 完善使用指南
- **测试覆盖**: 增加测试用例

## 💬 社区

- **GitHub Issues**: 报告问题和提出建议
- **GitHub Discussions**: 社区讨论和交流
- **微信群**: [待添加]

## 📄 许可证

通过贡献代码，您同意您的贡献将按照 [MIT 许可证](LICENSE) 进行许可。

## 🙏 感谢

感谢每一位贡献者的努力！您的贡献让 EchoAgent 变得更好。

---

**需要帮助？** 如果您在贡献过程中遇到任何问题，请随时创建 Issue 或联系维护者。
