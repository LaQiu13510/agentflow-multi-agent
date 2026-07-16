"""Worker Agent 基类与工具计划执行器。"""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from agent_team.context import ContextPacket, get_context_manager
from agent_team.runtime_state import current_runtime_context, get_runtime_state
from agent_team.safety import get_safety_controller
from config import MAX_TOOL_CALLS_PER_WORKER
from models.llm import get_llm
from tools.mcp_base import ToolRegistry, ToolResult


@dataclass
class WorkerResult:
    content: str
    observations: list[dict]
    used_tools: list[str]
    context_stats: dict


class BaseWorker:
    name = "base"
    role_prompt = "你是一个通用 AI 助手。"
    default_tool_plan: tuple[str, ...] = ()
    output_style = "给出清晰、可执行的回答。"

    def __init__(self, tools: ToolRegistry):
        self.tools = tools
        self.llm = get_llm()
        self.context_manager = get_context_manager()
        self.safety = get_safety_controller()
        self._tool_calls = 0

    def run(
        self,
        task: str,
        memory_context: str = "",
        tool_plan: list[str] | None = None,
    ) -> WorkerResult:
        self._reset_tool_budget()
        plan = list(tool_plan or self.default_tool_plan)
        observations, used_tools = self._execute_tool_plan(task, plan)
        evidence = "\n\n".join(
            f"[{item['tool']}]\n{item['content']}"
            for item in observations
        ) or "本次任务不需要调用外部工具。"
        answer, context_stats = self._compose(
            task,
            evidence,
            memory_context,
            self._style_for_plan(plan),
        )
        return WorkerResult(answer, observations, used_tools, context_stats)

    def _style_for_plan(self, tool_plan: list[str]) -> str:
        return self.output_style

    def _execute_tool_plan(
        self,
        task: str,
        tool_plan: list[str],
    ) -> tuple[list[dict], list[str]]:
        observations = []
        used_tools = []
        for qualified_name in tool_plan[:MAX_TOOL_CALLS_PER_WORKER]:
            if "." not in qualified_name:
                observations.append({
                    "tool": qualified_name,
                    "success": False,
                    "content": "工具名称必须使用 server.tool 格式",
                })
                continue
            server_name, tool_name = qualified_name.split(".", 1)
            result = self._call_tool(
                server_name,
                tool_name,
                **self._tool_arguments(qualified_name, task),
            )
            observations.append({
                "tool": qualified_name,
                "success": result.success,
                "content": result.content,
                "metadata": result.metadata,
            })
            used_tools.append(qualified_name)
        return observations, used_tools

    def _tool_arguments(self, qualified_name: str, task: str) -> dict:
        arguments = {
            "postgres.list_smartkb_documents": {"limit": 8},
            "milvus.search_smartkb": {"query": task, "top_k": 4},
            "project.engineering_requirements": {},
            "project.project_summary": {"project": task},
            "project.quality_checklist": {
                "stack": "Python, FastAPI, LangGraph, MCP-style Tools, Agent, RAG, PostgreSQL, Milvus, Redis"
            },
            "image.generate_image": {"prompt": task, "size": "1024x1024"},
        }
        return arguments.get(qualified_name, {})

    def _compose(
        self,
        task: str,
        evidence: str,
        memory_context: str,
        style: str,
    ) -> tuple[str, dict]:
        prompt, context_stats = self.context_manager.build_worker_prompt_with_stats(
            ContextPacket(
                task=task,
                memory_context=memory_context,
                tool_observations=[{"tool": "worker.evidence", "content": evidence}],
            ),
            style=style,
        )
        prompt = self.safety.redact(prompt)
        answer = self.llm.chat(
            [
                SystemMessage(content=self.role_prompt),
                HumanMessage(content=prompt),
            ],
            temperature=0.2,
        )
        return answer, context_stats

    def _reset_tool_budget(self):
        self._tool_calls = 0

    def _call_tool(self, server_name: str, tool_name: str, **kwargs) -> ToolResult:
        self._tool_calls += 1
        if self._tool_calls > MAX_TOOL_CALLS_PER_WORKER:
            return ToolResult(
                False,
                f"工具调用超过上限: {MAX_TOOL_CALLS_PER_WORKER}",
                {"max_tool_calls": MAX_TOOL_CALLS_PER_WORKER},
            )
        try:
            session_id, task_id = current_runtime_context()
            get_runtime_state().record_tool_call(
                session_id=session_id,
                task_id=task_id,
                worker=self.name,
                tool_name=f"{server_name}.{tool_name}",
            )
        except Exception:
            pass
        result = self.tools.call(server_name, tool_name, **kwargs)
        result.content = self.safety.redact(result.content)
        return result
