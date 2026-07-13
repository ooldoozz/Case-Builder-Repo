import json
import re


EXPECTED_SCHEMA = {
    "project_overview": None,
    "problem": None,
    "my_role": None,
    "users_context": None,
    "research": None,
    "key_ux_decisions": None,
    "solution": None,
    "impact": None,
    "what_i_learned": None,
}


def _remove_markdown(text: str) -> str:
    """
    Remove markdown code blocks.
    """

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text)

    return text.strip()


def _remove_thinking(text: str) -> str:
    """
    Remove <think>...</think> blocks used by some reasoning models.
    """

    return re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL,
    ).strip()


def _extract_json(text: str) -> str:
    """
    Extract the first JSON object from text.
    """

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found.")

    return text[start:end + 1]


def _normalize_schema(data: dict) -> dict:
    """
    Make sure every expected key exists.
    """

    result = EXPECTED_SCHEMA.copy()

    result["missing_info"] = []

    for key, value in data.items():
        result[key] = value

    if result["missing_info"] is None:
        result["missing_info"] = []

    return result


def parse_case_response(text: str) -> dict:
    """
    Parse raw LLM response into validated JSON.
    """

    cleaned = _remove_markdown(text)

    cleaned = _remove_thinking(cleaned)

    cleaned = _extract_json(cleaned)

    data = json.loads(cleaned)

    return _normalize_schema(data)