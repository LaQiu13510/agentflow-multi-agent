# AgentFlow 多 Agent 协作平台

AgentFlow 面向复杂 AI 任务中单 Agent 职责混杂、工具调用耦合、上下文膨胀和执行过程难以复盘的问题，构建基于 Supervisor、Skill 和 Worker 的多 Agent 协作平台，支持复合任务拆解、工具规划、记忆管理、断点恢复和执行追踪。

## 核心能力

- 使用 LangGraph 构建 `load_memory -> supervisor -> plan_tools -> worker/collaboration -> coordinate -> trace` 工作流。
- 支持 Researcher、Engineer、Writer、General 四类 Worker，分别处理知识检索、工程设计、技术写作和通用任务。
- 支持复合意图识别和多 Worker 顺序协作，上游 Worker 的结果会作为下游 Worker 的任务上下文，最终由 Supervisor 统一整合。
- 使用 SkillRegistry 管理触发词、优先级、独占规则、输入 Schema、输出格式、建议工具和降级路由。
- 图片生成 Skill 使用高优先级独占匹配，架构图、流程图等请求直接进入 `gpt-image-2` 生图工具。
- 使用 MCP 风格工具层统一封装 PostgreSQL、Milvus、项目分析和图片生成工具，并基于 Python 函数签名校验工具参数。
- 使用 ContextManager 统一裁剪用户任务、短期记忆、长期记忆、上游 Worker 结果和工具观察。
- 使用 PostgreSQL 保存短期会话与长期任务经验；数据库不可用时自动降级为内存实现。
- 使用 Redis 保存会话状态、任务状态、限流计数、预算用量和工具调用统计。
- 使用 LangGraph Checkpointer 保存任务图状态，提供 Checkpoint 查询和 Resume 接口。
- 使用 AgentTraceStore 持久化路由、技能、Worker 计划、工具调用、观察结果、延迟和最终回答。
- 提供 FastAPI 页面和 API，SSE 会实时输出 LangGraph 节点执行进度和最终回答。
- 提供 Docker Compose、GitHub Actions、离线端到端测试和多意图路由评测。

## 技术栈

Python、FastAPI、LangGraph、LangChain、Multi-Agent、Skills、MCP 风格工具协议、Redis、PostgreSQL、Milvus、Docker Compose、SSE

## 协作流程

```text
用户任务
  -> 运行时保护：会话、限流、预算、任务状态
  -> 加载短期记忆与长期记忆
  -> Supervisor + SkillRegistry 识别单一或复合意图
  -> 为每个 Worker 生成独立工具计划
  -> 单 Worker 执行
     或
     多 Worker 顺序协作并传递上游结果
  -> Supervisor 协调并整合最终答案
  -> 写入记忆、Checkpoint、运行时状态和 Trace
  -> FastAPI / SSE 返回执行进度与结果
```

## Worker 分工

| Worker | 主要职责 | 常用工具 |
| --- | --- | --- |
| `researcher` | 检索知识库、整理证据、标注来源 | PostgreSQL、Milvus |
| `engineer` | 设计架构、接口、实现步骤、测试与风险控制 | 项目分析、Milvus |
| `writer` | 生成 README、技术报告、摘要和发布说明 | 项目摘要、质量清单 |
| `general` | 处理通用任务和图片生成 | 项目工具、图片生成 |

## 目录结构

```text
agentflow-multi-agent/
├── app.py                  # FastAPI 页面、API、SSE 与运行时保护
├── config.py               # 环境变量和运行参数
├── agent_team/
│   ├── context.py          # 上下文预算与组织
│   ├── long_term_memory.py # 长期任务经验
│   ├── memory.py           # 短期会话记忆
│   ├── runtime_state.py    # Redis / 内存运行时状态
│   ├── safety.py           # 脱敏、预算估算和工具限制
│   ├── skills.py           # SkillRegistry
│   ├── supervisor.py       # LangGraph 多 Agent 工作流
│   ├── tracing.py          # JSONL 执行追踪
│   └── workers/            # 四类 Worker
├── tools/                  # MCP 风格协议、注册表与工具服务
├── eval/                   # 单意图和多意图路由评测
├── docs/                   # 架构、评测和工具说明
├── test_imports.py
├── test_e2e.py
├── Dockerfile
└── compose.yml
```

## 快速开始

### 本地运行

```bash
git clone <你的仓库地址>
cd agentflow-multi-agent
python -m venv .venv
```

激活虚拟环境后安装依赖：

```bash
python -m pip install -r requirements.txt
```

复制环境变量模板并填写自己的配置：

```bash
cp .env.example .env
```

启动服务：

```bash
uvicorn app:app --host 0.0.0.0 --port 8502
```

浏览器访问 `http://127.0.0.1:8502`，接口文档位于 `http://127.0.0.1:8502/docs`。

### Docker Compose

配置 `.env` 后执行：

```bash
docker compose up --build
```

Compose 会启动 AgentFlow、PostgreSQL、Redis、Milvus、etcd 和 MinIO，并配置健康检查与持久卷。

## 关键配置

```env
DEEPSEEK_MODEL=deepseek-v4-flash
AGENTFLOW_LONG_TERM_MEMORY_LIMIT=4
AGENTFLOW_SESSION_TTL_SECONDS=86400
AGENTFLOW_RATE_LIMIT_PER_MINUTE=20
AGENTFLOW_DAILY_BUDGET_UNITS=50000
MAX_TOOL_CALLS_PER_WORKER=4
IMAGE_API_BASE=https://www.right.codes/draw/v1
IMAGE_MODEL=gpt-image-2
```

完整配置见 `.env.example`。密钥只应保存在本地 `.env` 中，该文件已被 Git 忽略。

## 示例任务

```text
先检索 SmartKB 中关于混合检索的资料，再写一份技术摘要
设计一个 MCP Server，并给出接口和测试方案
生成一张多 Agent 协作架构图
根据已有任务经验补充部署风险清单
```

## 主要接口

| 接口 | 说明 |
| --- | --- |
| `POST /api/run` | 执行 Agent 任务 |
| `GET /api/run/stream` | SSE 输出图节点进度和最终回答 |
| `GET /api/tasks/{task_id}` | 查询运行时任务状态 |
| `GET /api/checkpoints/{task_id}` | 查询 LangGraph Checkpoint |
| `POST /api/tasks/{task_id}/resume` | 从待执行节点恢复任务 |
| `GET /api/traces` | 查看最近执行追踪 |
| `GET /api/memory` | 查看短期和长期记忆状态 |
| `GET /api/runtime` | 查看 Redis 运行时状态与任务 |

## 测试与评测

默认检查使用 Fake LLM 和 Fake MCP Server，不依赖外部服务：

```bash
python test_imports.py
python test_e2e.py
python eval/agent_eval.py
python eval/context_eval.py
```

配置外部服务后可执行连通性检查：

```bash
python test_imports.py --live
python test_e2e.py --live
```

## 项目文档

- `docs/ARCHITECTURE.md`：状态模型、多 Worker 协作和数据流。
- `docs/EVALUATION.md`：离线测试、路由评测和外部服务检查。
- `docs/MCP_TOOLS.md`：工具协议与工具清单。
- `docs/PROJECT_REPORT.md`：项目目标、设计取舍和模块职责。

> 当前工具层是进程内 MCP 风格实现，重点展示工具契约、发现、参数校验和统一调用边界；它不是独立进程的官方 MCP Server 实现。
