"""AgentFlow 端到端流程测试。

默认使用 Fake LLM 与 Fake MCP Server，稳定验证 LangGraph 编排流程。
加上 --live 可以运行真实外部服务健康检查。
"""

from __future__ import annotations

import sys
import warnings

from langchain_core.messages import HumanMessage

from agent_team.long_term_memory import InMemoryLongTermMemory
from agent_team.memory import InMemoryAgentMemory
from tools.mcp_base import LocalMCPServer, ToolRegistry, ToolResult, ToolSpec

warnings.filterwarnings("ignore")


class FakeLLM:
    def chat(self, messages, temperature=None, max_tokens=None) -> str:
        task = str(messages[-1].content)[:120]
        return (
            "【离线测试回答】AgentFlow 已完成任务处理。\n"
            f"- 任务摘要: {task}\n"
            "- 输出包含工具证据、Worker 分工和可执行建议。"
        )

    def test_connection(self):
        return True, "fake llm ok"


class FakePostgresServer(LocalMCPServer):
    server_name = "postgres"

    def register_tools(self):
        self.add_tool(ToolSpec("health", "fake postgres health"), self.health)
        self.add_tool(ToolSpec("list_smartkb_documents", "fake documents"), self.list_docs)

    def health(self):
        return ToolResult(True, "Fake PostgreSQL 正常")

    def list_docs(self, limit: int = 8):
        return ToolResult(
            True,
            "- test_rag_guide_zh.md (md, 8 chunks, indexed)\n"
            "- test_hybrid_search_en.md (md, 4 chunks, indexed)",
        )


class FakeMilvusServer(LocalMCPServer):
    server_name = "milvus"

    def register_tools(self):
        self.add_tool(ToolSpec("health", "fake milvus health"), self.health)
        self.add_tool(ToolSpec("search_smartkb", "fake smartkb search"), self.search)

    def health(self):
        return ToolResult(True, "Fake Milvus 正常")

    def search(self, query: str, top_k: int = 4):
        return ToolResult(
            True,
            f"[1] test_rag_guide_zh.md score=0.91\n与 {query} 相关的 SmartKB 片段。",
            {"rows": [{"file_name": "test_rag_guide_zh.md", "score": 0.91}]},
        )


class FakeProjectServer(LocalMCPServer):
    server_name = "project"

    def register_tools(self):
        self.add_tool(ToolSpec("engineering_requirements", "fake engineering requirements"), self.requirements)
        self.add_tool(ToolSpec("project_summary", "fake project summary"), self.summary)
        self.add_tool(ToolSpec("quality_checklist", "fake quality checklist"), self.checklist)

    def requirements(self):
        return ToolResult(True, "Engineering requirements: Python, LangGraph, RAG, MCP, and storage integration.")

    def summary(self, project: str):
        return ToolResult(True, f"{project}  summary: background, architecture, tools, and metrics.")

    def checklist(self, stack: str):
        return ToolResult(True, "Checklist: MCP boundaries, agent evaluation, and deployment readiness.")


class FakeImageServer(LocalMCPServer):
    server_name = "image"

    def register_tools(self):
        self.add_tool(ToolSpec("health", "fake image health"), self.health)
        self.add_tool(ToolSpec("generate_image", "fake image generation"), self.generate_image)

    def health(self):
        return ToolResult(True, "Fake image API 正常")

    def generate_image(self, prompt: str, size: str = "1024x1024"):
        return ToolResult(
            True,
            "图片已生成: data/generated_images/fake.png",
            {"image_path": "data/generated_images/fake.png", "size": size},
        )


def build_fake_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            FakePostgresServer(),
            FakeMilvusServer(),
            FakeProjectServer(),
            FakeImageServer(),
        ]
    )


def patch_runtime(
    memory: InMemoryAgentMemory,
    long_term_memory: InMemoryLongTermMemory,
):
    import agent_team.supervisor as supervisor_module
    import agent_team.workers.base as worker_base

    fake_llm = FakeLLM()
    supervisor_module.get_llm = lambda *args, **kwargs: fake_llm
    worker_base.get_llm = lambda *args, **kwargs: fake_llm
    supervisor_module.get_memory = lambda: memory
    supervisor_module.get_long_term_memory = lambda: long_term_memory


def run_case(graph, task: str, expected_route: str, expected_tools: list[str]):
    task_id = f"offline-{expected_route}"
    state = graph.invoke(
        {
            "messages": [HumanMessage(content=task)],
            "session_id": "offline-e2e",
            "task_id": task_id,
        },
        config={"configurable": {"thread_id": task_id}},
    )
    assert state["route"] == expected_route, state
    assert state.get("tool_plan") == expected_tools, state
    assert state.get("final_answer"), state
    assert state.get("used_tools"), state
    assert state.get("latency_ms", 0) >= 0, state
    print(
        f"[OK] {expected_route:<10} tools={len(state['used_tools'])} "
        f"latency={state['latency_ms']}ms"
    )
    return state


