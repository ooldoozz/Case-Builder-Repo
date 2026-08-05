import logging
from pathlib import Path

from services.ai.client import ai_client
from services.ai.parser import parse_case_response

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "case_builder.txt"


def build_prompt(note: str) -> str:
    """Load the case-builder prompt and inject the untrusted project note."""
    template = PROMPT_PATH.read_text(encoding="utf-8-sig")
    return template.replace("{{NOTE}}", note.strip())


def generate_case(note: str) -> dict:
    """Generate a normalized Product Design case study."""
    if not note.strip():
        return {"error": "Project note cannot be empty."}

    try:
        raw_response = ai_client.generate(prompt=build_prompt(note))
        return parse_case_response(raw_response)
    except Exception:
        logger.exception("Case generation failed")
        return {"error": "Case generation failed. Please try again."}
