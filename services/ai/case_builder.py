from services.ai.client import ai_client
from services.ai.parser import parse_case_response


PROMPT_TEMPLATE = """
You are an expert Product Design Case Study Assistant.

Your job is to transform an unstructured Product Design project note into a structured Product Design Case Study.

IMPORTANT RULES

1. Return ONLY a valid JSON object.
2. Never use markdown.
3. Never wrap JSON inside ```json blocks.
4. Never explain your answer.
5. Never invent information.
6. Never guess.
7. If information is missing, return null.
8. Do NOT return empty strings.
9. Keep every field concise.
10. Separate Solution from Impact.
11. Never create fake metrics.
12. If metrics are unavailable, explicitly say they are unavailable.
13. missing_info must ONLY contain field names.

Return EXACTLY this schema:

{
    "project_overview": null,
    "problem": null,
    "my_role": null,
    "users_context": null,
    "research": null,
    "key_ux_decisions": null,
    "solution": null,
    "impact": null,
    "what_i_learned": null,
    "missing_info": []
}

FIELD DEFINITIONS

project_overview:
A one or two sentence summary of the project.

problem:
The primary user or business problem.

my_role:
The designer's role and responsibilities.
Only include information explicitly mentioned.

users_context:
Target users and project context.
Do not assume demographics.

research:
Mention analytics, interviews, usability testing,
observations or any research activities that were
explicitly described.

key_ux_decisions:
The important UX decisions that were made and why.

solution:
Describe what was designed, changed or implemented.

impact:
Describe measurable results.
If only expected results are available,
explicitly mention that metrics are unavailable.

what_i_learned:
Lessons learned by the designer.

missing_info:

Return ONLY field names.

Allowed values:

[
    "project_overview",
    "problem",
    "my_role",
    "users_context",
    "research",
    "key_ux_decisions",
    "solution",
    "impact",
    "what_i_learned"
]

Example:

[
    "research",
    "impact"
]

RAW PROJECT NOTE

{{NOTE}}
"""


def build_prompt(note: str) -> str:
    """
    Build the final prompt by injecting the user's note.
    """

    return PROMPT_TEMPLATE.replace(
        "{{NOTE}}",
        note.strip(),
    )


def generate_case(note: str) -> dict:
    """
    Generate a structured Product Design Case Study.
    """

    if not note.strip():
        return {
            "error": "Project note cannot be empty."
        }

    prompt = build_prompt(note)

    try:

        raw_response = ai_client.generate(
            prompt=prompt,
        )

        result = parse_case_response(
            raw_response,
        )

        return result

    except Exception as e:

        return {
            "error": str(e)
        }