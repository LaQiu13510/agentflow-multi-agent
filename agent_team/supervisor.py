"""LangGraph Supervisor Agent。"""

import json
import re
import time
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver

from agent_team.long_term_memory import get_long_term_memory
from agent_team.memory import get_memory
from agent_team.runtime_state import runtime_context
from agent_team.skills import Skill, get_skill_registry
from agent_team.tracing import get_trace_store
from agent_team.workers.engineer import EngineerWorker
from agent_team.workers.general import GeneralWorker
from agent_team.workers.researcher import ResearcherWorker
from agent_team.workers.writer import WriterWorker
from config import DEFAULT_SESSION_ID
from models.llm import get_llm
from tools.mcp_base import ToolRegistry
from tools.registry import build_tool_registry


class AgentFlowState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    task_id: str
    task: str
    route: str
    route_reason: str
    short_term_context: str
    long_term_context: str
    memory_context: str
    worker_output: str
    worker_outputs: dict[str, str]
    worker_observations: dict[str, list[dict]]
    worker_context_stats: dict[str, dict]
    worker_routes: list[str]
    final_answer: str
    observations: list[dict]
    used_tools: list[str]
    tool_plan: list[str]
    worker_tool_plans: dict[str, list[str]]
    latency_ms: float
    skill_name: str
    skill_names: list[str]
    trace_record: dict
    _start_time: float


WORKER_ROUTES = ("researcher", "engineer", "writer", "general")
ROUTES = set(WORKER_ROUTES)
ROUTE_DEFAULT_TOOLS = {
    "researcher": ["postgres.list_smartkb_documents", "milvus.search_smartkb"],
    "engineer": ["project.engineering_requirements", "milvus.search_smartkb"],
    "writer": ["project.project_summary", "project.quality_checklist"],
    "general": ["project.engineering_requirements"],
}
_checkpointer = InMemorySaver()


class SupervisorAgent:
    """负责根据任务意图选择 Worker。"""

    def __init__(self):
        self.llm = get_llm(temperature=0.0, max_tokens=512)

    def route(self, task: str) -> tuple[str, str]:
        routes, reason, _ = self.plan(task)
        return routes[0], reason

    def plan(self, task: str) -> tuple[list[str], str, list[str]]:
        """识别单一或复合意图，并返回有序 Worker 执行计划。"""
        skills = get_skill_registry().match_all(task)
        if skills:
            routes = []
            for skill in skills:
                if skill.route in ROUTES and skill.route not in routes:
                    routes.append(skill.route)
            skill_names = [skill.name for skill in skills]
            reason_prefix = "skill" if len(skill_names) == 1 else "skills"
            return routes or ["general"], f"{reason_prefix}:{','.join(skill_names)}", skill_names

        prompt = f"""你是 Supervisor Agent，请把用户任务路由到一个 worker。

可选 worker:
- researcher: 检索资料、查知识库、总结证据
- engineer: 设计架构、实现方案、调试、测试
- writer: 项目文档、技术报告、发布说明、内容润色
- general: 其他泛化问题

只输出 JSON: {{"route": "...", "reason": "..."}}

用户任务: {task}
"""
        try:
            response = self.llm.chat(
                [
                    SystemMessage(content="你只输出合法 JSON。"),
                    HumanMessage(content=prompt),
                ],
                temperature=0.0,
                max_tokens=256,
            )
            data = self._parse_json(response)
            route = data.get("route", "general")
            if route not in ROUTES:
                route = "general"
            return [route], data.get("reason", "llm"), []
        except Exception as exc:
            return ["general"], f"fallback: {exc}", []

    def synthesize(self, task: str, worker_outputs: dict[str, str]) -> str:
        """将多个 Worker 的产出整合为面向用户的单一答案。"""
        sections = "\n\n".join(
            f"[{worker}]\n{content}"
            for worker, content in worker_outputs.items()
        )
        prompt = f"""用户任务：
{task}

各 Worker 产出：
{sections}

请按用户要求的先后顺序整合结果，保留有用证据和可执行结论，删除重复内容。
不要虚构工具没有返回的信息，也不要逐字复述 Worker 的角色说明。"""
        try:
            return self.llm.chat(
                [
                    SystemMessage(content="你是多 Agent 协作结果协调器，只输出整合后的最终答案。"),
                    HumanMessage(content=prompt),
                ],
                temperature=0.1,
            )
        except Exception:
            return sections

    def _keyword_route(self, task: str) -> str | None:
        skill = get_skill_registry().match(task)
        return skill.route if skill else None

    def _match_skill(self, task: str) -> Skill | None:
        return get_skill_registry().match(task)

    def _parse_json(self, text: str) -> dict:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        return json.loads(match.group(0))


