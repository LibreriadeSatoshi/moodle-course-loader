from __future__ import annotations

from collections.abc import Iterable

from moodle_loader.client import MoodleClient
from moodle_loader.exceptions import MoodleAPIError
from moodle_loader.models import CourseSpec, LoadResult
from moodle_loader.sources.base import CourseSource


class CourseLoader:
    """Orchestrates course creation from a CourseSource."""

    def __init__(self, client: MoodleClient | None, *, dry_run: bool = False):
        if not dry_run and client is None:
            raise ValueError("CourseLoader requires a client when dry_run=False")
        self._client = client
        self._dry_run = dry_run

    def load(self, source: CourseSource) -> list[LoadResult]:
        specs: Iterable[CourseSpec] = source.load()
        return [self._process(spec) for spec in specs]

    def _process(self, spec: CourseSpec) -> LoadResult:
        if self._dry_run:
            return LoadResult(
                spec=spec,
                status="skipped",
                message="dry-run: API not called",
            )
        assert self._client is not None  # guaranteed by __init__
        try:
            result = self._client.duplicate_course(
                courseid=spec.template_id,
                fullname=spec.fullname,
                shortname=spec.shortname,
                categoryid=spec.category_id,
                visible=spec.visible,
            )
            course_id = result.get("id") if isinstance(result, dict) else None
            if spec.summary and course_id is not None:
                self._client.update_course(
                    course_id=course_id,
                    fullname=spec.fullname,
                    summary=spec.summary,
                )
            return LoadResult(
                spec=spec,
                status="created",
                course_id=course_id,
                message=f"course duplicated from template {spec.template_id}",
            )
        except MoodleAPIError as e:
            return LoadResult(spec=spec, status="failed", message=str(e))
