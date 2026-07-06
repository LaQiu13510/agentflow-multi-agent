"""Worker Agent 基类。"""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from models.llm import get_llm
from tools.mcp_base import ToolRegistry


@dataclass
class WorkerResult:
    content: str
    observations: list[dict]
    used_tools: list[str]


class BaseWorker:
    name = "base"
    role_prompt = "你是一个通用 AI 助手。"

    def __init__(self, tools: ToolRegistry):
        self.tools = tools
        self.llm = get_llm()

    def run(self, task: str, memory_context: str = "") -> WorkerResult:
        raise NotImplementedError

    def _compose(
        self,
        task: str,
        evidence: str,
        memory_context: str,
        style: str,
    ) -> str:
        prompt = f"""用户任务:
{task}

历史记忆:
{memory_context}

工具观察:
{evidence}

请按以下风格输出:
{style}
"""
        return self.llm.chat(
            [
                SystemMessage(content=self.role_prompt),
                HumanMessage(content=prompt),
            ],
            temperature=0.2,
        )