def run_collaboration_case(graph):
    task_id = "offline-collaboration"
    state = graph.invoke(
        {
            "messages": [HumanMessage(content="先检索知识库中的 RAG 资料，再写一份技术报告")],
            "session_id": "offline-e2e",
            "task_id": task_id,
        },
        config={"configurable": {"thread_id": task_id}},
    )
    assert state["route"] == "collaboration", state
    assert state["worker_routes"] == ["researcher", "writer"], state
    assert state["worker_tool_plans"] == {
        "researcher": ["postgres.list_smartkb_documents", "milvus.search_smartkb"],
        "writer": ["project.project_summary", "project.quality_checklist"],
    }, state
    assert list(state["worker_outputs"]) == ["researcher", "writer"], state
    assert state["worker_context_stats"]["researcher"]["prompt_chars"] > 0, state
    assert (
        state["worker_context_stats"]["writer"]["prompt_chars"]
        <= state["worker_context_stats"]["writer"]["total_budget"]
    ), state
    assert len(state["used_tools"]) == 4, state
    assert state.get("trace_record", {}).get("worker_routes") == ["researcher", "writer"]
    print(
        "[OK] collaboration routes="
        f"{' -> '.join(state['worker_routes'])} tools={len(state['used_tools'])}"
    )
    return state


def run_api_stream_case(graph):
    import app as app_module
    from fastapi.testclient import TestClient

    app_module.get_graph_cached = lambda: graph
    client = TestClient(app_module.app)
    response = client.get(
        "/api/run/stream",
        params={
            "task": "先检索知识库中的 RRF 资料，再写一份摘要",
            "session_id": "offline-stream",
        },
    )
    assert response.status_code == 200, response.text
    body = response.text
    assert "event: stage" in body
    assert '"node": "supervisor"' in body
    assert '"node": "plan_tools"' in body
    assert '"node": "collaboration"' in body
    assert "event: delta" in body
    assert "event: final" in body
    invalid = client.get("/api/run/stream", params={"task": "", "session_id": "offline-stream"})
    assert invalid.status_code == 422

    run_response = client.post(
        "/api/run",
        json={
            "task": "先检索 RAG 资料，再写一份报告",
            "session_id": "offline-api",
        },
    )
    assert run_response.status_code == 200, run_response.text
    result = run_response.json()
    assert result["route"] == "collaboration"
    assert result["worker_routes"] == ["researcher", "writer"]
    checkpoint = client.get(f"/api/checkpoints/{result['task_id']}")
    assert checkpoint.status_code == 200
    assert checkpoint.json()["worker_routes"] == ["researcher", "writer"]
    resume = client.post(f"/api/tasks/{result['task_id']}/resume")
    assert resume.status_code == 200
    assert resume.json()["ok"] is True
    print("[OK] SSE streams real LangGraph node updates and final answer")


def run_offline_e2e():
    from agent_team.supervisor import build_agent_team

    memory = InMemoryAgentMemory("offline-e2e")
    long_term_memory = InMemoryLongTermMemory("offline-e2e")
    patch_runtime(memory, long_term_memory)
    graph = build_agent_team(build_fake_registry())

    cases = [
        (
            "请检索知识库中关于混合检索和 RRF 的资料",
            "researcher",
            ["postgres.list_smartkb_documents", "milvus.search_smartkb"],
        ),
        (
            "帮我设计一个 MCP server 的代码结构和测试方案",
            "engineer",
            ["project.engineering_requirements", "milvus.search_smartkb"],
        ),
        (
            "写一段 AgentFlow README 摘要",
            "writer",
            ["project.project_summary", "project.quality_checklist"],
        ),
        (
            "生成一张 AgentFlow 架构图片",
            "general",
            ["image.generate_image"],
        ),
    ]
    last_state = None
    for task, expected_route, expected_tools in cases:
        last_state = run_case(graph, task, expected_route, expected_tools)

    collaboration_state = run_collaboration_case(graph)

    stats = memory.stats()
    assert stats["total_messages"] == (len(cases) + 1) * 2
    print(f"[OK] memory backend={stats['backend']} messages={stats['total_messages']}")

    long_stats = long_term_memory.stats()
    assert long_stats["total_memories"] == len(cases) + 1
    long_context = long_term_memory.format_context("MCP server 测试方案", "offline-e2e")
    assert "MCP" in long_context
    print(
        f"[OK] long-term memory backend={long_stats['backend']} "
        f"memories={long_stats['total_memories']}"
    )
    print(f"[OK] last answer preview={last_state['final_answer'][:80]}")
    assert "researcher" in collaboration_state["worker_outputs"]
    run_api_stream_case(graph)


def run_live_health():
    from test_imports import live_checks

    live_checks()


def main():
    run_offline_e2e()
    if "--live" in sys.argv:
        run_live_health()
    print("\nAgentFlow e2e checks passed.")


if __name__ == "__main__":
    main()


