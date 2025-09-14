# 项目根目录配置示例

## 使用方式

### 1. 环境变量配置（推荐）

```bash
# Windows
set AGENT_PROJECT_ROOT=D:\AgentBuilding\my_agent_frame

# Linux/Mac
export AGENT_PROJECT_ROOT=/path/to/your/project
```

### 2. 项目标识文件

在项目根目录创建标识文件：

```bash
# 创建标识文件
touch .project-root

# 或者指定相对路径
echo "../" > .project-root
```

### 3. Python代码配置

```python
from utils.project_root_finder import configure_project_root, create_project_marker
from pathlib import Path

# 通过代码配置
configure_project_root("/path/to/your/project")

# 或创建标识文件
create_project_marker(Path("/path/to/your/project"))
```

## 支持的项目结构

### Python Agent 项目
- `agent_frame.py` + `requirements.txt` (最高优先级)
- `agent_frame.py` (高优先级)

### 标准Python项目
- `pyproject.toml` + `README.md`
- `setup.py` + `requirements.txt`
- `requirements.txt` + `README.md`

### 通用项目
- `.git` + `README.md`
- `README.md` (最低优先级)

## 调试和验证

```python
from utils.project_root_finder import get_project_root, ProjectRootFinder

# 获取当前项目根目录
root = get_project_root()
print(f"项目根目录: {root}")

# 获取详细信息
finder = ProjectRootFinder()
info = finder.get_project_structure_info()
print(f"项目结构信息: {info}")

# 验证有效性
is_valid = finder.validate_project_root(root)
print(f"根目录有效性: {is_valid}")
```

## 部署建议

1. **开发环境**：使用项目标识文件 `.project-root`
2. **测试环境**：使用环境变量 `AGENT_PROJECT_ROOT`
3. **生产环境**：使用环境变量 + 验证机制
4. **容器部署**：在Dockerfile中设置环境变量

## 故障排除

如果项目根目录检测不正确：

1. 检查环境变量是否设置
2. 验证项目标识文件位置
3. 确认项目包含必要的特征文件
4. 查看日志输出获取详细信息
