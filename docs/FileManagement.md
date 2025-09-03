<!--
文件: docs/FileManagement.md
功能: 说明生产级文件/路径管理方案与会话目录规范。
-->

## 文件与路径管理方案（生产级）

本方案统一管理 Agent 在运行过程中产生的目录与文件，确保在任意工作目录下启动，都能稳定将会话数据落盘，并便于排障与运维。

### 设计目标

- 会话一键创建：调用一次 Agent（构造 `EchoAgent`）即自动创建会话目录。
- 统一目录结构：所有会话文件按标准目录分类存放，方便检索与清理。
- 环境可配置：可通过环境变量 `AGENT_FILES_ROOT` 指定根目录，默认 `项目根目录/files`。
- 可观测性：每个会话独立日志，轮转保存，控制台与文件双通道输出。
- 易扩展：提供标准接口扩展 artifacts/outputs 等子目录的写入。

### 目录结构

```
{FILES_ROOT}/
  └─ {user_id}/
     └─ {agent_name}/
        ├─ latest.json               # 指向最近一次会话的 session_id
        └─ {session_id}/             # 例如: 20250903-101530-123456
           ├─ logs/
           │  └─ agent.log           # 会话级日志(轮转)
           ├─ conversations/
           │  ├─ agent_coder_system_prompt.md
           │  ├─ judge_prompt.md
           │  ├─ conversations.json
           │  ├─ display_conversations.md
           │  └─ full_context_conversations.md
           ├─ artifacts/             # 模型/工具产生的中间产物
           ├─ uploads/               # 用户上传内容
           ├─ outputs/               # 面向用户的最终输出
           ├─ images/                # 保存图片(可由工具/Notebook/绘图代码写入)
           └─ temp/                  # 临时文件
```

说明：
- `FILES_ROOT` 默认是项目根目录下的 `files/`。可通过 `AGENT_FILES_ROOT` 重定向，如将数据放到独立磁盘。
- `latest.json` 便于工具与运维快速定位最近一次会话目录。

### 使用方法

已在 `agent_frame.py` 内集成 `FileManager`：

1) Agent 初始化自动创建会话目录：

```python
from utils.file_manager import file_manager

agent = EchoAgent(config)  # 内部自动: file_manager.create_session(...)
# 会话目录: files/{user_id}/{agent_name}/{session_id}/
```

2) 状态保存统一落盘：

- 系统提示词、judge 提示词、会话记录、工具记录等均写入 `conversations/` 子目录。

3) 日志：

- `utils/file_manager.py` 提供 `get_session_logger()`，每个会话使用独立 `agent.log`，按 5MB 轮转，保留 3 个备份。

### 环境变量

- `AGENT_FILES_ROOT`：设置会话根目录（绝对路径）。未设置则使用默认的 `项目根目录/files`。

### 扩展建议

- 与对象存储对接：可在 `FileManager` 中新增上传接口，将 `artifacts/` 或 `outputs/` 同步到 OSS/S3。
- 多租户隔离：进一步在 `user_id` 层对权限与配额进行校验。
- 清理策略：定期清理 `temp/` 与长期未访问的 `artifacts/`，可结合 `latest.json` 与时间戳。

### 故障排查

- 若无法创建目录，请检查 `AGENT_FILES_ROOT` 写入权限与磁盘空间。
- 若日志为空，确认进程是否持有写权限，或是否被外部日志系统接管。


