from pathlib import Path

PROMPT_DIR = Path(__file__).parent.parent / "prompt"


def load_prompt(filename: str) -> str:
    return (PROMPT_DIR / filename).read_text(encoding="utf-8")


