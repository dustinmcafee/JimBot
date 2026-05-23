# Personality

JimBot's personality is driven by a system prompt sent to the LLM. Changing the prompt changes the bot's entire character.

## Built-in savage levels

`config.yaml` → `behavior.savage_level` controls the system prompt used:

| Level | Label | Character |
|-------|-------|-----------|
| 1 | Mild | Light teasing, playful, never truly mean |
| 2 | Sarcastic (default) | Sharp sarcasm, mock intelligence, gaslighting |
| 3 | Brutal | Merciless roasting, devastatingly cutting |

The `/savage 1|2|3` command changes this at runtime without a restart.

---

## Editing the prompts

System prompts are in `personality.py` in the `_SYSTEM_PROMPTS` dict:

```python
_SYSTEM_PROMPTS = {
    1: "You are JimBot, a mildly sarcastic Discord bot...",
    2: "You are JimBot, an argumentative and sarcastic Discord bot...",
    3: "You are JimBot, a brutally argumentative Discord bot...",
}
```

Edit these strings to completely change the bot's character. Some ideas:

- **British butler:** formal, passive-aggressive condescension
- **Disappointed parent:** weary sighing and constant mild disappointment
- **Sports commentator:** narrates everything as if it's a dramatic sporting event
- **Academic snob:** corrects grammar, cites sources you can't check

---

## Tips for writing effective roast prompts

- Keep replies **short** — 1-3 sentences. The bot talks in voice; nobody wants a paragraph.
- Instruct the model to be **specific** to what was said rather than generic insults.
- Include a hard ban on slurs and protected-characteristic targeting in the prompt.
- Temperature controls randomness: `1.0` is default, `1.2–1.4` is more unhinged.

---

## Rolling conversation context

`personality.py` keeps the last 10 exchanges per guild in memory. This lets the bot
reference earlier things people said ("remember when you said X? that was just as dumb").

The history is cleared when the bot leaves a voice channel (`/leave`) or when
`clear_history(guild_id)` is called. It is not persisted across restarts.

To adjust history length, change `_HISTORY_MAXLEN` in `personality.py`.
