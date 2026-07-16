"""工程师 Worker。"""

from agent_team.workers.base import BaseWorker


class EngineerWorker(BaseWorker):
    name = "engineer"
    role_prompt = "你是工程师 Agent，负责把需求拆成架构、模块、接口和测试。"
    default_tool_plan = (
        "project.engineering_requirements",
        "milvus.search_smartkb",
    )
    output_style = "输出工程方案：目标、模块划分、核心流程、接口、测试、风险和可观测性。"
