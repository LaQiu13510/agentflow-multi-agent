# AgentFlow 系统架构

## 核心流程

```text
FastAPI 请求
  -> Redis 运行时保护
       -> 会话状态
       -> 每分钟限流
       -> 每日预算
       -> 任务状态
  -> load_memory
       -> 短期会话记忆
       -> 长期任务经验检索
  -> supervisor
       -> SkillRegistry 多意图识别
       -> 独占 Skill 冲突处理
  -> plan_tools
       -> 按 Worker 生成工具计划
  -> 单 Worker
     或 collaboration 多 Worker 顺序协作
  -> coordinate 协调结果
  -> finalize
  -> save_memory
       -> 短期记忆
       -> 长期记忆
       -> AgentTraceStore
       -> LangGraph Checkpoint
```

## 状态模型

`AgentFlowState` 在图节点间传递以下关键信息：

- `messages`：LangChain 消息。
- `session_id`、`task_id`：会话和任务标识。
- `task`：当前用户任务。
- `route`、`route_reason`：单 Worker 路由或 `collaboration`。
- `skill_names`、`worker_routes`：命中的技能和有序 Worker 链。
- `worker_tool_plans`：每个 Worker 的独立工具计划。
- `short_term_context`、`long_term_context`：两类记忆上下文。
- `worker_outputs`、`worker_observations`：每个 Worker 的输出和工具结果。
- `used_tools`、`latency_ms`：执行统计。
- `trace_record`：最终持久化追踪记录。

## 路由策略

1. `SkillRegistry.match_all()` 根据触发词位置、优先级和独占规则识别技能。
2. 图片生成属于高优先级独占 Skill，避免“架构图”同时被 Engineer 抢占。
3. 命中一个技能时进入单 Worker 分支。
4. 命中多个不同 Worker 的技能时进入 `collaboration` 分支，并按用户描述中的顺序执行。
5. 没有稳定 Skill 命中时，Supervisor 使用 LLM JSON 路由降级。

## 多 Worker 协作

协作节点依次执行 Worker。前一个 Worker 的结果会追加到后一个 Worker 的任务上下文，因此“先检索资料，再写报告”会先由 Researcher 获取证据，再由 Writer 基于证据生成内容。所有 Worker 完成后，`coordinate` 节点调用 Supervisor 整合结果并删除重复信息。

## 工具规划

Skill 提供推荐工具，`plan_tools` 节点根据当前工具注册表过滤不存在的工具，并为每个 Worker 保存独立计划。Worker 通过统一执行器调用工具，参数在执行前根据 Python 函数签名和类型标注校验。

## 记忆与上下文

- 短期记忆保存近期对话。
- 长期记忆保存任务、答案、路由和 Skill 摘要，并按相关性检索。
- ContextManager 对任务、记忆、上游结果和工具观察分别设置预算，避免 Prompt 无限增长。
- PostgreSQL 不可用时，短期和长期记忆均有内存降级实现。

## Checkpoint 与恢复

LangGraph 使用 `task_id` 作为 `thread_id` 保存图状态。Checkpoint 接口可以查看下一待执行节点、路由和工具计划；存在待执行节点时，Resume 接口使用相同配置继续执行。

## 可观察性

SSE 输出真实图节点更新。Trace 以 JSONL 保存任务、路由、技能、Worker 链、工具计划、观察结果、最终答案和延迟。Redis 运行时状态保存任务阶段、工具调用次数、预算和限流信息。
