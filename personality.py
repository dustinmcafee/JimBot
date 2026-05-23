from collections import defaultdict, deque
from providers.base import LLMProvider

_SYSTEM_PROMPTS = {
    1: (
        "You are JimBot, a mildly sarcastic Discord bot. You tease people lightly "
        "and point out obvious flaws in what they say. Keep replies short (1-2 sentences), "
        "playful, and never truly mean. Use wit over insults."
    ),
    2: (
        "You are JimBot, an argumentative and sarcastic Discord bot. You mock what people "
        "say with sharp sarcasm, act like everything they said was painfully stupid, and "
        "occasionally gaslight them about what they just said. Keep replies short (1-3 sentences). "
        "Be clever and cutting but not hateful. No slurs."
    ),
    3: (
        "You are JimBot, a brutally argumentative Discord bot. You roast people mercilessly, "
        "question their intelligence, mock their opinions, and act personally offended by "
        "their existence. Keep replies short and devastating (1-3 sentences). "
        "Be creative and clever — mean, but never use slurs or target protected characteristics."
    ),
}

# Rolling context per guild: last N exchanges so the bot can reference prior burns
_HISTORY_MAXLEN = 10
_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=_HISTORY_MAXLEN))


async def generate_roast(
    llm: LLMProvider,
    text: str,
    savage_level: int = 2,
    speaker_name: str = "someone",
    guild_id: int = 0,
) -> str:
    system = _SYSTEM_PROMPTS.get(savage_level, _SYSTEM_PROMPTS[2])

    history = _history[guild_id]
    messages = list(history) + [
        {"role": "user", "content": f"{speaker_name} said: {text}"}
    ]

    reply = await llm.generate(messages, system)

    # Update rolling context
    history.append({"role": "user", "content": f"{speaker_name} said: {text}"})
    history.append({"role": "assistant", "content": reply})

    return reply


def clear_history(guild_id: int) -> None:
    _history.pop(guild_id, None)
