from services.ai.parser import EXPECTED_FIELDS


def calculate_case_status(case_json: dict) -> str:
    statuses = []

    for field_name in EXPECTED_FIELDS:
        field = case_json.get(field_name)
        status = field.get("status", "missing") if isinstance(field, dict) else "missing"
        statuses.append(status)

    if all(status == "complete" for status in statuses):
        return "complete"

    return "needs_review"
