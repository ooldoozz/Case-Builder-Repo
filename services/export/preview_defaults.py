from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

SECTION_DEFINITIONS = [
    ("01", "Project Overview", "project_overview"),
    ("02", "Problem", "problem"),
    ("03", "My Role", "my_role"),
    ("04", "Users / Context", "users_context"),
    ("05", "Research / Discovery", "research"),
    ("06", "Key UX Decisions", "key_ux_decisions"),
    ("07", "Solution", "solution"),
    ("08", "Impact", "impact"),
    ("09", "What I Learned", "what_i_learned"),
]
TOTAL_FIELDS = len(SECTION_DEFINITIONS)
SECTION_KEYS = [definition[2] for definition in SECTION_DEFINITIONS]

WIDTH_TO_SPAN = {
    "one_third": 4,
    "half": 6,
    "two_thirds": 8,
    "full": 12,
}
ALLOWED_LAYOUTS = {
    "text_only",
    "media_top",
    "media_bottom",
    "media_left",
    "media_right",
}
ALLOWED_FONT_FAMILIES = {"Inter", "Arial", "Georgia", "Times New Roman"}
ALLOWED_IMAGE_FITS = {"cover", "contain"}
ALLOWED_SECTION_STYLES = {"plain", "soft", "outline"}
ALLOWED_TEXT_ALIGNMENTS = {"left", "center"}
DEFAULT_WIDTHS = {
    "problem": "half",
    "my_role": "half",
    "solution": "two_thirds",
    "impact": "one_third",
}


