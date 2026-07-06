# AgentFlow Architecture

## Components

```text
app.py
  Streamlit UI and health checks

agent_team/supervisor.py
  LangGraph workflow, route selection, finalization, memory write

agent_team/workers/
  Worker implementations for research, engineering, writing, and general tasks

models/
  DeepSeek LLM wrapper and embedding wrapper

tools/
  MCP-style base protocol, registry, and concrete tool servers

agent_team/memory.py
  PostgreSQL memory and in-memory fallback
```

## State Model

`AgentFlowState` stores the runtime data shared across graph nodes:

- `messages`: LangChain messages.
- `session_id`: memory namespace.
- `task`: latest user task.
- `route`: selected worker name.
- `route_reason`: keyword or LLM routing explanation.
- `memory_context`: recent session context.
- `worker_output`: raw worker response.
- `final_answer`: final response shown to the user.
- `observations`: tool call outputs.
- `used_tools`: tool names.
- `latency_ms`: execution time.

## Routing Strategy

Routing uses two layers:

1. Keyword routing for high-confidence common tasks.
2. LLM JSON routing fallback when keywords are insufficient.

This keeps common demos fast and deterministic while still supporting open-ended input.

## Tool Registry

The registry stores MCP-style servers by name. Workers call tools through:

```python
self.tools.call("server", "tool", **kwargs)
```

This keeps worker code independent from PostgreSQL, Milvus, or any specific business logic implementation.

## Failure Handling

- Tool calls return `ToolResult(success, content, metadata)` instead of raw exceptions.
- PostgreSQL memory falls back to in-memory storage.
- Live checks are separate from offline tests.
- `.env.example` documents configuration without exposing credentials.
