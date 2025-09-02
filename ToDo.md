<!--
文件: ToDo.md
路径: 项目根目录
功能: 汇总本项目（智能体框架）的优化方向与可执行待办清单，按模块分组，便于分工与跟踪。每一条目尽量保持原子化、可落地，可被勾选完成。
-->

## 优化清单（Agent 框架）

- [ ] 核心循环与 END() 判定一致性校验
  - **问题**: `tools_configs.py` 中 END 工具描述为 `END()`；`agent_frame.Agent` 中通过 `self.STOP_SIGNAL = "END()"` 与意图识别 JSON 的 `tools` 列表交互。不同提示词中存在 `END()` 与 `END_CONVERSATION()` 的混用描述风险。
  - **行动**: 统一提示词与判断逻辑，仅保留 `END()`；在意图识别解析处对 `END()` 做健壮匹配（忽略大小写与空白）。

- [ ] 意图识别提示词变量占位符不一致
  - **问题**: `prompts/agent_prompts.py` 的 `AGENT_INTENTION_RECOGNITION_PROMPT` 使用 `{TOOLS_GUIDE}`，而 `AgentPromptManager.get_intention_prompt` 传入键为 `AGENT_TOOLS_GUIDE`，占位符名称不一致，导致提示词渲染缺失。
  - **行动**: 统一占位符为 `{AGENT_TOOLS_GUIDE}` 或在渲染前进行替换，避免空段落。

- [ ] 文件与路径管理一致性
  - **问题**: `AgentConfig` 使用 `self.agent_dir` 拼出 `files/{user_id}/{agent_name}`，但注释写的是“文件路径: agent/agent_frame.py”；示例与注释路径存在偏差；跨平台路径分隔符处理零散。
  - **行动**: 用 `pathlib.Path` 统一路径处理；更新注释与 README 的路径示例；将 `replace('\\','/')` 抽象为工具函数复用。

- [ ] 日志与可观测性统一
  - **问题**: 多处使用 `print`、`[DEBUG]`、`[ERROR]`，缺少统一日志框架、日志级别、持久化与轮转。
  - **行动**: 引入标准 `logging`，在 `utils` 下新增日志初始化模块，设置格式(时间戳/级别/模块/会话ID)、按天轮转；前后端交互动作与工具执行入参/耗时全量记录到文件。

- [ ] LLM 提供方与温度/长度参数一致性
  - **问题**: `LLMManager.generate_stream_conversation` 默认温度 0.5，而其他为 0.95；OpenRouter/Ark 等 provider 的 max_tokens、thinking 字段不统一，易出体验差异。
  - **行动**: 在 `LLMManager` 层统一默认参数与覆盖策略；将 provider 特殊参数通过配置注入，避免硬编码。

- [ ] 提示词与系统特性对齐（END 流程与工具调用）
  - **问题**: `FRAMEWORK_RUNNING_CHARACTER` 强调用工具后“停止”，但未在主循环对“先提示后停”的约束进行校验；当大模型直接产出非代码且意图识别未返回工具时，可能出现状态不一致。
  - **行动**: 在主循环中添加保护：当 assistant 明确声明将运行某工具而意图识别未返回对应工具时，回退一次并追加澄清提示；写入 `tool_conversations` 以便事后排查。

- [ ] 工具链注册与文档同步
  - **问题**: 仅注册了 `CodeRunner` 与 `continue_analyze` 两个本地工具，但 `tools_configs.py` 描述了更多工具，且 `AGENT_TOOLS_GUIDE` 只展示了 `CodeRunner`。
  - **行动**: 分阶段引入其余工具的“占位注册 + 幂等判空实现”，并在 `AGENT_TOOLS_GUIDE` 补充到可见工具清单；README 同步工具用法与示例。

- [ ] CodeRunner 安全域与第三方库白名单
  - **问题**: `utils/code_runner.py` 中 `allowed_modules` 包含 `open`, `file`, `input`, `raw_input` 等并非模块名；网络/系统危害项管控分散。
  - **行动**: 清理白名单为真实模块；抽离“危险内建/属性/模块”集中常量；增加磁盘/网络访问策略开关；将默认安全级别设为 `strict`，在工具参数中放宽。

- [ ] 代码执行的持久化上下文隔离
  - **问题**: 持久化上下文跨多问题共享可能造成污染；缺少 per-user、per-session 隔离与上限控制。
  - **行动**: 以 `user_id`/`agent_name` 为 key 建立隔离命名空间；限制上下文变量数量与总体内存；提供 `reset_context` 工具化入口。

- [ ] 工具输出截断与二次总结提示
  - **问题**: 工具可能输出很长内容，当前只在 CodeRunner 限制 stdout/stderr 长度；对其他工具缺少统一截断与“继续阅读”策略。
  - **行动**: 在 `AgentStateManager.add_message('tool', ...)` 前对长文本统一截断并生成摘要；将原文保存为外部文件并给出可回看路径。

- [ ] 意图 JSON 解析健壮性
  - **问题**: 解析失败时直接返回 `END_CONVERSATION()`；且 `tools` 字段与注释的 `tool` 命名在提示词中存在冲突；
  - **行动**: 解析失败时尝试二次纠错（提取第一行内联 JSON）；名称冲突统一为 `tools`；如果返回空，退回“澄清意图”流程。

- [ ] 代码片段提取器统一
  - **问题**: `tools_agent/code_interpreter.py` 与 `utils/code_runner.py` 都实现了 `extract_python_code`；存在重复。
  - **行动**: 在 `utils` 下保留一个实现，其他模块统一从该处导入；避免重复维护。

- [ ] 事件与操作日志（前后端统一）
  - **问题**: 缺少用户每一步操作的统一记录与结构化格式，难以追踪问题。
  - **行动**: 统一定义事件 schema（时间、级别、模块、用户ID、会话ID、动作、参数hash、耗时）；所有工具入口与主循环关键分支都发事件。

- [ ] 配置外置与多环境支持
  - **问题**: 模型名、端点、阈值写死在代码中；不同 provider 的 endpoint key 映射分散。
  - **行动**: 在根目录新增 `.env.example` 与 `config/`；将模型与端点、开关、阈值参数化；README 提供环境配置说明。

- [ ] README 与开发者指南完善
  - **问题**: 项目 README 尚未系统介绍“先答复-再判意图-工具执行-END() 停止”的核心机制与调试方法。
  - **行动**: 在 README 增补架构图/流程图、快速开始、工具扩展步骤、日志/排错指南、常见问题。

- [ ] Notebook 与代码路径同步
  - **问题**: `1. llm_api_test.ipynb`、`2. agent_test.ipynb` 存在，但与主框架行为未关联；
  - **行动**: 在 README 中说明如何用 Notebook 驱动 `Agent` 调试；将示例输入/输出持久化到 `files/{user}/{agent}/`。

- [ ] 统一异常与用户友好错误返回
  - **问题**: provider 与工具层异常提示不统一；
  - **行动**: 定义统一错误对象与可读消息；在前端渲染时支持 markdown 高亮与折叠详情。

- [ ] 性能与超时策略
  - **问题**: 工具循环缺少整体超时与最大轮数；
  - **行动**: 增加全局 `max_rounds`、单工具 `max_time`、整体 `hard_timeout`；在日志中标注中断原因。

- [ ] 测试与回归样例
  - **问题**: 缺少对核心模块（意图解析、END 识别、CodeRunner 安全检查）的回归用例；
  - **行动**: 增加最小化单元/集成测试样例（可先手动脚本形式），覆盖关键分支。


