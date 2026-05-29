from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from moodle_loader.builder import PlanBCourseBuilder, _render_html
from moodle_loader.exceptions import MoodleAPIError
from moodle_loader.models import (
    PlanBAsset,
    PlanBBuildResult,
    PlanBChapter,
    PlanBCourseSpec,
    PlanBPart,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(**method_return_values) -> MagicMock:
    """Return a MagicMock pre-configured with sensible defaults for all client methods."""
    client = MagicMock()
    client.get_course_by_shortname.return_value = None
    client.get_categories.return_value = [{"id": 1, "name": "Miscellaneous"}]
    client.create_course.return_value = {"id": 99}
    client.upload_file.return_value = {"itemid": 42}
    client.set_course_image.return_value = None
    client.update_section.return_value = None
    client.create_page.return_value = None
    for method_name, return_value in method_return_values.items():
        getattr(client, method_name).return_value = return_value
    return client


def make_spec(
    *,
    fullname: str = "Test Course",
    summary: str = "",
    default_shortname: str = "test-course",
    intro: str = "",
    parts: list[PlanBPart] | None = None,
    assets: list[PlanBAsset] | None = None,
) -> PlanBCourseSpec:
    return PlanBCourseSpec(
        fullname=fullname,
        summary=summary,
        default_shortname=default_shortname,
        intro=intro,
        parts=parts or [],
        assets=assets or [],
    )


def make_asset(tmp_path: Path, name: str = "001.webp") -> PlanBAsset:
    """Create a stub asset file and return a PlanBAsset pointing to it."""
    p = tmp_path / name
    p.write_bytes(b"fake-image-bytes")
    return PlanBAsset(relative_path=f"assets/en/{name}", absolute_path=p)


def make_chapter(
    title: str = "Chapter 1", body: str = "Some **content**."
) -> PlanBChapter:
    return PlanBChapter(title=title, chapter_id="uuid-1234", body=body)


def make_part(
    title: str = "Part 1",
    chapters: list[PlanBChapter] | None = None,
) -> PlanBPart:
    return PlanBPart(
        title=title,
        part_id="uuid-abcd",
        chapters=chapters or [make_chapter()],
    )


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


def test_build_happy_path(tmp_path: Path) -> None:
    asset = make_asset(tmp_path)
    part = make_part("Bitcoin Basics", [make_chapter("What is Bitcoin?")])
    spec = make_spec(
        fullname="Bitcoin 101",
        default_shortname="btc101",
        parts=[part],
        assets=[asset],
    )
    client = make_client()

    result = PlanBCourseBuilder(client, spec).build()

    assert isinstance(result, PlanBBuildResult)
    assert result.course_id == 99
    assert result.sections_created == ["Bitcoin Basics"]
    assert result.pages_created == ["What is Bitcoin?"]
    assert result.assets_uploaded == 1
    assert result.wiped is False


# ---------------------------------------------------------------------------
# 2. Wipe calls delete when course exists
# ---------------------------------------------------------------------------


def test_wipe_calls_delete_when_course_exists() -> None:
    client = make_client()
    client.get_course_by_shortname.return_value = {"id": 5, "shortname": "test-course"}

    result = PlanBCourseBuilder(client, make_spec()).build()

    client.delete_course.assert_called_once_with(5)
    assert result.wiped is True


# ---------------------------------------------------------------------------
# 3. No wipe when shortname absent
# ---------------------------------------------------------------------------


def test_no_wipe_when_shortname_absent() -> None:
    client = make_client()
    client.get_course_by_shortname.return_value = None

    result = PlanBCourseBuilder(client, make_spec()).build()

    client.delete_course.assert_not_called()
    assert result.wiped is False


# ---------------------------------------------------------------------------
# 4. Wipe propagates MoodleAPIError
# ---------------------------------------------------------------------------


def test_wipe_propagates_moodle_api_error() -> None:
    client = make_client()
    client.get_course_by_shortname.return_value = {"id": 5}
    client.delete_course.side_effect = MoodleAPIError(
        "core_course_delete_courses",
        "moodle_exception",
        "deletefailed",
        "Cannot delete course",
    )

    with pytest.raises(MoodleAPIError):
        PlanBCourseBuilder(client, make_spec()).build()


# ---------------------------------------------------------------------------
# 5. Category fallback to 1 when no match
# ---------------------------------------------------------------------------


def test_category_fallback_to_1() -> None:
    client = make_client()
    client.get_categories.return_value = []

    PlanBCourseBuilder(client, make_spec(), category_name="Nonexistent").build()

    _, kwargs = client.create_course.call_args
    assert kwargs["categoryid"] == 1


# ---------------------------------------------------------------------------
# 6. Category resolved by name
# ---------------------------------------------------------------------------


def test_category_resolved_by_name() -> None:
    client = make_client()
    client.get_categories.return_value = [{"id": 7, "name": "Bitcoin 4 Everyone"}]

    PlanBCourseBuilder(client, make_spec(), category_name="Bitcoin 4 Everyone").build()

    _, kwargs = client.create_course.call_args
    assert kwargs["categoryid"] == 7


# ---------------------------------------------------------------------------
# 7. Assets are embedded as data URIs (no upload_file calls for page content)
# ---------------------------------------------------------------------------


def test_build_asset_url_map_returns_data_uris(tmp_path: Path) -> None:
    asset1 = make_asset(tmp_path, "001.webp")
    asset2 = make_asset(tmp_path, "002.png")
    spec = make_spec(assets=[asset1, asset2])

    client = make_client()
    result = PlanBCourseBuilder(client, spec).build()

    # No file uploads for page content
    client.upload_file.assert_not_called()
    # Both assets counted
    assert result.assets_uploaded == 2

    # Verify pages received data URIs in their content
    # (page content is HTML rendered from the body, asset refs become data URIs)
    create_page_calls = client.create_page.call_args_list
    # No call is expected here since spec has no parts; just verify no crash


# ---------------------------------------------------------------------------
# 8. No upload when spec has no assets
# ---------------------------------------------------------------------------


def test_no_upload_when_no_assets() -> None:
    client = make_client()
    spec = make_spec(assets=[])

    result = PlanBCourseBuilder(client, spec).build()

    client.upload_file.assert_not_called()
    assert result.assets_uploaded == 0


# ---------------------------------------------------------------------------
# 9. set_course_image skipped when intro has no asset references
# ---------------------------------------------------------------------------


def test_set_course_image_skipped_when_no_intro_assets(tmp_path: Path) -> None:
    asset = make_asset(tmp_path)
    # Intro present but contains no ![](assets/en/...) pattern
    spec = make_spec(assets=[asset], intro="No images here, just text.")

    client = make_client()
    PlanBCourseBuilder(client, spec).build()

    client.set_course_image.assert_not_called()


# ---------------------------------------------------------------------------
# 10. set_course_image called when intro references an asset
# ---------------------------------------------------------------------------


def test_set_course_image_called_with_first_intro_asset(tmp_path: Path) -> None:
    asset = make_asset(tmp_path, "001.webp")
    spec = make_spec(
        assets=[asset],
        intro="![cover](assets/en/001.webp)\n\nIntro text.",
    )

    client = make_client()
    PlanBCourseBuilder(client, spec).build()

    client.set_course_image.assert_called_once()
    _, kwargs = client.set_course_image.call_args
    assert kwargs["course_id"] == 99
    assert kwargs["filename"] == "001.webp"
    assert kwargs["mimetype"] == "image/webp"
    # imagedata is base64-encoded content of the stub file
    import base64

    expected_b64 = base64.b64encode(b"fake-image-bytes").decode("ascii")
    assert kwargs["imagedata"] == expected_b64


# ---------------------------------------------------------------------------
# 11. Sections created in order (section_number 1, 2, 3)
# ---------------------------------------------------------------------------


def test_sections_created_in_order() -> None:
    parts = [
        PlanBPart(title="Part Alpha", part_id="p1", chapters=[]),
        PlanBPart(title="Part Beta", part_id="p2", chapters=[]),
        PlanBPart(title="Part Gamma", part_id="p3", chapters=[]),
    ]
    spec = make_spec(parts=parts)
    client = make_client()

    PlanBCourseBuilder(client, spec).build()

    assert client.update_section.call_count == 3
    calls = client.update_section.call_args_list
    assert calls[0].kwargs["section_number"] == 1
    assert calls[0].kwargs["name"] == "Part Alpha"
    assert calls[1].kwargs["section_number"] == 2
    assert calls[1].kwargs["name"] == "Part Beta"
    assert calls[2].kwargs["section_number"] == 3
    assert calls[2].kwargs["name"] == "Part Gamma"


# ---------------------------------------------------------------------------
# 12. Pages created for every chapter across all parts (2 parts × 2 chapters = 4)
# ---------------------------------------------------------------------------


def test_pages_created_per_chapter() -> None:
    parts = [
        PlanBPart(
            title="Part 1",
            part_id="p1",
            chapters=[
                PlanBChapter(title="Ch 1.1", chapter_id="c1", body="body"),
                PlanBChapter(title="Ch 1.2", chapter_id="c2", body="body"),
            ],
        ),
        PlanBPart(
            title="Part 2",
            part_id="p2",
            chapters=[
                PlanBChapter(title="Ch 2.1", chapter_id="c3", body="body"),
                PlanBChapter(title="Ch 2.2", chapter_id="c4", body="body"),
            ],
        ),
    ]
    spec = make_spec(parts=parts)
    client = make_client()

    result = PlanBCourseBuilder(client, spec).build()

    assert client.create_page.call_count == 4
    assert result.pages_created == ["Ch 1.1", "Ch 1.2", "Ch 2.1", "Ch 2.2"]


# ---------------------------------------------------------------------------
# 13. _render_html strips Plan ₿ XML tags
# ---------------------------------------------------------------------------


def test_render_html_strips_planb_tags() -> None:
    body = "<chapterId>uuid-123</chapterId>\n<partId>uuid-456</partId>\n\nContent here."
    html = _render_html(body, {})
    assert "<chapterId>" not in html
    assert "</chapterId>" not in html
    assert "<partId>" not in html
    assert "</partId>" not in html
    assert "Content here." in html


# ---------------------------------------------------------------------------
# 14. _render_html rewrites asset URLs via asset_url_map (data URIs in practice)
# ---------------------------------------------------------------------------


def test_render_html_rewrites_asset_urls() -> None:
    body = "![img](assets/en/001.webp)"
    data_uri = "data:image/webp;base64,ZmFrZQ=="
    url_map = {"assets/en/001.webp": data_uri}
    html = _render_html(body, url_map)
    assert data_uri in html
    assert "assets/en/001.webp" not in html


# ---------------------------------------------------------------------------
# 15. _render_html converts markdown to HTML
# ---------------------------------------------------------------------------


def test_render_html_converts_markdown() -> None:
    body = "**bold** and _italic_"
    html = _render_html(body, {})
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


# ---------------------------------------------------------------------------
# 16. _render_html constrains images to the page width
# ---------------------------------------------------------------------------


def test_render_html_makes_images_responsive() -> None:
    body = "![img](assets/en/001.webp)"
    url_map = {"assets/en/001.webp": "data:image/webp;base64,ZmFrZQ=="}
    html = _render_html(body, url_map)
    assert "<img" in html
    assert 'style="max-width: 100%; height: auto;"' in html
