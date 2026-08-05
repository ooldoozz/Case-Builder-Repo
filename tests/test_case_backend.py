import json
import unittest

from pydantic import ValidationError

from schemas import CreateCaseRequest, UpdateCaseRequest
from services.ai.case_builder import build_prompt
from services.ai.parser import EXPECTED_FIELDS, parse_case_response
from services.case_status import calculate_case_status
from services.storage.case_storage import save_case


class FakeSession:
    def __init__(self):
        self.added = None

    def add(self, value):
        self.added = value

    def commit(self):
        return None

    def refresh(self, value):
        value.id = 1

    def rollback(self):
        return None


def complete_case():
    return {
        field: {"content": f"{field} content", "status": "complete"}
        for field in EXPECTED_FIELDS
    }


class CaseBackendTests(unittest.TestCase):
    def test_case_prompt_is_loaded_from_prompt_file(self):
        prompt = build_prompt("A unique project note")
        self.assertIn("A unique project note", prompt)
        self.assertNotIn("{{NOTE}}", prompt)

    def test_case_without_project_name_uses_overview_content_as_title(self):
        request = CreateCaseRequest(note="Useful project notes")
        result = complete_case()
        result["project_overview"]["content"] = "Mobile booking redesign"

        case = save_case(FakeSession(), request, result)

        self.assertEqual(case.title, "Mobile booking redesign")

    def test_case_without_title_or_overview_gets_safe_fallback(self):
        request = CreateCaseRequest(note="Useful project notes")
        result = complete_case()
        result["project_overview"] = {"content": None, "status": "missing"}

        case = save_case(FakeSession(), request, result)

        self.assertEqual(case.title, "Untitled case study")

    def test_partial_case_cannot_be_marked_complete(self):
        partial = {"problem": {"content": "A problem", "status": "complete"}}
        self.assertEqual(calculate_case_status(partial), "needs_review")

    def test_all_required_fields_can_be_marked_complete(self):
        self.assertEqual(calculate_case_status(complete_case()), "complete")

    def test_update_request_rejects_unknown_field(self):
        with self.assertRaises(ValidationError):
            UpdateCaseRequest(field="unknown", content="text")

    def test_update_request_limits_content_length(self):
        with self.assertRaises(ValidationError):
            UpdateCaseRequest(field="problem", content="x" * 20_001)

    def test_parser_rejects_non_object_json(self):
        with self.assertRaises(ValueError):
            parse_case_response("[1, 2, 3]")

    def test_parser_normalizes_non_string_content_to_missing(self):
        raw = json.dumps(
            {
                "problem": {
                    "content": {"unexpected": "object"},
                    "status": "complete",
                }
            }
        )

        result = parse_case_response(raw)

        self.assertEqual(
            result["problem"],
            {"content": None, "status": "missing"},
        )


if __name__ == "__main__":
    unittest.main()
