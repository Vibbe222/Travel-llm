import json
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import HumanMessage

from models.qwen_factory import QwenLLMFactory


def safe_json_loads(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()

    try:
        data = json.loads(raw)
    except Exception:
        return None

    return data if isinstance(data, dict) else None


@dataclass
class StageExecutor:
    """Reusable LLM executor for one workflow stage."""

    model_name: str
    prompt_template: str
    temperature: float = 0
    expects_json: bool = False
    fallback: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            self._llm = QwenLLMFactory.get_llm(
                model=self.model_name,
                temperature=self.temperature,
            )
        return self._llm

    async def run(self, state: dict[str, Any], **context: Any) -> dict[str, Any]:
        try:
            prompt = self.prompt_template.format(
                state_summary=json.dumps(_json_safe(state), ensure_ascii=False, indent=2),
                **{key: _json_safe(value) for key, value in context.items()},
            )
            response = await self._get_llm().ainvoke([HumanMessage(content=prompt)])
            content = getattr(response, "content", "") or ""

            if self.expects_json:
                parsed = safe_json_loads(content)
                if parsed is not None:
                    return parsed

            return {"content": content}
        except Exception as exc:
            if self.fallback is not None:
                fallback_data = self.fallback(state)
                fallback_data.setdefault("fallback_reason", str(exc))
                return fallback_data
            return {"content": "", "error": str(exc)}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "content"):
        return _json_safe(getattr(value, "content", ""))

    return str(value)

