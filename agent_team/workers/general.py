"""通用 Worker。"""

from agent_team.workers.base import BaseWorker


class GeneralWorker(BaseWorker):
    name = "general"
    role_prompt = "你是协调型 Agent，负责综合回答用户问题。"
    default_tool_plan = ("project.engineering_requirements",)
    output_style = "给出简洁可执行的回答；需要专业处理时说明适合的 Worker 或下一步。"

    def _style_for_plan(self, tool_plan: list[str]) -> str:
        if "image.generate_image" in tool_plan:
            return "简洁说明图片生成结果，并原样列出工具返回的本地路径或 URL。"
        return self.output_style
