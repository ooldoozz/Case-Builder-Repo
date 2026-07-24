import json

from .client import ai_client

ALLOWED_STATUSES = {"complete", "missing", "weak"}

SYSTEM_PROMPT = """
You are a Senior Product Design Hiring Manager and UX Portfolio Reviewer.

Your job is to review ONE edited field of a Product Design case study.

The complete case study is provided only for context.

Evaluate ONLY the edited field.

Do not rewrite the content.

Do not invent missing information.

Do not evaluate any other field.

Use the following statuses only:

complete
weak
missing

Definitions

missing

The field is empty, null, or contains no meaningful information.

weak

The content is understandable but is not yet portfolio-ready.

Use weak when:

- important details are missing
- evidence is missing
- reasoning is missing
- ownership is too shallow
- explanations are too generic
- the field would likely trigger follow-up questions from a hiring manager

complete

Use complete only when:

- the information is explicit
- the scope is clear
- the content stands on its own
- the explanation is sufficiently detailed
- the content feels portfolio-ready
- a hiring manager would not immediately ask for clarification

Return only JSON.

{
    "status":"complete|weak|missing",
    "reasoning":"One concise sentence explaining the decision."
}

The reasoning should explain what is missing rather than simply repeating the content.

Never output markdown.

Never output anything outside the JSON.
"""


class CaseEditorError(Exception):
    """Raised when the AI field-status evaluation cannot be completed."""


def _build_prompt(full_case: dict, field_name: str, field_content: str) -> str:
    return (
        "FULL CASE STUDY (for context):\n"
        f"{json.dumps(full_case, indent=2, ensure_ascii=False)}\n\n"
        f"FIELD CHANGED: {field_name}\n"
        f"NEW CONTENT:\n{field_content!r}\n\n"
        "Evaluate only this field and return the JSON object described in your instructions."
    )


def evaluate_field_status(full_case: dict, field_name: str, field_content: str) -> dict:
    """
    Ask the AI to evaluate a single updated field against the rest of the case
    and return {"status": ..., "reasoning": ...}.

    Raises CaseEditorError on any failure (bad request, network/API error,
    invalid JSON, invalid status) so the caller never has to handle a raw
    exception from the AI client.
    """
    if not field_name:
        raise CaseEditorError("No field name provided to evaluate.")

    prompt = _build_prompt(full_case, field_name, field_content or "")

    try:
        raw_content = ai_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )
    except Exception as exc:
        raise CaseEditorError(f"AI request failed: {exc}") from exc

    try:
        result = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise CaseEditorError("AI response was not valid JSON.") from exc

    status = result.get("status")
    if status not in ALLOWED_STATUSES:
        raise CaseEditorError(f"AI returned an invalid status: {status!r}")

    return {
        "status": status,
        "reasoning": result.get("reasoning", ""),
    }