from __future__ import annotations

from pathlib import Path

import pytest

from moodle_loader.exceptions import SourceError
from moodle_loader.sources import YamlSource


def write_yaml(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "courses.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_merges_defaults(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path,
        """
defaults:
  category_id: 2
  visible: false
courses:
  - template_id: 10
    fullname: Curso A
    shortname: curso-a
  - template_id: 18
    fullname: Curso B
    shortname: curso-b
    category_id: 5
""",
    )
    specs = YamlSource(path).load()
    assert len(specs) == 2
    assert specs[0].category_id == 2
    assert specs[0].visible is False
    assert specs[1].category_id == 5  # override


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not found"):
        YamlSource(tmp_path / "nope.yaml").load()


def test_empty_courses_raises(tmp_path: Path) -> None:
    path = write_yaml(tmp_path, "courses: []\n")
    with pytest.raises(SourceError, match="non-empty list"):
        YamlSource(path).load()


def test_invalid_spec_raises(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path,
        """
courses:
  - fullname: missing template_id
    shortname: x
    category_id: 1
""",
    )
    with pytest.raises(SourceError, match="invalid"):
        YamlSource(path).load()


def test_rejects_unknown_field(tmp_path: Path) -> None:
    path = write_yaml(
        tmp_path,
        """
courses:
  - template_id: 10
    fullname: A
    shortname: a
    category_id: 1
    typo_field: ups
""",
    )
    with pytest.raises(SourceError):
        YamlSource(path).load()
