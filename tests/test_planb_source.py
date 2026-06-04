"""Tests for PlanBSource – parser for Plan ₿ course directories."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from moodle_loader.exceptions import SourceError
from moodle_loader.sources.planb_source import (
    PlanBSource,
    _make_uuid,
    _slugify,
    build_course_uuid_map,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_MINIMAL_FRONTMATTER = (
    "name: Test Course\n"
    "goal: Understand Bitcoin.\n"
    "objectives:\n"
    "  - Learn A\n"
    "  - Learn B"
)

_MINIMAL_BODY = """\
# Test Intro

Welcome to the course.

+++

# Part One

<partId>11111111-1111-1111-1111-111111111111</partId>

## Chapter Alpha

<chapterId>aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa</chapterId>

Body of chapter alpha.

## Chapter Beta

<chapterId>bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb</chapterId>

Body of chapter beta.

# Part Two

<partId>22222222-2222-2222-2222-222222222222</partId>

## Chapter Gamma

<chapterId>cccccccc-cccc-cccc-cccc-cccccccccccc</chapterId>

Body of chapter gamma.
"""

# Path to the real btc101 course (sibling workspace repo)
_BTC101 = (
    Path(__file__).parent.parent.parent
    / "bitcoin-educational-content"
    / "courses"
    / "btc101"
)


def _make_course(
    tmp_path: Path,
    *,
    slug: str = "test101",
    frontmatter_yaml: str = _MINIMAL_FRONTMATTER,
    body: str = _MINIMAL_BODY,
    course_yml: str = "id: 00000000-0000-0000-0000-000000000000\n",
    asset_files: list[str] | None = None,
) -> Path:
    """Write a minimal course directory to tmp_path and return its path."""
    d = tmp_path / slug
    d.mkdir()
    (d / "course.yml").write_text(course_yml, encoding="utf-8")
    en_md = f"---\n{frontmatter_yaml}\n---\n\n{body}"
    (d / "en.md").write_text(en_md, encoding="utf-8")
    if asset_files:
        asset_dir = d / "assets" / "en"
        asset_dir.mkdir(parents=True)
        for name in asset_files:
            (asset_dir / name).write_bytes(b"\x89PNG\r\n")  # fake image bytes
    return d


# ---------------------------------------------------------------------------
# Requirement: Parsear directorio de curso Plan ₿
# ---------------------------------------------------------------------------


def test_valid_directory_returns_spec(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()

    assert spec.fullname == "Test Course"
    assert spec.default_shortname == "test101"
    assert len(spec.parts) == 2
    assert spec.parts[0].title == "Part One"
    assert spec.parts[0].part_id == "11111111-1111-1111-1111-111111111111"
    assert len(spec.parts[0].chapters) == 2
    assert spec.parts[1].title == "Part Two"
    assert len(spec.parts[1].chapters) == 1


def test_missing_course_yml_raises(tmp_path: Path) -> None:
    d = tmp_path / "bad"
    d.mkdir()
    (d / "en.md").write_text("---\nname: X\n---\n\nHi", encoding="utf-8")

    with pytest.raises(SourceError, match="course.yml"):
        PlanBSource(d).load()


def test_missing_en_md_raises(tmp_path: Path) -> None:
    d = tmp_path / "bad"
    d.mkdir()
    (d / "course.yml").write_text("id: x\n", encoding="utf-8")

    with pytest.raises(SourceError, match="en.md"):
        PlanBSource(d).load()


def test_nonexistent_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not found"):
        PlanBSource(tmp_path / "does_not_exist").load()


# ---------------------------------------------------------------------------
# Requirement: Separar contenido en Partes
# ---------------------------------------------------------------------------


def test_multiple_parts_count(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()
    assert len(spec.parts) == 2


def test_no_separator_gives_empty_parts(tmp_path: Path) -> None:
    body = "# Course Intro\n\nAll content here, no separator.\n"
    course_dir = _make_course(tmp_path, body=body)
    spec = PlanBSource(course_dir).load()

    assert spec.parts == []
    assert "All content here" in spec.intro


def test_parts_preserve_order(tmp_path: Path) -> None:
    body = """\
# Intro

+++

# Alpha

<partId>aaaaaaaa-0000-0000-0000-000000000000</partId>

## Ch1

<chapterId>00000001-0000-0000-0000-000000000000</chapterId>

body

# Beta

<partId>bbbbbbbb-0000-0000-0000-000000000000</partId>

## Ch2

<chapterId>00000002-0000-0000-0000-000000000000</chapterId>

body

# Gamma

