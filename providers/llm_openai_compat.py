from openai import AsyncOpenAI
from providers.base import LLMProvider


class OpenAICompatProvider(LLMProvider):
    """Works with OpenAI, OpenRouter, Groq, Together, Ollama/LM Studio — anything
    that speaks the OpenAI chat completions format. Set base_url in config to
    redirect to a different endpoint."""

    def __init__(self, cfg: dict):
        self._client = AsyncOpenAI(
            api_key=cfg.get("api_key") or "dummy",
            base_url=cfg.get("base_url"),  # None = default OpenAI endpoint
        )
        self._model = cfg.get("model", "gpt-4o-mini")
        self._temperature = cfg.get("temperature", 1.0)
        self._max_tokens = cfg.get("max_tokens", 300)

    async def generate(self, messages: list[dict], system: str) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return response.choices[0].message.content.strip()
