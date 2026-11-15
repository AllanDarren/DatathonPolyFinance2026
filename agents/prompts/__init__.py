"""Versioned prompt files: `<name>_v<N>.txt`. The prompt_version is the file stem."""

from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


@cache
def load_prompt(name: str) -> tuple[str, str]:
    """Latest version of prompt `name` -> (text, prompt_version)."""
    files = sorted(PROMPTS_DIR.glob(f"{name}_v*.txt"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
    if not files:
        raise FileNotFoundError(f"no prompt named {name}")
    return files[-1].read_text(encoding="utf-8"), files[-1].stem


def render_prompt(text: str, **values: object) -> str:
    """Replace `{key}` placeholders only for the given keys (leaves `{{ev_id}}` untouched)."""
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text
