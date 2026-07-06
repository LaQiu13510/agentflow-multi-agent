"""Project-oriented MCP style service."""

from tools.mcp_base import LocalMCPServer, ToolResult, ToolSpec


class ProjectMCPServer(LocalMCPServer):
    """Generic project support tools used by AgentFlow workers."""

    server_name = "project"

    def register_tools(self):
        self.add_tool(
            ToolSpec(
                "engineering_requirements",
                "Return common engineering requirements for LLM applications.",
            ),
            self.engineering_requirements,
        )
        self.add_tool(
            ToolSpec(
                "project_summary",
                "Generate a concise project summary.",
                {"project": "SmartKB or AgentFlow"},
            ),
            self.project_summary,
        )
        self.add_tool(
            ToolSpec(
                "quality_checklist",
                "Return a quality checklist for the supplied technology stack.",
                {"stack": "Python, LangGraph, RAG"},
            ),
            self.quality_checklist,
        )

    def engineering_requirements(self) -> ToolResult:
        content = "\n".join(
            [
                "LLM application engineering requirements:",
                "- Clear API and configuration boundaries",
                "- Reliable LLM and embedding provider wrappers",
                "- Retrieval, memory, and tool-calling modules with observable outputs",
                "- Persistent storage for metadata, sessions, or task records",
                "- Repeatable tests for imports, routing, tools, and end-to-end flows",
                "- A local demo UI that exposes internal execution traces",
            ]
        )
        return ToolResult(True, content)

    def project_summary(self, project: str) -> ToolResult:
        if "agent" in project.lower() or "flow" in project.lower():
            content = (
                "AgentFlow coordinates specialized workers through a LangGraph "
                "Supervisor. Workers call MCP-style tools for PostgreSQL, Milvus, "
                "and project knowledge retrieval, then return a traceable final answer."
            )
        else:
            content = (
                "SmartKB is a retrieval-augmented question-answering system. It loads "
                "documents, chunks them, embeds them, stores vectors in Milvus, combines "
                "dense retrieval with BM25, and generates grounded answers with DeepSeek."
            )
        return ToolResult(True, content)

    def quality_checklist(self, stack: str) -> ToolResult:
        normalized = stack.lower()
        suggestions = []
        if "langgraph" in normalized:
            suggestions.append("Expose graph nodes, route reasons, and worker outputs.")
        if "rag" in normalized:
            suggestions.append("Track retrieval metrics such as Hit Rate and MRR.")
        if "mcp" in normalized:
            suggestions.append("Keep tool schemas explicit and tool outputs inspectable.")
        if "postgres" in normalized:
            suggestions.append("Use migrations or table initialization checks for metadata.")
        if not suggestions:
            suggestions.append("Add health checks, deterministic tests, and demo data.")
        return ToolResult(True, "\n".join(f"- {item}" for item in suggestions))
