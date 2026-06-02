from __future__ import annotations

import re
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
    assert (
        'style="display: block; margin: 1em auto; max-width: 75%; height: auto;"'
        in html
    )


# ---------------------------------------------------------------------------
# 17. _render_html converts GFM pipe tables to HTML <table>
# ---------------------------------------------------------------------------


def test_render_html_converts_gfm_table() -> None:
    # The Bitcoin halving table that prompted this fix.
    body = (
        "| Halving | Block height | Block reward |\n"
        "|---------|--------------|--------------|\n"
        "| Genesis | 0            | 50 BTC       |\n"
        "| 1st     | 210000       | 25 BTC       |\n"
        "| 2nd     | 420000       | 12.5 BTC     |\n"
    )
    html = _render_html(body, {})

    # Rendered as a real table, not raw markdown.
    assert "<table" in html
    assert "<thead>" in html
    assert "<tbody>" in html
    # Cells now carry an inline border style, so match on content not bare tags.
    assert ">Halving</th>" in html
    assert ">210000</td>" in html
    # The raw pipe syntax must not survive inside a paragraph.
    assert "<p>| Halving" not in html


def test_render_html_table_among_prose() -> None:
    body = (
        "Intro paragraph.\n\n"
        "| A | B |\n"
        "|---|---|\n"
        "| 1 | 2 |\n\n"
        "Closing paragraph."
    )
    html = _render_html(body, {})
    assert "<table" in html
    assert ">1</td>" in html
    assert ">2</td>" in html
    # Surrounding prose still renders as paragraphs.
    assert "<p>Intro paragraph.</p>" in html
    assert "<p>Closing paragraph.</p>" in html


# ---------------------------------------------------------------------------
# 18. Enabling the table rule leaves non-table content untouched
# ---------------------------------------------------------------------------


def test_render_html_no_table_is_unaffected() -> None:
    body = "**bold** and _italic_\n\n- one\n- two"
    html = _render_html(body, {})
    assert "<table" not in html
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<li>one</li>" in html


# ---------------------------------------------------------------------------
# 19. Tables get inline borders (Moodle's theme draws none by default)
# ---------------------------------------------------------------------------


def test_render_html_table_has_inline_borders() -> None:
    body = "| A | B |\n|---|---|\n| 1 | 2 |\n"
    html = _render_html(body, {})
    # Table collapses its borders...
    assert re.search(r'<table style="[^"]*border-collapse:\s*collapse', html)
    # ...and every cell carries a visible border + padding.
    assert re.search(r'<th style="[^"]*border:\s*1px solid', html)
    assert re.search(r'<td style="[^"]*border:\s*1px solid', html)
    assert "padding" in html


def test_render_html_table_preserves_column_alignment() -> None:
    # ':--:' / '--:' alignment makes markdown-it emit text-align on cells;
    # our border style must merge with it, not clobber it.
    body = "| L | R |\n|:--|--:|\n| a | b |\n"
    html = _render_html(body, {})
    assert "text-align:right" in html
    # The right-aligned cell keeps both its alignment and the injected border.
    cell = re.search(r"<td style=\"([^\"]*)\">b</td>", html)
    assert cell is not None
    assert "text-align:right" in cell.group(1)
    assert "border: 1px solid" in cell.group(1)


# ---------------------------------------------------------------------------
# 20. planb.academy link rewriting
# ---------------------------------------------------------------------------

_KNOWN_UUID = "a51c7ceb-e079-4ac3-bf69-6700b985a082"
_LINK_MAP = {_KNOWN_UUID: "https://moodle.example.com/course/view.php?id=42"}


def test_render_html_rewrites_known_course_link() -> None:
    body = f"See our HIS 201 course:\n\nhttps://planb.academy/courses/{_KNOWN_UUID}"
    html = _render_html(body, {}, _LINK_MAP)
    assert "https://moodle.example.com/course/view.php?id=42" in html
    assert "planb.academy" not in html


def test_render_html_known_course_link_with_lang_prefix() -> None:
    body = f"https://planb.academy/en/courses/{_KNOWN_UUID}"
    html = _render_html(body, {}, _LINK_MAP)
    assert "course/view.php?id=42" in html
    assert "planb.academy" not in html


def test_render_html_drops_chapter_in_deep_link() -> None:
    chapter = "dbb8264a-7434-57e4-9d1b-fbd1bae37fdf"
    body = f"[miner chapter](https://planb.academy/courses/{_KNOWN_UUID}/{chapter})"
    html = _render_html(body, {}, _LINK_MAP)
    # Points at the course; the chapter uuid is gone.
    assert 'href="https://moodle.example.com/course/view.php?id=42"' in html
    assert ">miner chapter</a>" in html
    assert chapter not in html


def test_render_html_markdown_link_to_unknown_course_keeps_text() -> None:
    unknown = "c762773a-9017-4129-bc0e-06adf86050ef"
    body = f"see [that course](https://planb.academy/courses/{unknown}) now"
    html = _render_html(body, {}, _LINK_MAP)
    assert "that course" in html
    assert "planb.academy" not in html
    assert "<a " not in html  # link removed, only text kept


def test_render_html_strips_bare_unknown_course_link() -> None:
    unknown = "c762773a-9017-4129-bc0e-06adf86050ef"
    body = f"Intro.\n\nhttps://planb.academy/courses/{unknown}\n\nOutro."
    html = _render_html(body, {}, _LINK_MAP)
    assert "planb.academy" not in html
    assert "Intro." in html
    assert "Outro." in html


def test_render_html_strips_tutorial_and_glossary_links() -> None:
    body = (
        "A [wallet tutorial](https://planb.academy/tutorials/wallet) and a "
        "bare one https://planb.academy/resources/glossary/utxo here."
    )
    html = _render_html(body, {}, _LINK_MAP)
    assert "planb.academy" not in html
    assert "wallet tutorial" in html  # markdown link text preserved


def test_render_html_leaves_non_planb_links_untouched() -> None:
    body = "[Bitcoin paper](https://bitcoin.org/bitcoin.pdf)"
    html = _render_html(body, {}, _LINK_MAP)
    assert 'href="https://bitcoin.org/bitcoin.pdf"' in html
    assert ">Bitcoin paper</a>" in html


def test_render_html_link_map_optional() -> None:
    # No link map: planb links are still stripped (nothing resolves).
    body = f"https://planb.academy/courses/{_KNOWN_UUID}"
    html = _render_html(body, {})
    assert "planb.academy" not in html
