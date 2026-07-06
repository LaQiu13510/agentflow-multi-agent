"""AgentFlow tool registry."""

from tools.mcp_base import ToolRegistry
from tools.mcp_servers.database_server import PostgreSQLMCPServer
from tools.mcp_servers.project_server import ProjectMCPServer
from tools.mcp_servers.vector_server import MilvusMCPServer


def build_tool_registry() -> ToolRegistry:
    """Build the default tool registry."""
    return ToolRegistry(
        [
            PostgreSQLMCPServer(),
            MilvusMCPServer(),
            ProjectMCPServer(),
        ]
    )
