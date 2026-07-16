"""Context management for AgentFlow workers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextPacket:
    """Compact context passed from Supervisor to Workers."""

    task: str
    memory_context: str = ""
    tool_observations: list[dict] = field(default_factory=list)


class ContextManager:
    """按任务、记忆、证据和总长度预算构建 Worker 上下文。"""

    def __init__(
        self,
        task_budget: int = 1200,
        memory_budget: int = 1200,
        evidence_budget: int = 2400,
        total_budget: int = 4400,
        per_observation_budget: int = 900,
    ):
        self.task_budget = task_budget
        self.memory_budget = memory_budget
        self.evidence_budget = evidence_budget
        self.total_budget = total_budget
        self.per_observation_budget = per_observation_budget

    def trim_memory(self, memory_context: str) -> str:
        """Keep the most recent memory text within budget."""
        return self._trim_from_end(memory_context or "暂无历史记忆。", self.memory_budget)

    def format_observations(self, observations: list[dict]) -> str:
        """按原始排序保留高优先级证据，并去除重复工具结果。"""
        if not observations:
            return "暂无工具观察。"
        parts = []
        seen: set[str] = set()
        for item in observations:
            tool = item.get("tool", "tool")
            content = str(item.get("content", "")).strip()
            normalized = " ".join(content.lower().split())
            if not content or normalized in seen:
                continue
            seen.add(normalized)
            content = self._trim_from_start(content, self.per_observation_budget)
            block = f"[{tool}]\n{content}"
            candidate = "\n\n".join([*parts, block])
            if len(candidate) > self.evidence_budget:
                remaining = self.evidence_budget - len("\n\n".join(parts)) - (2 if parts else 0)
                if remaining > len(f"[{tool}]\n") + 24:
                    parts.append(self._trim_from_start(block, remaining))
                break
            parts.append(block)
        return "\n\n".join(parts) or "暂无有效工具观察。"

    def build_worker_prompt(
        self,
        packet: ContextPacket,
        style: str,
    ) -> str:
        """Build the final prompt body used by worker LLM calls."""
        prompt, _ = self.build_worker_prompt_with_stats(packet, style)
        return prompt

    def build_worker_prompt_with_stats(
        self,
        packet: ContextPacket,
        style: str,
    ) -> tuple[str, dict]:
        """构建 Prompt，并返回用于评测和追踪的压缩统计。"""
        raw_task = packet.task or ""
        raw_memory = packet.memory_context or ""
        raw_evidence = "\n\n".join(
            str(item.get("content", ""))
            for item in packet.tool_observations
        )
        task = self._trim_middle(raw_task or "未提供任务。", self.task_budget)
        memory = self.trim_memory(packet.memory_context)
        evidence = self.format_observations(packet.tool_observations)
        style_text = self._trim_from_start(style or "给出清晰、可执行的回答。", 400)
        prompt = self._render_prompt(task, memory, evidence, style_text)

        if len(prompt) > self.total_budget:
            fixed = self._render_prompt(task, memory, "", style_text)
            evidence_budget = max(0, self.total_budget - len(fixed))
            evidence = self._trim_from_start(evidence, evidence_budget)
            prompt = self._render_prompt(task, memory, evidence, style_text)
        if len(prompt) > self.total_budget:
            memory_budget = max(0, self.total_budget - len(self._render_prompt(task, "", evidence, style_text)))
            memory = self._trim_from_end(memory, memory_budget)
            prompt = self._render_prompt(task, memory, evidence, style_text)

        raw_chars = len(raw_task) + len(raw_memory) + len(raw_evidence) + len(style or "")
        stats = {
            "raw_chars": raw_chars,
            "prompt_chars": len(prompt),
            "total_budget": self.total_budget,
            "task_chars": len(task),
            "memory_chars": len(memory),
            "evidence_chars": len(evidence),
            "compression_ratio": round(len(prompt) / raw_chars, 4) if raw_chars else 1.0,
        }
        return prompt, stats

    def _render_prompt(self, task: str, memory: str, evidence: str, style: str) -> str:
        return f"""用户任务:
{task}

历史记忆:
{memory}

工具观察:
{evidence}

请按以下风格输出:
{style}
"""

    def _trim_from_end(self, text: str, budget: int) -> str:
        text = text.strip()
        if budget <= 0:
            return ""
        if len(text) <= budget:
            return text
        return "..." + text[-max(0, budget - 3):]

    def _trim_from_start(self, text: str, budget: int) -> str:
        text = text.strip()
        if budget <= 0:
            return ""
        if len(text) <= budget:
            return text
        return text[:max(0, budget - 3)].rstrip() + "..."

    def _trim_middle(self, text: str, budget: int) -> str:
        text = text.strip()
        if budget <= 0:
            return ""
        if len(text) <= budget:
            return text
        head = max(1, (budget - 5) * 2 // 3)
        tail = max(1, budget - 5 - head)
        return f"{text[:head]} ... {text[-tail:]}"


_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
