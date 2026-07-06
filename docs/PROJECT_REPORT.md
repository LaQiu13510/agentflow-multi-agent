# AgentFlow Project Report

## Overview

AgentFlow is a multi-agent orchestration application for LLM workflows. It demonstrates how to route a user task through a Supervisor, execute it with specialized workers, call external systems through a tool protocol, and return an answer with an execution trace.

The project is designed as a runnable local system rather than a static prototype. It includes a Streamlit UI, deterministic tests, live health checks, database-backed memory, and a tool registry.

## Goals

AgentFlow focuses on four engineering goals:

1. Make agent routing explicit and observable.
2. Separate worker logic from tool implementations.
3. Reuse an existing retrieval system as an agent tool.
4. Keep the local demo stable even when an external service is temporarily unavailable.

## Core Workflow

```text
Input message
  -> load_memory
  -> supervisor
  -> selected worker
  -> tool calls
  -> final answer
  -> memory write
```

The workflow is implemented with LangGraph `StateGraph`. Each node updates a shared state object containing messages, route metadata, tool observations, the worker output, and latency.

## Worker Roles

| Worker | Responsibility | Typical Tools |
| --- | --- | --- |
| researcher | Retrieve and summarize knowledge | PostgreSQL, Milvus |
| engineer | Design modules, interfaces, and tests | Project tools, Milvus |
| writer | Produce project documentation text | Project tools |
| general | Coordinate lightweight tasks | Project tools |

## Tool Layer

AgentFlow implements a local MCP-style protocol. Each server exposes:

- `list_tools()`: returns tool names, descriptions, and input schema.
- `call_tool(name, **kwargs)`: executes a named tool and returns a structured result.

The current servers are:

- PostgreSQL server for metadata and table-safe queries.
- Milvus server for SmartKB vector search.
- Project server for engineering summaries and quality checklists.

## Memory Design

The memory module writes conversation turns to PostgreSQL when the database is available. If connection or table initialization fails, it falls back to an in-memory implementation with the same interface. This keeps UI demos and offline tests stable while preserving production-like behavior for live runs.

## SmartKB Integration

AgentFlow can query the SmartKB Milvus collection produced by `smartkb-rag`. This creates a clean separation:

- SmartKB owns document ingestion, chunking, embedding, retrieval, and answer generation.
- AgentFlow owns task routing, worker specialization, tool orchestration, and execution traces.

## UI

The Streamlit app exposes:

- Current route and route reason.
- Worker output.
- Tool names and observations.
- Latency.
- Memory backend and message count.
- Service health checks.

## Validation

The project includes two test scripts:

- `test_imports.py`: configuration, imports, tool registry, keyword routing, memory fallback.
- `test_e2e.py`: offline LangGraph end-to-end execution with fake LLM and fake MCP servers.

Both scripts support a `--live` mode for external service health checks.

## Current Status

AgentFlow is complete as a local multi-agent demo:

- The UI starts with Streamlit.
- Offline tests pass without external services.
- Live checks verify LLM, embedding, PostgreSQL, and Milvus connectivity.
- GitHub documentation and safe configuration templates are included.
