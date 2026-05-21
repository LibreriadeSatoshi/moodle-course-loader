from __future__ import annotations

import pytest

from moodle_loader.client import MoodleClient
from moodle_loader.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        moodle_url="https://moodle.test",
        moodle_token="test-token-1234",
    )


@pytest.fixture
def client(settings: Settings) -> MoodleClient:
    return MoodleClient(settings)
