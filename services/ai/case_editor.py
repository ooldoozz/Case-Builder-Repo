import json
from pathlib import Path

from .client import ai_client

ALLOWED_STATUSES = {"complete", "missing", "weak"}
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class CaseEditorError(Exception):
    """Raised when the AI field-status evaluation cannot be completed."""


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8-sig").strip()


def _build_prompt(full_case: dict, field_name: str, field_content: str | None) -> str:
    return (
        _load_prompt("case_editor_user.txt")
        .replace(
            "{{FULL_CASE}}",
            json.dumps(full_case, indent=2, ensure_ascii=False),
        )
        .replace("{{FIELD_NAME}}", field_name)
        .replace("{{FIELD_CONTENT}}", repr(field_content or ""))
    )


def evaluate_field_status(
    full_case: dict,
    field_name: str,
    field_content: str | None,
) -> dict:
    if not field_name:
        raise CaseEditorError("No field name provided to evaluate.")

    try:
        raw_content = ai_client.generate(
            prompt=_build_prompt(full_case, field_name, field_content),
            system_prompt=_load_prompt("case_editor_system.txt"),
        )
    except Exception as exc:
        raise CaseEditorError("AI request failed.") from exc

    try:
        result = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise CaseEditorError("AI response was not valid JSON.") from exc

    if not isinstance(result, dict):
        raise CaseEditorError("AI response was not a JSON object.")

    status = result.get("status")
    if status not in ALLOWED_STATUSES:
        raise CaseEditorError("AI returned an invalid status.")

    reasoning = result.get("reasoning", "")
    return {
        "status": status,
        "reasoning": reasoning if isinstance(reasoning, str) else "",
    }
