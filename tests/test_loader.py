from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from moodle_loader.exceptions import MoodleAPIError
from moodle_loader.loader import CourseLoader
from moodle_loader.models import CourseSpec
from moodle_loader.sources.base import CourseSource


class StaticSource(CourseSource):
    def __init__(self, specs: list[CourseSpec]):
        self._specs = specs

    def load(self) -> list[CourseSpec]:
        return self._specs


def make_spec(**overrides) -> CourseSpec:
    base = dict(
        template_id=10,
        fullname="Curso X",
        shortname="curso-x",
        category_id=2,
        summary="",
        visible=False,
    )
    base.update(overrides)
    return CourseSpec(**base)


def test_dry_run_does_not_call_client() -> None:
    source = StaticSource([make_spec()])
    loader = CourseLoader(client=None, dry_run=True)
    results = loader.load(source)
    assert len(results) == 1
    assert results[0].status == "skipped"


def test_creates_course_and_updates_summary() -> None:
    client = MagicMock()
    client.get_course_by_shortname.return_value = None
    client.duplicate_course.return_value = {"id": 77}
    source = StaticSource([make_spec(summary="hola")])

    results = CourseLoader(client=client).load(source)

    assert results[0].status == "created"
    assert results[0].course_id == 77
    client.duplicate_course.assert_called_once_with(
        courseid=10,
        fullname="Curso X",
        shortname="curso-x",
        categoryid=2,
        visible=False,
    )
    client.update_course.assert_called_once_with(
        course_id=77,
        fullname="Curso X",
        summary="hola",
    )


def test_no_update_call_when_summary_empty() -> None:
    client = MagicMock()
    client.get_course_by_shortname.return_value = None
    client.duplicate_course.return_value = {"id": 5}
    results = CourseLoader(client=client).load(StaticSource([make_spec()]))
    assert results[0].status == "created"
    client.update_course.assert_not_called()


def test_skips_course_that_already_exists_in_moodle() -> None:
    client = MagicMock()
    client.get_course_by_shortname.return_value = {"id": 99, "shortname": "curso-x"}
    results = CourseLoader(client=client).load(StaticSource([make_spec()]))
    assert results[0].status == "skipped"
    assert "already exists" in results[0].message
    assert "99" in results[0].message
    client.duplicate_course.assert_not_called()


def test_creates_course_when_shortname_not_in_moodle() -> None:
    client = MagicMock()
    client.get_course_by_shortname.return_value = None
    client.duplicate_course.return_value = {"id": 55}
    results = CourseLoader(client=client).load(StaticSource([make_spec()]))
    assert results[0].status == "created"
    client.duplicate_course.assert_called_once()


def test_failure_is_captured_as_result() -> None:
    client = MagicMock()
    client.get_course_by_shortname.return_value = None
    client.duplicate_course.side_effect = MoodleAPIError(
        "core_course_duplicate_course", "moodle_exception", "shortnametaken", "shortname duplicado"
    )
    results = CourseLoader(client=client).load(StaticSource([make_spec()]))
    assert results[0].status == "failed"
    assert "shortnametaken" in results[0].message


def test_load_specs_filters_to_single_course() -> None:
    client = MagicMock()
    client.get_course_by_shortname.return_value = None
    client.duplicate_course.return_value = {"id": 10}
    specs = [make_spec(shortname="a"), make_spec(shortname="b"), make_spec(shortname="c")]
    results = CourseLoader(client=client).load_specs([s for s in specs if s.shortname == "b"])
    assert len(results) == 1
    assert results[0].spec.shortname == "b"
    assert results[0].status == "created"


def test_load_specs_empty_list_returns_empty() -> None:
    loader = CourseLoader(client=None, dry_run=True)
    assert loader.load_specs([]) == []
