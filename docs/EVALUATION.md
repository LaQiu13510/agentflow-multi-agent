# Evaluation

## Test Strategy

AgentFlow separates deterministic workflow tests from live service checks.

## Offline Tests

```powershell
E:\Anaconda_envs\envs\langchain\python.exe test_imports.py
E:\Anaconda_envs\envs\langchain\python.exe test_e2e.py
```

Covered behavior:

- Configuration directories exist.
- Core modules import correctly.
- MCP tool registry exposes required tools.
- Keyword routing selects the expected worker.
- Memory fallback stores and reads session context.
- LangGraph executes researcher, engineer, and writer routes end to end.
- Tool traces and latency fields are populated.

## Live Checks

```powershell
E:\Anaconda_envs\envs\langchain\python.exe test_imports.py --live
E:\Anaconda_envs\envs\langchain\python.exe test_e2e.py --live
```

Live checks validate:

- DeepSeek chat API.
- Embedding provider.
- PostgreSQL connection.
- Milvus connection.

## UI Smoke Test

```powershell
streamlit run app.py --server.port 8502
```

The page should open at http://localhost:8502 and show the AgentFlow dashboard, examples, route metrics, and tool observations.
