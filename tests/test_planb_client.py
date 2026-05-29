from __future__ import annotations

from urllib.parse import unquote_plus

import pytest
import responses

from moodle_loader.client import MoodleClient
from moodle_loader.exceptions import MoodleAPIError

REST_URL = "https://moodle.test/webservice/rest/server.php"
UPLOAD_URL = "https://moodle.test/webservice/upload.php"


# ---------------------------------------------------------------------------
# create_course
# ---------------------------------------------------------------------------


@responses.activate
def test_create_course_sends_correct_params(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        REST_URL,
        json=[{"id": 10, "shortname": "btc101"}],
        status=200,
    )
    client.create_course(
        fullname="Bitcoin 101",
        shortname="btc101",
        categoryid=3,
        summary="A course about Bitcoin",
        visible=True,
        numsections=5,
    )
    decoded = unquote_plus(responses.calls[0].request.body)
    assert "wsfunction=core_course_create_courses" in decoded
    assert "courses[0][fullname]=Bitcoin 101" in decoded
    assert "courses[0][shortname]=btc101" in decoded
    assert "courses[0][categoryid]=3" in decoded
    assert "courses[0][summaryformat]=1" in decoded
    assert "courses[0][visible]=1" in decoded
    assert "courses[0][courseformatoptions][0][name]=numsections" in decoded
    assert "courses[0][courseformatoptions][0][value]=5" in decoded


@responses.activate
def test_create_course_returns_first_element(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        REST_URL,
        json=[{"id": 99, "shortname": "x"}],
        status=200,
    )
    result = client.create_course(
        fullname="X",
        shortname="x",
        categoryid=1,
    )
    assert result == {"id": 99, "shortname": "x"}


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


@responses.activate
def test_upload_file_posts_to_upload_endpoint(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        UPLOAD_URL,
        json=[{"itemid": 55, "filepath": "/", "filename": "test.png"}],
        status=200,
    )
    result = client.upload_file(
        filename="test.png",
        file_bytes=b"fake-image-data",
    )
    assert responses.calls[0].request.url == UPLOAD_URL
    assert result == {"itemid": 55, "filepath": "/", "filename": "test.png"}


@responses.activate
def test_upload_file_raises_on_exception_response(client: MoodleClient) -> None:
    responses.add(
        responses.POST,
        UPLOAD_URL,
        json={
            "exception": "upload_exception",
            "errorcode": "e",
            "message": "upload failed",
        },
        status=200,
    )
    with pytest.raises(MoodleAPIError) as excinfo:
        client.upload_file(filename="bad.png", file_bytes=b"data")
    assert excinfo.value.function == "upload_file"
    assert excinfo.value.errorcode == "e"
    assert "upload failed" in str(excinfo.value)


# ---------------------------------------------------------------------------
# set_course_image
# ---------------------------------------------------------------------------


@responses.activate
def test_set_course_image_calls_correct_function(client: MoodleClient) -> None:
    responses.add(responses.POST, REST_URL, json={"success": True}, status=200)
    client.set_course_image(
        course_id=42,
        filename="cover.webp",
        imagedata="abc123base64",
        mimetype="image/webp",
    )
    decoded = unquote_plus(responses.calls[0].request.body)
    assert "wsfunction=local_moodlecourseloader_set_course_image" in decoded
    assert "courseid=42" in decoded
    assert "filename=cover.webp" in decoded
    assert "imagedata=abc123base64" in decoded
    assert "mimetype=image/webp" in decoded


# ---------------------------------------------------------------------------
# update_section
# ---------------------------------------------------------------------------


@responses.activate
def test_update_section_calls_correct_function(client: MoodleClient) -> None:
    responses.add(responses.POST, REST_URL, json={"success": True}, status=200)
    client.update_section(
        course_id=42,
        section_number=2,
        name="Week 2",
        summary="Section summary",
    )
    decoded = unquote_plus(responses.calls[0].request.body)
    assert "wsfunction=local_moodlecourseloader_update_section" in decoded
    assert "courseid=42" in decoded
    assert "sectionnum=2" in decoded
    assert "name=Week 2" in decoded
    assert "summaryformat" not in decoded


# ---------------------------------------------------------------------------
# create_page
# ---------------------------------------------------------------------------


@responses.activate
def test_create_page_calls_correct_function(client: MoodleClient) -> None:
    responses.add(responses.POST, REST_URL, json={"cmid": 7}, status=200)
    client.create_page(
        course_id=42,
        section_number=1,
        name="My Page",
        content="<p>Hello</p>",
    )
    decoded = unquote_plus(responses.calls[0].request.body)
    assert "wsfunction=local_moodlecourseloader_create_page" in decoded
    assert "courseid=42" in decoded
    assert "sectionnum=1" in decoded
    assert "name=My Page" in decoded
    assert "visible=1" in decoded
    assert "contentformat" not in decoded
    assert "files_itemid" not in decoded
