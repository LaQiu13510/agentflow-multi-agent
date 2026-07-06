"""短期记忆。

优先使用 PostgreSQL 持久化；数据库暂不可用时降级为进程内记忆，保证 Demo 和测试可运行。
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import AGENTFLOW_MEMORY_TABLE, DB_URL


class Base(DeclarativeBase):
    pass


class AgentMemoryRecord(Base):
    __tablename__ = AGENTFLOW_MEMORY_TABLE

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    route = Column(String(32), default="")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentMemory:
    """用 PostgreSQL 保存 AgentFlow 的短期对话记忆。"""

    def __init__(self, database_url: str = DB_URL):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.session_factory = sessionmaker(bind=self.engine)

    def init_tables(self):
        Base.metadata.create_all(self.engine)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        route: str = "",
    ):
        self.init_tables()
        with self.session_factory() as session:
            session.add(
                AgentMemoryRecord(
                    session_id=session_id,
                    role=role,
                    content=content[:6000],
                    route=route,
                )
            )
            session.commit()

    def recent_context(self, session_id: str, limit: int = 6) -> str:
        self.init_tables()
        with self.session_factory() as session:
            rows = (
                session.query(AgentMemoryRecord)
                .filter_by(session_id=session_id)
                .order_by(AgentMemoryRecord.created_at.desc())
                .limit(limit)
                .all()
            )
        if not rows:
            return "暂无历史记忆。"

        lines = []
        for row in reversed(rows):
            prefix = f"{row.role}"
            if row.route:
                prefix += f"/{row.route}"
            lines.append(f"{prefix}: {row.content[:300]}")
        return "\n".join(lines)

    def stats(self) -> dict:
        self.init_tables()
        with self.session_factory() as session:
            total = session.query(AgentMemoryRecord).count()
            sessions = {
                row[0]
                for row in session.query(AgentMemoryRecord.session_id).distinct().all()
            }
        return {"backend": "postgresql", "total_messages": total, "sessions": len(sessions)}


@dataclass
class InMemoryRecord:
    session_id: str
    role: str
    content: str
    route: str
    created_at: datetime


class InMemoryAgentMemory:
    """PostgreSQL 不可用时的轻量降级实现。"""

    def __init__(self, reason: str = ""):
        self.reason = reason
        self.rows: list[InMemoryRecord] = []

    def init_tables(self):
        return None

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        route: str = "",
    ):
        self.rows.append(
            InMemoryRecord(
                session_id=session_id,
                role=role,
                content=content[:6000],
                route=route,
                created_at=datetime.utcnow(),
            )
        )

    def recent_context(self, session_id: str, limit: int = 6) -> str:
        rows = [row for row in self.rows if row.session_id == session_id][-limit:]
        if not rows:
            return "暂无历史记忆。"

        lines = []
        for row in rows:
            prefix = f"{row.role}"
            if row.route:
                prefix += f"/{row.route}"
            lines.append(f"{prefix}: {row.content[:300]}")
        return "\n".join(lines)

    def stats(self) -> dict:
        sessions = {row.session_id for row in self.rows}
        return {
            "backend": "memory",
            "total_messages": len(self.rows),
            "sessions": len(sessions),
            "fallback_reason": self.reason,
        }


_memory_instance: AgentMemory | InMemoryAgentMemory | None = None


def get_memory() -> AgentMemory | InMemoryAgentMemory:
    global _memory_instance
    if _memory_instance is None:
        try:
            _memory_instance = AgentMemory()
            _memory_instance.init_tables()
        except Exception as exc:
            _memory_instance = InMemoryAgentMemory(str(exc)[:200])
    return _memory_instance