<partId>cccccccc-0000-0000-0000-000000000000</partId>

## Ch3

<chapterId>00000003-0000-0000-0000-000000000000</chapterId>

body
"""
    course_dir = _make_course(tmp_path, body=body)
    spec = PlanBSource(course_dir).load()

    assert [p.title for p in spec.parts] == ["Alpha", "Beta", "Gamma"]


def test_part_id_extracted(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()
    assert spec.parts[0].part_id == "11111111-1111-1111-1111-111111111111"
    assert spec.parts[1].part_id == "22222222-2222-2222-2222-222222222222"


def test_missing_part_id_synthesises_uuid5(tmp_path: Path) -> None:
    body = """\
# Intro

+++

# Unnamed Part

## Ch

<chapterId>00000000-0000-0000-0000-000000000001</chapterId>

body
"""
    course_dir = _make_course(tmp_path, body=body)
    spec = PlanBSource(course_dir).load()

    part = spec.parts[0]
    assert part.title == "Unnamed Part"
    # Must be a valid UUID
    parsed = uuid.UUID(part.part_id)
    assert parsed.version == 5
    # Must be deterministic – second call gives the same value
    spec2 = PlanBSource(course_dir).load()
    assert spec2.parts[0].part_id == part.part_id


# ---------------------------------------------------------------------------
# Requirement: Separar Partes en Capítulos
# ---------------------------------------------------------------------------


def test_chapters_extracted(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    chapters = spec_chapters(tmp_path, course_dir)
    assert chapters[0].title == "Chapter Alpha"
    assert chapters[0].chapter_id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert chapters[1].title == "Chapter Beta"
    assert chapters[1].chapter_id == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def spec_chapters(tmp_path: Path, course_dir: Path):  # noqa: ARG001
    spec = PlanBSource(course_dir).load()
    return spec.parts[0].chapters


def test_chapter_body_strips_chapter_id_tag(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()
    body = spec.parts[0].chapters[0].body
    assert "<chapterId>" not in body
    assert "Body of chapter alpha" in body


def test_chapter_body_ends_before_next_h2(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()
    body = spec.parts[0].chapters[0].body
    # Body of first chapter must NOT contain "Chapter Beta" heading
    assert "## Chapter Beta" not in body
    assert "Chapter Beta" not in body


def test_missing_chapter_id_synthesises_uuid5(tmp_path: Path) -> None:
    body = """\
# Intro

+++

# Part

<partId>11111111-0000-0000-0000-000000000000</partId>

## Unnamed Chapter

No chapterId tag here.
"""
    course_dir = _make_course(tmp_path, body=body)
    spec = PlanBSource(course_dir).load()

    ch = spec.parts[0].chapters[0]
    assert ch.title == "Unnamed Chapter"
    parsed = uuid.UUID(ch.chapter_id)
    assert parsed.version == 5
    # Deterministic
    spec2 = PlanBSource(course_dir).load()
    assert spec2.parts[0].chapters[0].chapter_id == ch.chapter_id


def test_h3_does_not_split_chapter(tmp_path: Path) -> None:
    body = """\
# Intro

+++

# Part

<partId>11111111-0000-0000-0000-000000000000</partId>

## Chapter One

<chapterId>00000000-0000-0000-0000-000000000001</chapterId>

Top text.

### Subsection A

Subsection content.

### Subsection B

More subsection content.
"""
    course_dir = _make_course(tmp_path, body=body)
    spec = PlanBSource(course_dir).load()

    assert len(spec.parts[0].chapters) == 1
    body_text = spec.parts[0].chapters[0].body
    assert "### Subsection A" in body_text
    assert "### Subsection B" in body_text


# ---------------------------------------------------------------------------
# Requirement: Detectar y deduplicar assets
# ---------------------------------------------------------------------------


def test_assets_deduplicated(tmp_path: Path) -> None:
    # Same asset referenced in intro + two chapters
    body = """\
# Intro

![img](assets/en/same.webp)

+++

# Part

<partId>11111111-0000-0000-0000-000000000000</partId>

## Ch1

<chapterId>00000001-0000-0000-0000-000000000000</chapterId>

![img](assets/en/same.webp)

## Ch2

<chapterId>00000002-0000-0000-0000-000000000000</chapterId>

![img](assets/en/same.webp)
"""
    course_dir = _make_course(tmp_path, body=body, asset_files=["same.webp"])
    spec = PlanBSource(course_dir).load()

    assert len(spec.assets) == 1
    assert spec.assets[0].relative_path == "assets/en/same.webp"


def test_multiple_distinct_assets(tmp_path: Path) -> None:
    body = """\