def _clamp(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _clean_text(value: Any, default: str = "", limit: int = 500) -> str:
    if value is None:
        return default
    return str(value).strip()[:limit]


def image_to_dict(image: Any) -> dict[str, Any]:
    if isinstance(image, dict):
        return image
    return {
        "id": image.id,
        "section_key": image.section_key,
        "location": image.location,
        "name": image.name,
        "evidence_type": image.evidence_type,
        "caption": image.caption,
        "sort_order": image.sort_order,
    }


def build_sections(result: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for number, title, key in SECTION_DEFINITIONS:
        field = result.get(key, {})
        if not isinstance(field, dict):
            field = {"content": field, "status": "missing"}

        status = field.get("status", "missing")
        if status not in {"complete", "weak", "unclear", "missing"}:
            status = "missing"

        sections.append(
            {
                "number": number,
                "title": title,
                "key": key,
                "status": status,
                "body": field.get("content") or "",
            }
        )
    return sections


def build_default_preview(case: Any, sections: list[dict], images: Iterable[Any]) -> dict:
    image_dicts = [image_to_dict(image) for image in images]
    images_by_section = {key: [] for key in SECTION_KEYS}

    for image in image_dicts:
        key = image.get("section_key")
        if key in images_by_section:
            images_by_section[key].append(image)

    for items in images_by_section.values():
        items.sort(key=lambda item: (item.get("sort_order", 0), item.get("id", 0)))

    overview = next(
        (section["body"] for section in sections if section["key"] == "project_overview"),
        "",
    )
    cover_image_id = (
        images_by_section["project_overview"][0]["id"]
        if images_by_section["project_overview"]
        else None
    )

    preview = {
        "version": 1,
        "cover": {
            "eyebrow": "CASE STUDY 01",
            "subtitle": overview[:280],
            "role": "Product Designer",
            "platform": "Responsive Website",
            "focus": "Product Experience",
            "timeline": "",
            "cover_image_id": cover_image_id,
            "image_height": 300,
            "image_fit": "cover",
        },
        "document": {
            "font_family": "Inter",
            "base_font_size": 14,
            "content_width": 860,
            "show_status_badges": False,
            "include_missing_sections": True,
        },
        "sections": {},
    }

    for section in sections:
        key = section["key"]
        section_images = images_by_section[key]
        preview["sections"][key] = {
            "width": DEFAULT_WIDTHS.get(key, "full"),
            "min_height": 150,
            "padding": 22,
            "title_size": 22,
            "body_size": 14,
            "line_height": 1.65,
            "text_align": "left",
            "layout": "media_bottom" if section_images else "text_only",
            "image_height": 230,
            "image_fit": "cover",
            "image_columns": min(2, max(1, len(section_images))) if section_images else 1,
            "show_caption": True,
            "show_evidence_type": True,
            "style": "plain",
            "image_order": [image["id"] for image in section_images],
        }

    return preview


def normalize_preview(raw_preview: Any, default_preview: dict, images: Iterable[Any]) -> dict:
    raw = raw_preview if isinstance(raw_preview, dict) else {}
    normalized = deepcopy(default_preview)
    image_dicts = [image_to_dict(image) for image in images]
    image_ids_by_section = {key: set() for key in SECTION_KEYS}
    all_image_ids: set[int] = set()

    for image in image_dicts:
        image_id = image.get("id")
        section_key = image.get("section_key")
        if isinstance(image_id, int):
            all_image_ids.add(image_id)
            if section_key in image_ids_by_section:
                image_ids_by_section[section_key].add(image_id)

    raw_cover = raw.get("cover") if isinstance(raw.get("cover"), dict) else {}
    cover = normalized["cover"]
    for field, limit in {
        "eyebrow": 80,
        "subtitle": 800,
        "role": 120,
        "platform": 120,
        "focus": 120,
        "timeline": 120,
    }.items():
        cover[field] = _clean_text(raw_cover.get(field), cover[field], limit)

    cover_id = raw_cover.get("cover_image_id")
    cover["cover_image_id"] = cover_id if cover_id in all_image_ids else None
    cover["image_height"] = int(
        _clamp(raw_cover.get("image_height"), 160, 620, cover["image_height"])
    )
    fit = raw_cover.get("image_fit")
    cover["image_fit"] = fit if fit in ALLOWED_IMAGE_FITS else cover["image_fit"]

    raw_document = raw.get("document") if isinstance(raw.get("document"), dict) else {}
    document = normalized["document"]
    font_family = raw_document.get("font_family")
    if font_family in ALLOWED_FONT_FAMILIES:
        document["font_family"] = font_family
    document["base_font_size"] = int(
        _clamp(raw_document.get("base_font_size"), 12, 18, document["base_font_size"])
    )
    document["content_width"] = int(
        _clamp(raw_document.get("content_width"), 700, 1000, document["content_width"])
    )
    document["show_status_badges"] = bool(
        raw_document.get("show_status_badges", document["show_status_badges"])
    )
    document["include_missing_sections"] = bool(
        raw_document.get("include_missing_sections", document["include_missing_sections"])
    )

    raw_sections = raw.get("sections") if isinstance(raw.get("sections"), dict) else {}
    for key in SECTION_KEYS:
        source = raw_sections.get(key) if isinstance(raw_sections.get(key), dict) else {}
        target = normalized["sections"][key]

        width = source.get("width")
        if width in WIDTH_TO_SPAN:
            target["width"] = width

        target["min_height"] = int(_clamp(source.get("min_height"), 110, 760, target["min_height"]))
        target["padding"] = int(_clamp(source.get("padding"), 12, 48, target["padding"]))
        target["title_size"] = int(_clamp(source.get("title_size"), 17, 36, target["title_size"]))
        target["body_size"] = int(_clamp(source.get("body_size"), 11, 22, target["body_size"]))
        target["line_height"] = round(
            _clamp(source.get("line_height"), 1.25, 2.1, target["line_height"]), 2
        )
        target["image_height"] = int(
            _clamp(source.get("image_height"), 120, 620, target["image_height"])
        )
        target["image_columns"] = int(
            _clamp(source.get("image_columns"), 1, 2, target["image_columns"])
        )

        if source.get("text_align") in ALLOWED_TEXT_ALIGNMENTS:
            target["text_align"] = source["text_align"]
        if source.get("layout") in ALLOWED_LAYOUTS:
            target["layout"] = source["layout"]
        if source.get("image_fit") in ALLOWED_IMAGE_FITS:
            target["image_fit"] = source["image_fit"]
        if source.get("style") in ALLOWED_SECTION_STYLES:
            target["style"] = source["style"]

        target["show_caption"] = bool(source.get("show_caption", target["show_caption"]))
        target["show_evidence_type"] = bool(
            source.get("show_evidence_type", target["show_evidence_type"])
        )

        requested_order = source.get("image_order") if isinstance(source.get("image_order"), list) else []
        allowed_ids = image_ids_by_section[key]
        ordered_ids: list[int] = []
        for image_id in requested_order:
            if image_id in allowed_ids and image_id not in ordered_ids:
                ordered_ids.append(image_id)
        for image_id in default_preview["sections"][key]["image_order"]:
            if image_id in allowed_ids and image_id not in ordered_ids:
                ordered_ids.append(image_id)
        target["image_order"] = ordered_ids

    normalized["version"] = 1
    return normalized


def width_span(width: str) -> int:
    return WIDTH_TO_SPAN.get(width, 12)
