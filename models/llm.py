"""
DeepSeek LLM 封装
================
保持与 SmartKB 相同的调用风格，方便两个项目复用统一模型接口。
"""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class DeepSeekLLM:
    """DeepSeek Chat 的薄封装。"""

    def __init__(self, temperature: float = 0.2, max_tokens: int = 2048):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm = ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def chat(
        self,
        messages: list[BaseMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        if temperature is not None or max_tokens is not None:
            llm = ChatOpenAI(
                model=DEEPSEEK_MODEL,
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                temperature=self.temperature if temperature is None else temperature,
                max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            )
            return llm.invoke(messages).content
        return self._llm.invoke(messages).content

    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return self.chat(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ],
            **kwargs,
        )

    def test_connection(self) -> tuple[bool, str]:
        try:
            response = self.chat([HumanMessage(content="请回复 ok")], max_tokens=16)
            return bool(response), f"模型={DEEPSEEK_MODEL}, 响应={response[:20]}"
        except Exception as exc:
            return False, str(exc)[:200]


_llm_cache: dict[tuple[float, int], DeepSeekLLM] = {}


def get_llm(
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> DeepSeekLLM:
    key = (temperature, max_tokens)
    if key not in _llm_cache:
        _llm_cache[key] = DeepSeekLLM(
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return _llm_cache[key]

