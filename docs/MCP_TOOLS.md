# MCP-Style Tools

AgentFlow uses an in-process MCP-style protocol. It is intentionally lightweight, but it keeps the same architectural boundary: agents discover tools from servers and call them through a structured interface.

## Base Types

- `ToolSpec`: name, description, input schema.
- `ToolResult`: success flag, content, metadata.
- `LocalMCPServer`: base class for servers.
- `ToolRegistry`: multi-server registry used by workers.

## PostgreSQL Server

Server name: `postgres`

| Tool | Purpose |
| --- | --- |
| `health` | Check database connectivity |
| `list_tables` | Inspect available tables |
| `list_smartkb_documents` | List SmartKB document metadata |
| `safe_select` | Run limited read-only queries against allowed tables |

## Milvus Server

Server name: `milvus`

| Tool | Purpose |
| --- | --- |
| `health` | Check Milvus connectivity |
| `collection_stats` | Inspect SmartKB vector count |
| `search_smartkb` | Retrieve relevant SmartKB chunks |

## Project Server

Server name: `project`

| Tool | Purpose |
| --- | --- |
| `engineering_requirements` | Provide common LLM application engineering requirements |
| `project_summary` | Generate a compact project summary |
| `quality_checklist` | Produce quality checks for the supplied stack |

## Why This Shape

The local implementation avoids the operational cost of multiple background processes while preserving the key design idea: workers depend on tool contracts, not direct database or vector-store code.
