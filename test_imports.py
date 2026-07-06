"""AgentFlow 基础导入与结构检查。

默认不访问外部 API；加上 --live 时检查 DeepSeek、Embedding、PostgreSQL、Milvus。
"""

from __future__ import annotations

import sys
import py_compile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")


def step(name: str, fn):
    print(f"[TEST] {name} ...", end=" ")
    try:
        result = fn()
        print("[OK]")
        if result:
            print(f"       {result}")
    except Exception as exc:
        print("[FAIL]")
        print(f"       {type(exc).__name__}: {exc}")
        raise


def check_config():
    import config

    assert config.ROOT_DIR.exists()
    assert config.DATA_DIR.exists()
    assert config.DOCS_DIR.exists()
    assert config.DEFAULT_SESSION_ID
    return f"root={config.ROOT_DIR}"


def check_core_imports():
    import models.embedding  # noqa: F401
    import models.llm  # noqa: F401
    warnings.filterwarnings("ignore")
    import agent_team.memory  # noqa: F401
    import agent_team.supervisor  # noqa: F401
    import tools.mcp_base  # noqa: F401
    py_compile.compile(str(Path(__file__).parent / "app.py"), doraise=True)
    return "核心模块导入成功，app.py 语法检查通过"


def check_registry():
    from tools.registry import build_tool_registry

    registry = build_tool_registry()
    tools = registry.list_tools()
    assert len(tools) >= 8
    names = {f"{item['server']}.{item['name']}" for item in tools}
    required = {
        "postgres.list_smartkb_documents",
        "milvus.search_smartkb",
        "project.project_summary",
    }
    assert required.issubset(names)
    return f"tools={len(tools)}"


def check_keyword_router():
    from agent_team.supervisor import SupervisorAgent

    router = SupervisorAgent._keyword_route
    assert router(None, "帮我写一段项目技术报告") == "writer"
    assert router(None, "设计 MCP server 的代码结构") == "engineer"
    assert router(None, "检索知识库里的 RAG 文档") == "researcher"
    return "keyword routes ok"


def check_memory_fallback():
    from agent_team.memory import InMemoryAgentMemory

    memory = InMemoryAgentMemory("test")
    memory.add_message("s1", "user", "你好", route="general")
    memory.add_message("s1", "assistant", "你好，我是 AgentFlow", route="general")
    context = memory.recent_context("s1")
    stats = memory.stats()
    assert "AgentFlow" in context
    assert stats["total_messages"] == 2
    return f"backend={stats['backend']}"


def live_checks():
    from models.embedding import get_embedding_model
    from models.llm import get_llm
    from tools.registry import build_tool_registry

    llm_ok, llm_msg = get_llm(max_tokens=64).test_connection()
    print(f"[LIVE] DeepSeek: {llm_ok} {llm_msg}")

    emb_ok, emb_msg = get_embedding_model().test_connection()
    print(f"[LIVE] Embedding: {emb_ok} {emb_msg}")

    registry = build_tool_registry()
    for server in ["postgres", "milvus"]:
        result = registry.call(server, "health")
        print(f"[LIVE] {server}: {result.success} {result.content}")


def main():
    step("配置加载", check_config)
    step("核心模块导入", check_core_imports)
    step("MCP 工具注册", check_registry)
    step("Supervisor 关键词路由", check_keyword_router)
    step("内存降级记忆", check_memory_fallback)

    if "--live" in sys.argv:
        step("外部服务连通", live_checks)

    print("\nAgentFlow import checks passed.")


if __name__ == "__main__":
    main()

