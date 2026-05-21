from __future__ import annotations

import pytest
import responses

from moodle_loader.client import MoodleClient
from moodle_loader.exceptions import MoodleAPIError

REST_URL = "https://moodle.test/webservice/rest/server.php"


@responses.activate
def test_site_info_returns_payload(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        REST_URL,
        json={"sitename": "Test", "fullname": "Tester", "username": "t"},
        status=200,
    )
    data = client.site_info()
    assert data["sitename"] == "Test"


@responses.activate
def test_call_raises_on_api_exception(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        REST_URL,
        json={
            "exception": "moodle_exception",
            "errorcode": "invalidtoken",
            "message": "Token inválido",
        },
        status=200,
    )
    with pytest.raises(MoodleAPIError) as excinfo:
        client.site_info()
    assert excinfo.value.errorcode == "invalidtoken"
    assert "Token inválido" in str(excinfo.value)


@responses.activate
def test_duplicate_course_sends_expected_params(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        REST_URL,
        json={"id": 42, "shortname": "x"},
        status=200,
    )
    result = client.duplicate_course(
        courseid=10,
        fullname="X",
        shortname="x",
        categoryid=2,
        visible=False,
    )
    assert result["id"] == 42
    body = responses.calls[0].request.body
    assert "wsfunction=core_course_duplicate_course" in body
    assert "courseid=10" in body
    assert "visible=0" in body


@responses.activate
def test_delete_course_uses_array_syntax(client: MoodleClient) -> None:
    responses.add(responses.POST, REST_URL, json=[], status=200)
    client.delete_course(99)
    body = responses.calls[0].request.body
    assert "courseids%5B0%5D=99" in body  # courseids[0]=99 url-encoded


@responses.activate
def test_get_categories_returns_list(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        REST_URL,
        json=[{"id": 2, "name": "Bitcoin 4 Everyone"}, {"id": 3, "name": "Bitcoin Dev"}],
        status=200,
    )
    cats = client.get_categories()
    assert len(cats) == 2
    assert cats[0]["name"] == "Bitcoin 4 Everyone"
    body = responses.calls[0].request.body
    assert "wsfunction=core_course_category_get_categories" in body
