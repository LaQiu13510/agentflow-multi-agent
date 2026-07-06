"""通用 Worker。"""

from agent_team.workers.base import BaseWorker, WorkerResult


class GeneralWorker(BaseWorker):
    name = "general"
    role_prompt = "你是协调型 Agent，负责综合回答用户问题。"

    def run(self, task: str, memory_context: str = "") -> WorkerResult:
        observations = []
        used_tools = []

        req = self.tools.call("project", "engineering_requirements")
        observations.append({"tool": "project.engineering_requirements", "content": req.content})
        used_tools.append("project.engineering_requirements")

        answer = self._compose(
            task,
            req.content,
            memory_context,
            "给出简洁可执行的回答。必要时说明可以继续交给 researcher、engineer 或 writer。",
        )
        return WorkerResult(answer, observations, used_tools)



