# AgentFlow 项目设计说明

## 项目目标

AgentFlow 用于解决复杂 AI 任务中单 Agent 同时承担路由、检索、工程设计、写作和工具调用导致的职责混乱问题。项目强调任务分工、上下文控制、执行恢复和可观察性，而不是只展示一次模型调用。

## 关键设计

### Supervisor 与 Skill

Supervisor 负责识别任务意图。高置信度任务先由 SkillRegistry 确定性匹配，开放任务再进入 LLM 路由。Skill 定义触发词、优先级、独占规则、输入输出契约和推荐工具，使路由规则与 Worker 代码解耦。

### 多 Worker 协作

单意图任务只执行一个 Worker。复合任务生成有序 Worker 链，并把上游结果传给下游。协调节点最终整合多个结果，避免直接把各 Worker 文本简单拼接给用户。

### 工具层

所有 Worker 使用相同的工具计划执行器。MCP 风格注册表统一提供工具发现、参数校验、错误封装和元数据返回，数据库、向量库和图片服务不会直接耦合到 Worker 实现。

### 上下文与记忆

ContextManager 分别控制历史记忆和工具证据预算。短期记忆保存会话，长期记忆沉淀可复用任务经验，并在后续任务中按相关性注入。多 Worker 协作时，上游输出也受上下文组织约束。

### 可靠性与恢复

Redis 运行时层提供会话 TTL、限流、预算和任务状态。LangGraph Checkpointer 保存图状态，任务中断后可通过相同 `thread_id` 恢复。外部存储不可用时，记忆和运行时状态有内存降级路径。

### 可观察性

FastAPI SSE 输出真实图节点进度。AgentTraceStore 记录路由原因、技能命中、Worker 链、工具计划、实际调用、观察结果、延迟和最终回答，便于调试和复盘。

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `agent_team/supervisor.py` | LangGraph 编排、协作和协调 |
| `agent_team/skills.py` | Skill 定义、优先级和多意图匹配 |
| `agent_team/workers/` | 专业 Worker 与统一工具执行器 |
| `agent_team/context.py` | Prompt 上下文预算与组织 |
| `agent_team/memory.py` | 短期记忆 |
| `agent_team/long_term_memory.py` | 长期任务经验 |
| `agent_team/runtime_state.py` | Redis / 内存运行时保护 |
| `agent_team/tracing.py` | JSONL 执行追踪 |
| `tools/` | MCP 风格工具层 |
| `app.py` | FastAPI、SSE、任务和恢复接口 |
| `eval/agent_eval.py` | 单意图与多意图评测 |

## 已知边界

- 当前多 Worker 协作采用有序执行，适合存在上下游依赖的任务；完全独立的子任务尚未并行执行。
- 工具层是进程内 MCP 风格实现，不等同于独立官方 MCP Server。
- 默认 Checkpointer 为内存实现，生产部署可替换为持久化 Checkpointer。
- 规则未命中的语义改写依赖 LLM 路由，离线 Skill 评测不会覆盖这部分能力。
