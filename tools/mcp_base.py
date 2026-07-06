"""
轻量 MCP 风格工具协议
====================
这里不启动独立进程，而是在同一 Python 进程中模拟 MCP Server 的核心接口：
list_tools 与 call_tool。
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    success: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalMCPServer:
    """本地 MCP 风格服务基类。"""

    server_name = "base"

    def __init__(self):
        self._tools: dict[str, tuple[ToolSpec, Callable[..., ToolResult]]] = {}
        self.register_tools()

    def register_tools(self):
        """子类注册工具。"""

    def add_tool(
        self,
        spec: ToolSpec,
        handler: Callable[..., ToolResult],
    ):
        self._tools[spec.name] = (spec, handler)

    def list_tools(self) -> list[ToolSpec]:
        return [spec for spec, _ in self._tools.values()]

    def call_tool(self, name: str, **kwargs) -> ToolResult:
        if name not in self._tools:
            return ToolResult(False, f"工具不存在: {self.server_name}.{name}")
        _, handler = self._tools[name]
        try:
            return handler(**kwargs)
        except Exception as exc:
            return ToolResult(False, f"{self.server_name}.{name} 调用失败: {exc}")


class ToolRegistry:
    """统一管理多个 MCP 风格服务。"""

    def __init__(self, servers: list[LocalMCPServer] | None = None):
        self.servers: dict[str, LocalMCPServer] = {}
        for server in servers or []:
            self.register(server)

    def register(self, server: LocalMCPServer):
        self.servers[server.server_name] = server

    def list_tools(self) -> list[dict[str, Any]]:
        rows = []
        for server_name, server in self.servers.items():
            for spec in server.list_tools():
                rows.append(
                    {
                        "server": server_name,
                        "name": spec.name,
                        "description": spec.description,
                        "input_schema": spec.input_schema,
                    }
                )
        return rows

    def call(self, server_name: str, tool_name: str, **kwargs) -> ToolResult:
        server = self.servers.get(server_name)
        if server is None:
            return ToolResult(False, f"MCP Server 不存在: {server_name}")
        return server.call_tool(tool_name, **kwargs)

