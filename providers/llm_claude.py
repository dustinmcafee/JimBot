import anthropic
from providers.base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self, cfg: dict):
        self._client = anthropic.AsyncAnthropic(api_key=cfg["api_key"])
        self._model = cfg.get("model", "claude-haiku-4-5")
        self._temperature = cfg.get("temperature", 1.0)
        self._max_tokens = cfg.get("max_tokens", 300)

    async def generate(self, messages: list[dict], system: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=system,
            messages=messages,
        )
        return response.content[0].text.strip()
