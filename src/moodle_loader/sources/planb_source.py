"""Parser for Plan ₿ course directories.

A Plan ₿ course directory contains:
  course.yml      – course metadata (existence required; v1 fields come from en.md)
  en.md           – full English content with YAML frontmatter
  assets/en/      – optional image assets referenced from en.md

The en.md layout:
  ---
  name: ...
  goal: ...
  objectives: [...]
  ---

  # Course intro title

  ...intro body...

  +++

  # Part One title
  <partId>UUID</partId>

  ## Chapter title
  <chapterId>UUID</chapterId>

  ...chapter body...

  # Part Two title
  ...

After the single +++ separator every top-level (h1) heading starts a new Part;
every h2 heading inside a Part starts a new Chapter.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

import frontmatter
import yaml

from moodle_loader.exceptions import SourceError
from moodle_loader.models import (
    PlanBAsset,
    PlanBChapter,
    PlanBCourseSpec,
    PlanBPart,
    PlanBVideo,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Matches Plan ₿ image references: ![alt](assets/en/filename.ext)
_ASSET_RE = re.compile(r"!\[[^\]]*\]\((assets/en/[^)]+)\)")

_PART_ID_RE = re.compile(r"<partId>([^<]+)</partId>")
_CHAPTER_ID_RE = re.compile(r"<chapterId>([^<]+)</chapterId>")

# Top-level ``id:`` line in course.yml (the Plan ₿ course UUID). Anchored at
# the start of a line so indented keys aren't matched; stops before a comment.
_COURSE_ID_RE = re.compile(r"^id:\s*([^\s#]+)", re.MULTILINE)

# h1 heading at start of line (exactly one #, not ##)
_H1_RE = re.compile(r"^# (?!#)(.+)$", re.MULTILINE)
# h2 heading at start of line (exactly two ##, not ###)
_H2_RE = re.compile(r"^## (?!#)(.+)$", re.MULTILINE)

# UUIDv5 namespace for synthesized IDs – stable across runs
_UUID_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "planb.network")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def _make_uuid(title: str) -> str:
    """Return a deterministic UUIDv5 string derived from the title slug."""
    return str(uuid.uuid5(_UUID_NS, _slugify(title)))


def _read_course_id(course_yml: Path) -> str | None:
    """Return the ``id:`` (Plan ₿ course UUID) from a course.yml, or None."""
    m = _COURSE_ID_RE.search(course_yml.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _flatten_tracks(raw: object) -> dict[str, str]:
    """Flatten a provider list ``[{lang: id}, ...]`` into ``{lang: id}``.

    Plan ₿ stores each provider as a YAML list of single-key mappings; this
    collapses them into one dict. Empty / malformed entries are ignored.
    """
    tracks: dict[str, str] = {}
    if not isinstance(raw, list):
        return tracks
    for item in raw:
        if not isinstance(item, dict):
            continue
        for lang, vid in item.items():
            if lang and vid is not None:
                tracks[str(lang)] = str(vid)
    return tracks


def _read_videos(course_yml: Path) -> dict[str, PlanBVideo]:
    """Parse the ``videos:`` block of a course.yml into ``{UUID → PlanBVideo}``.

    Each entry maps a video UUID to its ``youtube`` / ``peertube`` provider
    tracks (per language). Entries without an ``id`` or without any provider
    track are skipped with a warning; a missing/empty block yields ``{}``.
    """
    try:
        data = yaml.safe_load(course_yml.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SourceError(f"Could not parse {course_yml}: {exc}") from exc

    entries = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {}

    videos: dict[str, PlanBVideo] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        vid = entry.get("id")
        if not vid:
            log.warning("Skipping video entry without 'id' in %s", course_yml)
            continue
        youtube = _flatten_tracks(entry.get("youtube"))
        peertube = _flatten_tracks(entry.get("peertube"))
        if not youtube and not peertube:
            log.warning(
                "Skipping video %s in %s: no youtube/peertube tracks", vid, course_yml
            )
            continue
        videos[str(vid)] = PlanBVideo(
            video_id=str(vid), youtube=youtube, peertube=peertube
        )
    return videos


def build_course_uuid_map(courses_root: Path) -> dict[str, str]:
    """Map ``{planb_course_uuid → shortname}`` for every course under *courses_root*.

    Scans each ``<dir>/course.yml`` for its ``id:`` field, using the directory
    name as the Moodle shortname. Courses without an ``id:`` are skipped. This
    registry lets cross-course links (which reference courses by UUID) resolve
    to the right shortname even though the importer runs one course at a time.
    """
    mapping: dict[str, str] = {}
    for course_yml in sorted(courses_root.glob("*/course.yml")):
        course_id = _read_course_id(course_yml)
        if course_id:
            mapping[course_id] = course_yml.parent.name
    return mapping


def _build_summary(goal: str, objectives: list) -> str:
    parts: list[str] = []
    if goal:
        parts.append(goal)
    if objectives:
        parts.append("\n".join(f"- {obj}" for obj in objectives))
    return "\n\n".join(parts)


def _parse_parts(parts_blob: str) -> list[PlanBPart]:
    """Split a text blob into PlanBPart objects using h1 headings as boundaries."""
    if not parts_blob.strip():
        return []

    positions = [m.start() for m in _H1_RE.finditer(parts_blob)]
    if not positions:
        return []

    result: list[PlanBPart] = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(parts_blob)
        block = parts_blob[start:end].strip()
        result.append(_parse_part(block))
    return result


def _parse_part(block: str) -> PlanBPart:
    title_match = _H1_RE.match(block)
    title = title_match.group(1).strip() if title_match else ""

    part_id_match = _PART_ID_RE.search(block)
    part_id = part_id_match.group(1).strip() if part_id_match else _make_uuid(title)

    chapters = _split_chapters(block)
    return PlanBPart(title=title, part_id=part_id, chapters=chapters)


def _split_chapters(part_body: str) -> list[PlanBChapter]:
    """Split a part body into chapters at every h2 heading."""
    matches = list(_H2_RE.finditer(part_body))
    if not matches:
        return []

    chapters: list[PlanBChapter] = []
    for i, match in enumerate(matches):
        chapter_title = match.group(1).strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(part_body)
        raw_body = part_body[body_start:body_end].strip()

        chapter_id_match = _CHAPTER_ID_RE.search(raw_body)
        if chapter_id_match:
            chapter_id = chapter_id_match.group(1).strip()
            # Remove the tag from the body
            raw_body = (
                raw_body[: chapter_id_match.start()]
                + raw_body[chapter_id_match.end() :]
            ).strip()
        else:
            chapter_id = _make_uuid(chapter_title)

        chapters.append(
            PlanBChapter(title=chapter_title, chapter_id=chapter_id, body=raw_body)
        )
    return chapters


def _collect_assets(bodies: list[str], course_dir: Path) -> list[PlanBAsset]:
    """Scan bodies for asset references, validate them, and deduplicate."""
    seen: dict[str, PlanBAsset] = {}
    resolved_root = course_dir.resolve()

    for body in bodies:
        for m in _ASSET_RE.finditer(body):
            rel = m.group(1)  # "assets/en/filename.ext"
            if rel in seen:
                continue

            abs_path = (course_dir / rel).resolve()

            # Guard against path traversal (absolute paths, .., etc.)
            try:
                abs_path.relative_to(resolved_root)
            except ValueError:
                raise SourceError(f"Asset path escapes course directory: {rel!r}")

            if not abs_path.is_file():
                raise SourceError(f"Asset not found on disk: {abs_path}")

            seen[rel] = PlanBAsset(relative_path=rel, absolute_path=abs_path)

    return list(seen.values())


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class PlanBSource:
    """Parse a Plan ₿ course directory and return a PlanBCourseSpec.

    Usage::

        spec = PlanBSource(Path("courses/btc101")).load()
    """

    def __init__(self, course_path: Path | str) -> None:
        self.course_path = Path(course_path)

    def load(self) -> PlanBCourseSpec:
        """Parse the course directory and return a validated PlanBCourseSpec.

        Raises SourceError for any structural or filesystem problem.
        Calling load() multiple times on the same unchanged directory returns
        equal results (idempotent).
        """
        course_dir = self.course_path.resolve()

        if not course_dir.is_dir():
            raise SourceError(f"Course directory not found: {course_dir}")

        course_yml = course_dir / "course.yml"
        if not course_yml.is_file():
            raise SourceError(f"Missing required file: {course_yml}")

        en_md = course_dir / "en.md"
        if not en_md.is_file():
            raise SourceError(f"English content not found: {en_md}")

        # --- parse frontmatter + body -----------------------------------------
        post = frontmatter.loads(en_md.read_text(encoding="utf-8"))

        name = post.metadata.get("name")
        if not name:
            raise SourceError(f"Missing 'name' field in frontmatter of {en_md}")

        goal: str = post.metadata.get("goal") or ""
        objectives: list = post.metadata.get("objectives") or []
        summary = _build_summary(goal, objectives)

        # --- split intro / parts ------------------------------------------------
        raw_content: str = post.content
        blocks = raw_content.split("\n+++\n")

        intro = blocks[0].strip()

        # Join any remaining blocks (typically just one) then split by h1
        parts_blob = "\n\n".join(b.strip() for b in blocks[1:] if b.strip())
        parts = _parse_parts(parts_blob)

        # --- collect & validate assets ------------------------------------------
        all_bodies = [intro] + [ch.body for part in parts for ch in part.chapters]
        assets = _collect_assets(all_bodies, course_dir)

        return PlanBCourseSpec(
            fullname=str(name),
            summary=summary,
            default_shortname=course_dir.name,
            planb_id=_read_course_id(course_yml),
            intro=intro,
            parts=parts,
            assets=assets,
            videos=_read_videos(course_yml),
        )
