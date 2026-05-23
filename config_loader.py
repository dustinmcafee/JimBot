import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# .env is the venv folder name — load from secrets.env instead
_SECRETS_FILE = Path(__file__).parent / "secrets.env"
load_dotenv(_SECRETS_FILE)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)

    _resolve_api_keys(cfg)
    _validate(cfg)
    return cfg


def _resolve_api_keys(cfg: dict) -> None:
    """Replace api_key_env pointers with the actual env var values."""
    for section in ("llm", "stt", "tts"):
        block = cfg.get(section, {})
        env_var = block.get("api_key_env")
        if env_var:
            block["api_key"] = os.environ.get(env_var, "")
        else:
            block["api_key"] = ""

    cfg["discord_token"] = os.environ.get("DISCORD_TOKEN", "")


def _validate(cfg: dict) -> None:
    if not cfg.get("discord_token"):
        raise ValueError("DISCORD_TOKEN is not set. Add it to your secrets.env file.")

    llm_provider = cfg["llm"]["provider"]
    if llm_provider == "claude" and not cfg["llm"].get("api_key"):
        raise ValueError("LLM provider is 'claude' but ANTHROPIC_API_KEY is not set.")

    # openai_compat covers LM Studio / Ollama which need no key — only enforce
    # when the user has actually pointed api_key_env at something.
    if llm_provider in ("openai", "openai_compat"):
        api_key_env = cfg["llm"].get("api_key_env")
        if api_key_env and not cfg["llm"].get("api_key"):
            raise ValueError(
                f"LLM provider is '{llm_provider}' but no API key env var is set "
                "(set api_key_env to OPENAI_API_KEY or OPENAI_COMPAT_API_KEY)."
            )
