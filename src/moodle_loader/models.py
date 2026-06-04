from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CourseSpec(BaseModel):
    """Declarative specification of a course to create."""

    model_config = ConfigDict(extra="forbid")

    template_id: int = Field(..., description="ID of the template course to duplicate")
    fullname: str
    shortname: str
    category_id: int
    summary: str = ""
    visible: bool = False


class LoadResult(BaseModel):
    """Result of processing a CourseSpec."""

    spec: CourseSpec
    status: Literal["created", "skipped", "failed"]
    course_id: int | None = None
    message: str = ""


# ---------------------------------------------------------------------------
# Plan ₿ models
# ---------------------------------------------------------------------------


class PlanBAsset(BaseModel):
    """A single image asset referenced from en.md."""

    relative_path: str  # e.g. "assets/en/001.webp"
    absolute_path: Path


class PlanBChapter(BaseModel):
    """One chapter (## heading block) inside a PlanBPart."""

    title: str
    chapter_id: str  # UUID string
    body: str  # markdown body, <chapterId> tag stripped


class PlanBPart(BaseModel):
    """One part (# heading block) inside a PlanBCourseSpec."""

    title: str
    part_id: str  # UUID string
    chapters: list[PlanBChapter] = []


class PlanBVideo(BaseModel):
    """A video referenced from course content, mapped from course.yml `videos:`.

    Each provider holds a ``{language → id_from_provider}`` map (flattened from
    the YAML list of single-key dicts). Either provider may be empty.
    """

    video_id: str  # UUID used in the `:::video id=...:::` directive
    youtube: dict[str, str] = {}  # {language: youtube video id}
    peertube: dict[str, str] = {}  # {language: peertube short id}


class PlanBCourseSpec(BaseModel):
    """Parsed representation of a Plan ₿ course directory."""

    fullname: str
    summary: str = ""
    default_shortname: str
    planb_id: str | None = None  # course.yml `id:` (Plan ₿ course UUID), if present
    intro: str = ""
    parts: list[PlanBPart] = []
    assets: list[PlanBAsset] = []
    videos: dict[str, PlanBVideo] = {}  # {video UUID → PlanBVideo}, from course.yml


class PlanBBuildResult(BaseModel):
    """Outcome of PlanBCourseBuilder.build()."""

    course_id: int
    sections_created: list[str] = []
    pages_created: list[str] = []
    assets_uploaded: int = 0
    wiped: bool = False
