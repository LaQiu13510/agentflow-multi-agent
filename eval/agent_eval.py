"""AgentFlow 离线 Skill 路由与多意图规划评测。"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_team.skills import get_skill_registry


SINGLE_INTENT_CASES = [
    {"task": "请检索知识库中关于 RAG 的资料", "skill": "knowledge_research", "route": "researcher"},
    {"task": "搜索 Milvus 里的混合检索证据", "skill": "knowledge_research", "route": "researcher"},
    {"task": "查找 PostgreSQL 中的文档元数据", "skill": "knowledge_research", "route": "researcher"},
    {"task": "向量库里有哪些 RRF 内容", "skill": "knowledge_research", "route": "researcher"},
    {"task": "总结这份 RAG 资料", "skill": "knowledge_research", "route": "researcher"},
    {"task": "知识库中有没有缓存策略", "skill": "knowledge_research", "route": "researcher"},
    {"task": "search milvus for rag evidence", "skill": "knowledge_research", "route": "researcher"},
    {"task": "公司内部关于缓存失效机制有哪些材料", "skill": "knowledge_research", "route": "researcher"},
    {"task": "设计一个多 Agent 协作架构", "skill": "engineering_design", "route": "engineer"},
    {"task": "实现 FastAPI 工具调用接口", "skill": "engineering_design", "route": "engineer"},
    {"task": "排查任务恢复时出现的 bug", "skill": "engineering_design", "route": "engineer"},
    {"task": "编写一套 Checkpoint 测试方案", "skill": "engineering_design", "route": "engineer"},
    {"task": "用 Docker 完成容器化部署", "skill": "engineering_design", "route": "engineer"},
    {"task": "重构 MCP 工具调用层", "skill": "engineering_design", "route": "engineer"},
    {"task": "设计 MCP server 的接口边界", "skill": "engineering_design", "route": "engineer"},
    {"task": "让这个服务能一键跑起来，并保证出错后可恢复", "skill": "engineering_design", "route": "engineer"},
    {"task": "撰写 AgentFlow 技术文档", "skill": "technical_writing", "route": "writer"},
    {"task": "写一份项目阶段报告", "skill": "technical_writing", "route": "writer"},
    {"task": "生成 README 摘要", "skill": "technical_writing", "route": "writer"},
    {"task": "润色这段功能说明", "skill": "technical_writing", "route": "writer"},
    {"task": "整理一份 release notes", "skill": "technical_writing", "route": "writer"},
    {"task": "输出本周项目复盘", "skill": "technical_writing", "route": "writer"},
    {"task": "编写系统运维手册", "skill": "technical_writing", "route": "writer"},
    {"task": "把这段内容改成新人容易阅读的版本", "skill": "technical_writing", "route": "writer"},
    {"task": "生成一张多 Agent 协作图片", "skill": "image_generation", "route": "general"},
    {"task": "画图展示任务执行链路", "skill": "image_generation", "route": "general"},
    {"task": "生成系统架构图", "skill": "image_generation", "route": "general"},
    {"task": "绘制业务流程图", "skill": "image_generation", "route": "general"},
    {"task": "输出一张组件示意图", "skill": "image_generation", "route": "general"},
    {"task": "生成服务拓扑图", "skill": "image_generation", "route": "general"},
    {"task": "generate image for the agent workflow", "skill": "image_generation", "route": "general"},
    {"task": "把系统结构可视化一下", "skill": "image_generation", "route": "general"},
]


MULTI_INTENT_CASES = [
    {"task": "先检索 RAG 资料，再写一份技术报告", "skills": ["knowledge_research", "technical_writing"]},
    {"task": "先设计接口，再写 README", "skills": ["engineering_design", "technical_writing"]},
    {"task": "检索知识库资料并设计部署方案", "skills": ["knowledge_research", "engineering_design"]},
    {"task": "查知识库后生成一张架构图", "skills": ["image_generation"]},
    {"task": "生成架构图并附带文字说明", "skills": ["image_generation"]},
    {"task": "分析 Milvus 资料，设计接口，最后撰写文档", "skills": ["knowledge_research", "engineering_design", "technical_writing"]},
    {"task": "先写项目报告，再检索 RAG 资料补充证据", "skills": ["technical_writing", "knowledge_research"]},
    {"task": "先调试检索接口，再搜索知识库验证结果", "skills": ["engineering_design", "knowledge_research"]},
    {"task": "先梳理现有证据，再整理成项目复盘", "skills": ["knowledge_research", "technical_writing"]},
    {"task": "先看看已有信息，再给出可落地方案", "skills": ["knowledge_research", "engineering_design"]},
]


def macro_f1(rows: list[dict]) -> tuple[float, dict[str, dict[str, float]]]:
    labels = sorted({row["expected_route"] for row in rows})
    per_route = {}
    for label in labels:
        true_positive = sum(
            row["expected_route"] == label and row["actual_route"] == label
            for row in rows
        )
        false_positive = sum(
            row["expected_route"] != label and row["actual_route"] == label
            for row in rows
        )
        false_negative = sum(
            row["expected_route"] == label and row["actual_route"] != label
            for row in rows
        )
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        per_route[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return round(sum(item["f1"] for item in per_route.values()) / len(per_route), 4), per_route


def recommended_tools(skills) -> list[str]:
    return list(dict.fromkeys(
        tool
        for skill in skills
        for tool in skill.suggested_tools
    ))


def run_eval() -> dict:
    registry = get_skill_registry()
    single_details = []
    confusion = defaultdict(lambda: defaultdict(int))
    for case in SINGLE_INTENT_CASES:
        skill = registry.match(case["task"])
        actual_skill = skill.name if skill else "unmatched"
        actual_route = skill.route if skill else "unmatched"
        passed = actual_skill == case["skill"] and actual_route == case["route"]
        row = {
            "task": case["task"],
            "expected_skill": case["skill"],
            "actual_skill": actual_skill,
            "expected_route": case["route"],
            "actual_route": actual_route,
            "passed": passed,
        }
        single_details.append(row)
        confusion[case["route"]][actual_route] += 1

    multi_details = []
    for case in MULTI_INTENT_CASES:
        skills = registry.match_all(case["task"])
        actual = [skill.name for skill in skills]
        expected_skill_objects = [registry.get(name) for name in case["skills"]]
        expected_skill_objects = [skill for skill in expected_skill_objects if skill]
        expected_tools = recommended_tools(expected_skill_objects)
        actual_tools = recommended_tools(skills)
        multi_details.append({
            "task": case["task"],
            "expected_skills": case["skills"],
            "actual_skills": actual,
            "expected_tools": expected_tools,
            "actual_tools": actual_tools,
            "skill_plan_passed": actual == case["skills"],
            "tool_plan_passed": actual_tools == expected_tools,
        })

    single_passed = sum(row["passed"] for row in single_details)
    multi_passed = sum(row["skill_plan_passed"] for row in multi_details)
    tool_passed = sum(row["tool_plan_passed"] for row in multi_details)
    f1, per_route = macro_f1(single_details)
    skills = registry.list_skills()
    schema_ready = sum(
        bool(skill.get("input_schema") and skill.get("output_format") and skill.get("worker_detail"))
        for skill in skills
    )

    return {
        "project": "agentflow-multi-agent",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "dataset": {
            "single_intent_cases": len(single_details),
            "multi_intent_cases": len(multi_details),
            "total_cases": len(single_details) + len(multi_details),
        },
        "metrics": {
            "single_intent_accuracy": round(single_passed / len(single_details), 4),
            "single_intent_macro_f1": f1,
            "multi_intent_exact_match": round(multi_passed / len(multi_details), 4),
            "multi_intent_tool_plan_exact_match": round(tool_passed / len(multi_details), 4),
            "skill_schema_coverage": round(schema_ready / len(skills), 4),
        },
        "per_route": per_route,
        "confusion_matrix": {
            expected: dict(predicted)
            for expected, predicted in confusion.items()
        },
        "single_intent_details": single_details,
        "multi_intent_details": multi_details,
    }


def main():
    print(json.dumps(run_eval(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
