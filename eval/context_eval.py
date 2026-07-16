"""AgentFlow 上下文预算、保留和压缩离线评测。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_team.context import ContextManager, ContextPacket
from agent_team.safety import SafetyController


def build_cases() -> list[dict]:
    cases = []
    for index in range(12):
        task_marker = f"TASK_{index}"
        memory_marker = f"LATEST_MEMORY_{index}"
        evidence_marker = f"EVIDENCE_{index}"
        task = f"{task_marker}：完成一个多步骤 Agent 任务。" + "补充需求。" * (30 + index)
        memory = "较早的会话信息。" * (45 + index) + memory_marker
        evidence = f"{evidence_marker}：高优先级工具证据。" + "证据细节。" * (35 + index)
        cases.append({
            "task_marker": task_marker,
            "memory_marker": memory_marker,
            "evidence_marker": evidence_marker,
            "packet": ContextPacket(
                task=task,
                memory_context=memory,
                tool_observations=[
                    {"tool": "milvus.search", "content": evidence},
                    {"tool": "milvus.search.duplicate", "content": evidence},
                    {
                        "tool": "postgres.lookup",
                        "content": "补充证据 postgresql://admin:secret@127.0.0.1:5432/app " + "元数据。" * 40,
                    },
                ],
            ),
        })
    return cases


def run_eval() -> dict:
    manager = ContextManager(
        task_budget=260,
        memory_budget=220,
        evidence_budget=430,
        total_budget=1050,
        per_observation_budget=230,
    )
    safety = SafetyController()
    details = []
    for case in build_cases():
        prompt, stats = manager.build_worker_prompt_with_stats(
            case["packet"],
            style="基于证据给出结构化、可执行且不夸大的回答。",
        )
        redacted = safety.redact(prompt)
        row = {
            "task_marker": case["task_marker"],
            "budget_passed": len(prompt) <= manager.total_budget,
            "task_retained": case["task_marker"] in prompt,
            "recent_memory_retained": case["memory_marker"] in prompt,
            "priority_evidence_retained": case["evidence_marker"] in prompt,
            "duplicate_removed": prompt.count(case["evidence_marker"]) == 1,
            "secret_redacted": "admin:secret" not in redacted and "[REDACTED_SECRET]" in redacted,
            **stats,
        }
        details.append(row)

    total = len(details)
    rate = lambda key: round(sum(bool(row[key]) for row in details) / total, 4)
    return {
        "project": "agentflow-multi-agent",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "dataset": {"cases": total, "total_budget": manager.total_budget},
        "metrics": {
            "budget_compliance_rate": rate("budget_passed"),
            "task_retention_rate": rate("task_retained"),
            "recent_memory_retention_rate": rate("recent_memory_retained"),
            "priority_evidence_retention_rate": rate("priority_evidence_retained"),
            "observation_dedup_rate": rate("duplicate_removed"),
            "secret_redaction_rate": rate("secret_redacted"),
            "average_compression_ratio": round(
                sum(row["compression_ratio"] for row in details) / total,
                4,
            ),
        },
        "details": details,
    }


def main():
    print(json.dumps(run_eval(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
