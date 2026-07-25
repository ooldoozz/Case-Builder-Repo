from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .common import image_data_uri
from .preview_defaults import width_span


def build_case_pdf(
    case: Any,
    sections: list[dict[str, Any]],
    all_images: list[dict[str, Any]],
    preview: dict[str, Any],
) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError("WeasyPrint is not installed.") from exc

    images_by_id: dict[int, dict[str, Any]] = {}
    for image in all_images:
        prepared = dict(image)
        prepared["data_uri"] = image_data_uri(case.id, image.get("location"))
        images_by_id[prepared["id"]] = prepared

    images_by_section: dict[str, list[dict[str, Any]]] = {}
    for section in sections:
        key = section["key"]
        images_by_section[key] = [
            images_by_id[image_id]
            for image_id in preview["sections"][key].get("image_order", [])
            if image_id in images_by_id and images_by_id[image_id].get("section_key") == key
        ]

    cover_image = images_by_id.get(preview["cover"].get("cover_image_id"))
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("exports/case_document.html")
    html = template.render(
        case=case,
        sections=sections,
        images_by_section=images_by_section,
        cover_image=cover_image,
        preview=preview,
        width_span=width_span,
    )
    return HTML(string=html, base_url=str(Path.cwd())).write_pdf()
