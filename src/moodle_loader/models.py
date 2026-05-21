from __future__ import annotations

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
