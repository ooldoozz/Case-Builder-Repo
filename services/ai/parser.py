import json
import re


EXPECTED_FIELDS = [
    "project_overview",
    "problem",
    "my_role",
    "users_context",
    "research",
    "key_ux_decisions",
    "solution",
    "impact",
    "what_i_learned",
]

VALID_STATUSES = {
    "complete",
    "weak",
    "missing",
    "unclear",
}


def _default_schema() -> dict:
    """
    Create the normalized schema.
    """

    return {
        field: {
            "content": None,
            "status": "missing",
        }
        for field in EXPECTED_FIELDS
    }


def _remove_markdown(text: str) -> str:
    """
    Remove markdown code fences.
    """

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text)

    return text.strip()


def _remove_thinking(text: str) -> str:
    """
    Remove reasoning blocks produced by some models.
    """

    return re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL,
    ).strip()


def _extract_json(text: str) -> str:
    """
    Extract the first JSON object.
    """

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found.")

    return text[start:end + 1]


def _normalize_field(value) -> dict:
    """
    Normalize a single field.
    """

    if value is None:
        return {
            "content": None,
            "status": "missing",
        }

    # Old schema compatibility
    if isinstance(value, str):
        return {
            "content": value.strip() or None,
            "status": "complete" if value.strip() else "missing",
        }

    if not isinstance(value, dict):
        return {
            "content": None,
            "status": "missing",
        }

    content = value.get("content")
    status = str(value.get("status", "missing")).lower()

    if isinstance(content, str):
        content = content.strip() or None
    elif content is not None:
        content = None

    if content is None:
        status = "missing"

    if content == "":
        content = None

    if status not in VALID_STATUSES:
        status = "missing"

    return {
        "content": content,
        "status": status,
    }


def _normalize_schema(data: dict) -> dict:
    """
    Normalize the whole AI response.
    """

    result = _default_schema()

    for field in EXPECTED_FIELDS:
        result[field] = _normalize_field(
            data.get(field)
        )

    return result


def parse_case_response(text: str) -> dict:
    """
    Parse raw LLM response into validated schema.
    """

    cleaned = _remove_markdown(text)

    cleaned = _remove_thinking(cleaned)

    cleaned = _extract_json(cleaned)

    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("AI response must contain a JSON object.")

    return _normalize_schema(data)