def _latest_user_message(state: AgentFlowState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    return str(messages[-1].content)


def build_agent_team(
    tools: ToolRegistry | None = None,
):
    """构建 AgentFlow LangGraph。"""
    registry = tools or build_tool_registry()
    supervisor = SupervisorAgent()
    memory = get_memory()
    long_term_memory = get_long_term_memory()
    workers = {
        "researcher": ResearcherWorker(registry),
        "engineer": EngineerWorker(registry),
        "writer": WriterWorker(registry),
        "general": GeneralWorker(registry),
    }

    def load_memory_node(state: AgentFlowState) -> AgentFlowState:
        session_id = state.get("session_id") or DEFAULT_SESSION_ID
        state["session_id"] = session_id
        state["task"] = _latest_user_message(state)
        short_term_context = memory.recent_context(session_id)
        long_term_context = long_term_memory.format_context(
            state.get("task", ""),
            session_id=session_id,
        )
        state["short_term_context"] = short_term_context
        state["long_term_context"] = long_term_context
        state["memory_context"] = (
            f"短期记忆:\n{short_term_context}\n\n"
            f"长期记忆:\n{long_term_context}"
        )
        state["_start_time"] = time.time()
        return state

    def supervisor_node(state: AgentFlowState) -> AgentFlowState:
        routes, reason, skill_names = supervisor.plan(state.get("task", ""))
        state["worker_routes"] = routes
        state["route"] = routes[0] if len(routes) == 1 else "collaboration"
        state["route_reason"] = reason
        state["skill_names"] = skill_names
        state["skill_name"] = ",".join(skill_names)
        return state

    def worker_node(worker_name: str):
        def _run(state: AgentFlowState) -> AgentFlowState:
            with runtime_context(
                state.get("session_id", DEFAULT_SESSION_ID),
                state.get("task_id", ""),
            ):
                result = workers[worker_name].run(
                    task=state.get("task", ""),
                    memory_context=state.get("memory_context", ""),
                    tool_plan=state.get("worker_tool_plans", {}).get(
                        worker_name,
                        state.get("tool_plan", []),
                    ),
                )
            state["worker_output"] = result.content
            state["worker_outputs"] = {worker_name: result.content}
            state["worker_observations"] = {worker_name: result.observations}
            state["worker_context_stats"] = {worker_name: result.context_stats}
            state["observations"] = result.observations
            state["used_tools"] = result.used_tools
            return state

        return _run

    def plan_tools_node(state: AgentFlowState) -> AgentFlowState:
        skill_registry = get_skill_registry()
        skills = [
            skill_registry.get(name)
            for name in state.get("skill_names", [])
        ]
        available = {
            f"{item['server']}.{item['name']}"
            for item in registry.list_tools()
        }
        worker_plans: dict[str, list[str]] = {}
        for route in state.get("worker_routes", [state.get("route", "general")]):
            proposed = []
            for skill in skills:
                if skill and skill.route == route:
                    proposed.extend(skill.suggested_tools)
            if not proposed:
                proposed.extend(ROUTE_DEFAULT_TOOLS.get(route, []))
            worker_plans[route] = list(dict.fromkeys(
                name for name in proposed if name in available
            ))

        state["worker_tool_plans"] = worker_plans
        state["tool_plan"] = list(dict.fromkeys(
            name
            for route in state.get("worker_routes", [])
            for name in worker_plans.get(route, [])
        ))
        return state

    def collaboration_node(state: AgentFlowState) -> AgentFlowState:
        outputs: dict[str, str] = {}
        observations_by_worker: dict[str, list[dict]] = {}
        context_stats_by_worker: dict[str, dict] = {}
        observations: list[dict] = []
        used_tools: list[str] = []

        for worker_name in state.get("worker_routes", []):
            upstream = "\n\n".join(
                f"上游 {name} 结果：\n{content}"
                for name, content in outputs.items()
            )
            worker_task = state.get("task", "")
            if upstream:
                worker_task = f"{worker_task}\n\n请结合以下上游结果完成你负责的部分：\n{upstream}"
            with runtime_context(
                state.get("session_id", DEFAULT_SESSION_ID),
                state.get("task_id", ""),
            ):
                result = workers[worker_name].run(
                    task=worker_task,
                    memory_context=state.get("memory_context", ""),
                    tool_plan=state.get("worker_tool_plans", {}).get(worker_name, []),
                )
            outputs[worker_name] = result.content
            observations_by_worker[worker_name] = result.observations
            context_stats_by_worker[worker_name] = result.context_stats
            observations.extend(
                {**item, "worker": worker_name}
                for item in result.observations
            )
            used_tools.extend(result.used_tools)

        state["worker_outputs"] = outputs
        state["worker_observations"] = observations_by_worker
        state["worker_context_stats"] = context_stats_by_worker
        state["observations"] = observations
        state["used_tools"] = list(dict.fromkeys(used_tools))
        return state

    def coordinate_node(state: AgentFlowState) -> AgentFlowState:
        state["worker_output"] = supervisor.synthesize(
            state.get("task", ""),
            state.get("worker_outputs", {}),
        )
        return state

    def finalize_node(state: AgentFlowState) -> AgentFlowState:
        route = state.get("route", "general")
        route_detail = " -> ".join(state.get("worker_routes", [])) or route
        tools_used = ", ".join(state.get("used_tools", [])) or "无"
        state["final_answer"] = (
            f"{state.get('worker_output', '')}\n\n"
            f"---\n"
            f"Supervisor 路由: `{route}` ({route_detail}; {state.get('route_reason', '')})\n"
            f"调用工具: {tools_used}"
        )
        start_time = state.get("_start_time", time.time())
        state["latency_ms"] = round((time.time() - start_time) * 1000, 1)
        return state

    def save_memory_node(state: AgentFlowState) -> AgentFlowState:
        session_id = state.get("session_id") or DEFAULT_SESSION_ID
        task = state.get("task", "")
        answer = state.get("final_answer", "")
        route = state.get("route", "general")
        if task:
            memory.add_message(session_id, "user", task, route=route)
        if answer:
            memory.add_message(session_id, "assistant", answer, route=route)
            long_term_memory.add_memory(
                session_id=session_id,
                task=task,
                answer=answer,
                route=route,
                skill_name=state.get("skill_name", ""),
            )
        state["trace_record"] = get_trace_store().append(state)
        return state

    def route_condition(state: AgentFlowState) -> Literal[
        "researcher", "engineer", "writer", "general", "collaboration"
    ]:
        route = state.get("route", "general")
        return route if route in ROUTES | {"collaboration"} else "general"

    graph = StateGraph(AgentFlowState)
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("plan_tools", plan_tools_node)
    graph.add_node("researcher", worker_node("researcher"))
    graph.add_node("engineer", worker_node("engineer"))
    graph.add_node("writer", worker_node("writer"))
    graph.add_node("general", worker_node("general"))
    graph.add_node("collaboration", collaboration_node)
    graph.add_node("coordinate", coordinate_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("save_memory", save_memory_node)

    graph.set_entry_point("load_memory")
    graph.add_edge("load_memory", "supervisor")
    graph.add_edge("supervisor", "plan_tools")
    graph.add_conditional_edges(
        "plan_tools",
        route_condition,
        {
            "researcher": "researcher",
            "engineer": "engineer",
            "writer": "writer",
            "general": "general",
            "collaboration": "collaboration",
        },
    )
    for name in WORKER_ROUTES:
        graph.add_edge(name, "finalize")
    graph.add_edge("collaboration", "coordinate")
    graph.add_edge("coordinate", "finalize")
    graph.add_edge("finalize", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile(checkpointer=_checkpointer)


