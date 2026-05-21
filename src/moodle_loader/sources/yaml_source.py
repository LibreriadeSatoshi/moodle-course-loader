from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from moodle_loader.exceptions import SourceError
from moodle_loader.models import CourseSpec
from moodle_loader.sources.base import CourseSource


class YamlSource(CourseSource):
    """Reads courses from a YAML file shaped like:

        defaults:
          category_id: 2
          visible: false
        courses:
          - template_id: 10
            fullname: ...
            shortname: ...
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> list[CourseSpec]:
        if not self.path.is_file():
            raise SourceError(f"YAML not found: {self.path}")

        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise SourceError(f"Invalid YAML in {self.path}: {e}") from e

        if not isinstance(raw, dict):
            raise SourceError(f"YAML root must be a mapping, got {type(raw).__name__}")

        defaults: dict[str, Any] = raw.get("defaults", {}) or {}
        courses_raw = raw.get("courses")
        if not isinstance(courses_raw, list) or not courses_raw:
            raise SourceError("`courses` key must be a non-empty list")

        specs: list[CourseSpec] = []
        for index, entry in enumerate(courses_raw):
            if not isinstance(entry, dict):
                raise SourceError(f"courses[{index}] must be a mapping")
            merged = {**defaults, **entry}
            try:
                specs.append(CourseSpec(**merged))
            except ValidationError as e:
                raise SourceError(f"courses[{index}] is invalid: {e}") from e
        return specs
