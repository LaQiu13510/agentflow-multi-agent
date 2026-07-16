"""研究员 Worker。"""

from agent_team.workers.base import BaseWorker


class ResearcherWorker(BaseWorker):
    name = "researcher"
    role_prompt = "你是研究员 Agent，负责检索资料、提炼证据和指出来源。"
    default_tool_plan = (
        "postgres.list_smartkb_documents",
        "milvus.search_smartkb",
    )
    output_style = "用中文给出关键发现、证据来源和下一步建议；证据不足时明确说明。"