# Intro

+++

# Part

<partId>11111111-0000-0000-0000-000000000000</partId>

## Ch1

<chapterId>00000001-0000-0000-0000-000000000000</chapterId>

![a](assets/en/a.webp)

## Ch2

<chapterId>00000002-0000-0000-0000-000000000000</chapterId>

![b](assets/en/b.webp)
"""
    course_dir = _make_course(tmp_path, body=body, asset_files=["a.webp", "b.webp"])
    spec = PlanBSource(course_dir).load()

    rel_paths = {a.relative_path for a in spec.assets}
    assert rel_paths == {"assets/en/a.webp", "assets/en/b.webp"}


def test_missing_asset_file_raises(tmp_path: Path) -> None:
    body = """\
# Intro

+++

# Part

<partId>11111111-0000-0000-0000-000000000000</partId>

## Ch

<chapterId>00000001-0000-0000-0000-000000000000</chapterId>

![img](assets/en/missing.webp)
"""
    # asset_files intentionally omitted – file doesn't exist on disk
    course_dir = _make_course(tmp_path, body=body)

    with pytest.raises(SourceError, match="missing.webp"):
        PlanBSource(course_dir).load()


def test_asset_path_traversal_raises(tmp_path: Path) -> None:
    body = """\
# Intro

+++

# Part

<partId>11111111-0000-0000-0000-000000000000</partId>

## Ch

<chapterId>00000001-0000-0000-0000-000000000000</chapterId>

![img](assets/en/../../../secret.txt)
"""
    course_dir = _make_course(tmp_path, body=body)
    # assets/en/../../../ resolves to tmp_path (parent of the course dir)
    (tmp_path / "secret.txt").write_text("oops", encoding="utf-8")

    with pytest.raises(SourceError, match="escapes"):
        PlanBSource(course_dir).load()


def test_asset_absolute_path_in_ref_not_matched(tmp_path: Path) -> None:
    """Absolute paths in image refs don't match assets/en/ pattern – no error."""
    body = "# Intro\n\n![img](/etc/passwd)\n"
    course_dir = _make_course(tmp_path, body=body)
    spec = PlanBSource(course_dir).load()
    assert spec.assets == []


# ---------------------------------------------------------------------------
# Requirement: Metadatos básicos
# ---------------------------------------------------------------------------


