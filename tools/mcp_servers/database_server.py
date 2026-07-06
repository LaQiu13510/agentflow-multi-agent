"""PostgreSQL MCP 风格服务。"""

from sqlalchemy import create_engine, inspect, text

from config import AGENTFLOW_MEMORY_TABLE, DB_URL
from tools.mcp_base import LocalMCPServer, ToolResult, ToolSpec


class PostgreSQLMCPServer(LocalMCPServer):
    server_name = "postgres"

    def __init__(self):
        self.engine = create_engine(DB_URL, pool_pre_ping=True) if DB_URL else None
        super().__init__()

    def register_tools(self):
        self.add_tool(ToolSpec("health", "检查 PostgreSQL 连接"), self.health)
        self.add_tool(ToolSpec("list_tables", "列出当前数据库表"), self.list_tables)
        self.add_tool(
            ToolSpec("list_smartkb_documents", "读取 SmartKB 文档元数据"),
            self.list_smartkb_documents,
        )
        self.add_tool(
            ToolSpec(
                "safe_select",
                "执行只读 SELECT 查询，仅允许常用演示表",
                {"sql": "SELECT ... LIMIT 20"},
            ),
            self.safe_select,
        )

    def health(self) -> ToolResult:
        if self.engine is None:
            return ToolResult(False, "DB_URL 未配置")
        with self.engine.connect() as conn:
            conn.execute(text("select 1"))
        return ToolResult(True, "PostgreSQL 连接正常")

    def list_tables(self) -> ToolResult:
        if self.engine is None:
            return ToolResult(False, "DB_URL 未配置")
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        return ToolResult(True, "\n".join(tables), {"count": len(tables)})

    def list_smartkb_documents(self, limit: int = 10) -> ToolResult:
        if self.engine is None:
            return ToolResult(False, "DB_URL 未配置。请复制 .env.example 并填写数据库连接。")
        inspector = inspect(self.engine)
        if "documents" not in inspector.get_table_names():
            return ToolResult(
                False,
                "未找到 SmartKB documents 表。请先运行项目一并加载示例文档。",
            )

        sql = text(
            """
            select file_name, file_type, chunk_count, status, created_at
            from documents
            order by created_at desc
            limit :limit
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"limit": limit}).mappings().all()

        if not rows:
            return ToolResult(True, "SmartKB 暂无文档记录", {"rows": []})

        lines = [
            f"- {r['file_name']} ({r['file_type']}, {r['chunk_count']} chunks, {r['status']})"
            for r in rows
        ]
        return ToolResult(True, "\n".join(lines), {"rows": [dict(r) for r in rows]})

    def safe_select(self, sql: str) -> ToolResult:
        if self.engine is None:
            return ToolResult(False, "DB_URL 未配置")
        normalized = sql.strip().lower()
        allowed_tables = [
            "documents",
            "evaluation_records",
            "chat_history",
            AGENTFLOW_MEMORY_TABLE,
        ]
        if not normalized.startswith("select"):
            return ToolResult(False, "只允许 SELECT 查询")
        if not any(table in normalized for table in allowed_tables):
            return ToolResult(False, f"只允许查询这些表: {', '.join(allowed_tables)}")
        if " limit " not in normalized:
            sql = f"{sql.rstrip(';')} limit 20"

        with self.engine.connect() as conn:
            rows = conn.execute(text(sql)).mappings().all()

        preview = "\n".join(str(dict(row)) for row in rows[:20])
        return ToolResult(True, preview or "查询结果为空", {"row_count": len(rows)})
