# AgentFlow

AgentFlow is a local multi-agent coordination platform for LLM applications. It uses LangGraph to route user tasks through a Supervisor node, delegates work to specialized workers, and exposes PostgreSQL, Milvus, and SmartKB retrieval through MCP-style tools.

## Features

- LangGraph Supervisor workflow with explicit state transitions.
- Four worker roles: researcher, engineer, writer, and general coordinator.
- MCP-style local tool protocol with `list_tools` and `call_tool` interfaces.
- PostgreSQL-backed short-term memory with in-memory fallback for demos and tests.
- Milvus retrieval over the SmartKB collection from `smartkb-rag`.
- Streamlit UI showing route decisions, tool calls, observations, latency, and memory status.
- Offline deterministic tests plus live health checks for external services.

## Architecture

```text
User task
  -> load_memory
  -> supervisor route
  -> researcher | engineer | writer | general
  -> MCP-style tools
       -> PostgreSQL metadata and memory
       -> Milvus SmartKB retrieval
       -> Project engineering helper tools
  -> finalize answer and trace
  -> save_memory
```

## Directory Structure

```text
agentflow-multi-agent/
├── app.py
├── config.py
├── test_imports.py
├── test_e2e.py
├── agent_team/
│   ├── supervisor.py
│   ├── memory.py
│   └── workers/
├── models/
├── tools/
│   ├── mcp_base.py
│   └── mcp_servers/
└── docs/
```

## Quick Start

```powershell
cd agentflow-multi-agent
E:\Anaconda_envs\envs\langchain\python.exe test_imports.py
E:\Anaconda_envs\envs\langchain\python.exe test_e2e.py
streamlit run app.py --server.port 8502
```

Open http://localhost:8502.

## Live Checks

The default tests avoid external network calls. To verify DeepSeek, embedding, PostgreSQL, and Milvus connections:

```powershell
E:\Anaconda_envs\envs\langchain\python.exe test_imports.py --live
E:\Anaconda_envs\envs\langchain\python.exe test_e2e.py --live
```

## Configuration

AgentFlow first reads `SMARTKB_PROJECT_DIR/.env`, then allows `agentflow-multi-agent/.env` to override values. Use `.env.example` as a template. Do not commit real API keys or database credentials.

## Documentation

- `docs/PROJECT_REPORT.md`: complete project report.
- `docs/ARCHITECTURE.md`: system design and module responsibilities.
- `docs/MCP_TOOLS.md`: local MCP-style tool protocol and tool catalog.
- `docs/EVALUATION.md`: test strategy and validation results.
