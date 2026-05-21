from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from moodle_loader.models import CourseSpec


class CourseSource(ABC):
    """Source of course specifications (YAML, Google Sheets, ...)."""

    @abstractmethod
    def load(self) -> Iterable[CourseSpec]:
        """Return an iterable of CourseSpec ready to be processed."""