def test_fullname_from_frontmatter(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()
    assert spec.fullname == "Test Course"


def test_summary_includes_goal_and_objectives(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()
    assert "Understand Bitcoin." in spec.summary
    assert "- Learn A" in spec.summary
    assert "- Learn B" in spec.summary


def test_partial_frontmatter_no_goal(tmp_path: Path) -> None:
    fm = "name: Partial Course"
    course_dir = _make_course(tmp_path, frontmatter_yaml=fm)
    spec = PlanBSource(course_dir).load()
    assert spec.fullname == "Partial Course"
    assert spec.summary == ""


def test_partial_frontmatter_no_objectives(tmp_path: Path) -> None:
    fm = "name: Another Course\ngoal: Some goal"
    course_dir = _make_course(tmp_path, frontmatter_yaml=fm)
    spec = PlanBSource(course_dir).load()
    assert spec.summary == "Some goal"


def test_missing_name_raises(tmp_path: Path) -> None:
    fm = "goal: Something"
    course_dir = _make_course(tmp_path, frontmatter_yaml=fm)
    with pytest.raises(SourceError, match="name"):
        PlanBSource(course_dir).load()


def test_no_frontmatter_raises(tmp_path: Path) -> None:
    d = tmp_path / "nofm"
    d.mkdir()
    (d / "course.yml").write_text("id: x\n", encoding="utf-8")
    (d / "en.md").write_text(
        "# Just a title\n\nNo frontmatter here.\n", encoding="utf-8"
    )
    with pytest.raises(SourceError, match="name"):
        PlanBSource(d).load()


def test_default_shortname_is_directory_name(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path, slug="btc999")
    spec = PlanBSource(course_dir).load()
    assert spec.default_shortname == "btc999"


# ---------------------------------------------------------------------------
# Requirement: Idempotencia del parseo
# ---------------------------------------------------------------------------


def test_idempotent_two_calls(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path, asset_files=[])
    src = PlanBSource(course_dir)
    spec1 = src.load()
    spec2 = src.load()
    assert spec1 == spec2


def test_idempotent_new_instance(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    spec1 = PlanBSource(course_dir).load()
    spec2 = PlanBSource(course_dir).load()
    assert spec1 == spec2


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def test_slugify_basic() -> None:
    assert _slugify("Hello World") == "hello-world"
    assert _slugify("  Bitcoin 101 ") == "bitcoin-101"
    # Python's \w keeps unicode letters; & and ! are stripped
    assert _slugify("Café & Noir!") == "café-noir"


def test_make_uuid_deterministic() -> None:
    a = _make_uuid("My Title")
    b = _make_uuid("My Title")
    assert a == b
    assert uuid.UUID(a).version == 5


def test_make_uuid_different_titles() -> None:
    assert _make_uuid("Part One") != _make_uuid("Part Two")


# ---------------------------------------------------------------------------
# Integration: real btc101 course
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_parts_count() -> None:
    spec = PlanBSource(_BTC101).load()
    # 7 h1 headings after the +++ separator
    assert len(spec.parts) == 7


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_chapters_count() -> None:
    spec = PlanBSource(_BTC101).load()
    total_chapters = sum(len(p.chapters) for p in spec.parts)
    assert total_chapters == 25


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_fullname() -> None:
    spec = PlanBSource(_BTC101).load()
    assert spec.fullname == "The Bitcoin Journey"
    assert spec.default_shortname == "btc101"


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_summary_has_goal_and_objectives() -> None:
    spec = PlanBSource(_BTC101).load()
    assert "Discover Bitcoin fundamentals" in spec.summary
    assert "- Gain a general understanding" in spec.summary


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_assets_deduplicated() -> None:
    spec = PlanBSource(_BTC101).load()
    # All assets are unique
    rel_paths = [a.relative_path for a in spec.assets]
    assert len(rel_paths) == len(set(rel_paths))
    # All referenced asset files exist on disk
    for asset in spec.assets:
        assert asset.absolute_path.is_file(), f"Missing: {asset.absolute_path}"


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_all_chapter_ids_are_valid_uuids() -> None:
    spec = PlanBSource(_BTC101).load()
    for part in spec.parts:
        uuid.UUID(part.part_id)  # raises if invalid
        for ch in part.chapters:
            uuid.UUID(ch.chapter_id)


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_idempotent() -> None:
    src = PlanBSource(_BTC101)
    assert src.load() == src.load()


# ---------------------------------------------------------------------------
# Requirement: Reescritura de enlaces a planb.academy — id del curso y registro
# ---------------------------------------------------------------------------


def test_reads_planb_id_from_course_yml(tmp_path: Path) -> None:
    course_dir = _make_course(
        tmp_path, course_yml="id: a51c7ceb-e079-4ac3-bf69-6700b985a082\ntopic: bitcoin\n"
    )
    spec = PlanBSource(course_dir).load()
    assert spec.planb_id == "a51c7ceb-e079-4ac3-bf69-6700b985a082"


def test_planb_id_none_when_absent(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path, course_yml="topic: bitcoin\n")
    spec = PlanBSource(course_dir).load()
    assert spec.planb_id is None


def test_build_course_uuid_map(tmp_path: Path) -> None:
    _make_course(
        tmp_path, slug="btc101", course_yml="id: 11111111-1111-1111-1111-111111111111\n"
    )
    _make_course(
        tmp_path, slug="his201", course_yml="id: 22222222-2222-2222-2222-222222222222\n"
    )
    # A directory without a course.yml is ignored.
    (tmp_path / "not_a_course").mkdir()

    mapping = build_course_uuid_map(tmp_path)
    assert mapping == {
        "11111111-1111-1111-1111-111111111111": "btc101",
        "22222222-2222-2222-2222-222222222222": "his201",
    }


def test_build_course_uuid_map_skips_idless_courses(tmp_path: Path) -> None:
    _make_course(tmp_path, slug="btc101", course_yml="topic: bitcoin\n")
    _make_course(
        tmp_path, slug="his201", course_yml="id: 22222222-2222-2222-2222-222222222222\n"
    )
    mapping = build_course_uuid_map(tmp_path)
    assert mapping == {"22222222-2222-2222-2222-222222222222": "his201"}


# ---------------------------------------------------------------------------
# Requirement: Parsear el bloque `videos:` de `course.yml`
# ---------------------------------------------------------------------------

# A course.yml with one YouTube-only, one PeerTube-only, and one dual-provider
# video — mirrors the real btc101/btc102 shapes.
_VIDEOS_YML = """\
id: 00000000-0000-0000-0000-000000000000
videos:
  - id: 758d7d3b-84e6-4f52-bf43-967a2ce7e7ec
    youtube:
      - fr: PdiL6_1wbQY
  - id: 58e578ef-bb3c-423d-8431-0c16db8e5f29
    peertube:
      - es: aee8BTojUSaDFnEPnoUUzC
      - it: 2Gq2JdsnSJJLc5BtPGe1kJ
  - id: 9f3a7b2e-2c4d-4c1e-8b1f-3a2c1d4e5f6a
    youtube:
      - en: dQw4w9WgXcQ
    peertube:
      - en: uNFrQeXvnwtqnjbMHT7oXM
"""


def test_parses_youtube_only_video(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path, course_yml=_VIDEOS_YML)
    spec = PlanBSource(course_dir).load()

    video = spec.videos["758d7d3b-84e6-4f52-bf43-967a2ce7e7ec"]
    assert video.youtube == {"fr": "PdiL6_1wbQY"}
    assert video.peertube == {}


def test_parses_peertube_only_video(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path, course_yml=_VIDEOS_YML)
    spec = PlanBSource(course_dir).load()

    video = spec.videos["58e578ef-bb3c-423d-8431-0c16db8e5f29"]
    assert video.peertube == {
        "es": "aee8BTojUSaDFnEPnoUUzC",
        "it": "2Gq2JdsnSJJLc5BtPGe1kJ",
    }
    assert video.youtube == {}


def test_parses_dual_provider_video(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path, course_yml=_VIDEOS_YML)
    spec = PlanBSource(course_dir).load()

    video = spec.videos["9f3a7b2e-2c4d-4c1e-8b1f-3a2c1d4e5f6a"]
    assert video.youtube == {"en": "dQw4w9WgXcQ"}
    assert video.peertube == {"en": "uNFrQeXvnwtqnjbMHT7oXM"}


def test_videos_empty_when_block_absent(tmp_path: Path) -> None:
    # The default course.yml has an `id:` but no `videos:` block.
    course_dir = _make_course(tmp_path)
    spec = PlanBSource(course_dir).load()
    assert spec.videos == {}


def test_video_entry_without_id_is_skipped(tmp_path: Path) -> None:
    course_yml = (
        "id: 00000000-0000-0000-0000-000000000000\n"
        "videos:\n"
        "  - youtube:\n"
        "      - en: noIdHere\n"
        "  - id: 11111111-1111-1111-1111-111111111111\n"
        "    youtube:\n"
        "      - en: keepsThis\n"
    )
    course_dir = _make_course(tmp_path, course_yml=course_yml)
    spec = PlanBSource(course_dir).load()

    # Only the entry with an id survives.
    assert list(spec.videos) == ["11111111-1111-1111-1111-111111111111"]


def test_video_entry_without_providers_is_skipped(tmp_path: Path) -> None:
    course_yml = (
        "id: 00000000-0000-0000-0000-000000000000\n"
        "videos:\n"
        "  - id: 22222222-2222-2222-2222-222222222222\n"  # no youtube/peertube
        "  - id: 33333333-3333-3333-3333-333333333333\n"
        "    peertube:\n"
        "      - en: hasTrack\n"
    )
    course_dir = _make_course(tmp_path, course_yml=course_yml)
    spec = PlanBSource(course_dir).load()

    assert list(spec.videos) == ["33333333-3333-3333-3333-333333333333"]


def test_videos_do_not_disturb_parts_and_assets(tmp_path: Path) -> None:
    # Same content with and without a videos block → identical parts/chapters.
    plain = PlanBSource(_make_course(tmp_path, slug="plain")).load()
    with_videos = PlanBSource(
        _make_course(tmp_path, slug="withvideos", course_yml=_VIDEOS_YML)
    ).load()

    assert [p.title for p in plain.parts] == [p.title for p in with_videos.parts]
    assert [(c.title, c.body) for p in plain.parts for c in p.chapters] == [
        (c.title, c.body) for p in with_videos.parts for c in p.chapters
    ]
    assert plain.videos == {}
    assert with_videos.videos != {}


def test_btc102_real_videos_block_parsed() -> None:
    """The real btc102 course.yml carries a videos block we should parse."""
    btc102 = _BTC101.parent / "btc102"
    if not (btc102 / "course.yml").is_file():
        pytest.skip("btc102 content not available")

    spec = PlanBSource(btc102).load()
    # The directive id referenced from btc102/en.md resolves in the map.
    assert "58e578ef-bb3c-423d-8431-0c16db8e5f29" in spec.videos
    assert spec.videos["58e578ef-bb3c-423d-8431-0c16db8e5f29"].peertube
