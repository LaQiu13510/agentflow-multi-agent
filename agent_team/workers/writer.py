"""写作 Worker。"""

from agent_team.workers.base import BaseWorker


class WriterWorker(BaseWorker):
    name = "writer"
    role_prompt = "你是文档 Agent，负责把技术内容整理成项目说明、技术报告和发布说明。"
    default_tool_plan = (
        "project.project_summary",
        "project.quality_checklist",
    )
    output_style = "输出可直接使用的中文技术文档，结构清楚、事实准确、避免夸大。"
