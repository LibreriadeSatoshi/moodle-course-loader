from __future__ import annotations

import io
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

from moodle_loader.config import Settings
from moodle_loader.exceptions import MoodleAPIError


class _SourceAddressAdapter(HTTPAdapter):
    """HTTPAdapter that binds every outgoing connection to a specific local IP.

    Needed on macOS with ZeroTier (feth interface mode) where routes are
    IFSCOPE-flagged and only reachable when the socket is bound to the
    correct source interface.
    """

    def __init__(self, source_address: str, **kwargs: Any) -> None:
        self._source = (source_address, 0)
        super().__init__(**kwargs)

    def init_poolmanager(
        self, connections: int, maxsize: int, block: bool = False, **kwargs: Any
    ) -> None:
        kwargs["source_address"] = self._source
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **kwargs,
        )


class MoodleClient:
    """Wrapper around the Moodle Web Services API."""

    def __init__(self, settings: Settings, timeout: float = 30.0):
        self._settings = settings
        self._timeout = timeout
        self._session = requests.Session()
        if settings.moodle_source_address:
            adapter = _SourceAddressAdapter(settings.moodle_source_address)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

    @property
    def base_url(self) -> str:
        """Moodle site base URL with no trailing slash (e.g. for building links)."""
        return self._settings.moodle_url.rstrip("/")

    def call(self, function: str, **params: Any) -> Any:
        payload = {
            "wstoken": self._settings.moodle_token,
            "wsfunction": function,
            "moodlewsrestformat": "json",
            **params,
        }
        response = self._session.post(
            self._settings.rest_endpoint, data=payload, timeout=self._timeout
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and "exception" in data:
            raise MoodleAPIError(
                function=function,
                exception=data.get("exception", ""),
                errorcode=data.get("errorcode", ""),
                message=data.get("message", ""),
            )
        return data

    # --- High-level endpoints ------------------------------------------

    def site_info(self) -> dict:
        return self.call("core_webservice_get_site_info")

    def duplicate_course(
        self,
        *,
        courseid: int,
        fullname: str,
        shortname: str,
        categoryid: int,
        visible: bool = False,
    ) -> dict:
        return self.call(
            "core_course_duplicate_course",
            courseid=courseid,
            fullname=fullname,
            shortname=shortname,
            categoryid=categoryid,
            visible=1 if visible else 0,
        )

    def update_course(
        self,
        *,
        course_id: int,
        fullname: str | None = None,
        summary: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {"courses[0][id]": course_id}
        if fullname is not None:
            params["courses[0][fullname]"] = fullname
        if summary is not None:
            params["courses[0][summary]"] = summary
        return self.call("core_course_update_courses", **params)

    def delete_course(self, course_id: int) -> Any:
        return self.call("core_course_delete_courses", **{"courseids[0]": course_id})

    def get_course_contents(self, course_id: int) -> list[dict]:
        return self.call("core_course_get_contents", courseid=course_id)

    def get_categories(self) -> list[dict]:
        return self.call("core_course_get_categories")

    def get_course_by_shortname(self, shortname: str) -> dict | None:
        result = self.call(
            "core_course_get_courses_by_field", field="shortname", value=shortname
        )
        courses = result.get("courses", []) if isinstance(result, dict) else []
        return courses[0] if courses else None

    def create_course(
        self,
        *,
        fullname: str,
        shortname: str,
        categoryid: int,
        summary: str = "",
        visible: bool = False,
        numsections: int = 1,
    ) -> dict:
        """Create a course via core_course_create_courses.

        Returns the first element of the API response list, e.g. {"id": 42, "shortname": "btc101"}.
        """
        params: dict[str, Any] = {
            "courses[0][fullname]": fullname,
            "courses[0][shortname]": shortname,
            "courses[0][categoryid]": categoryid,
            "courses[0][summary]": summary,
            "courses[0][summaryformat]": 1,
            "courses[0][visible]": 1 if visible else 0,
            "courses[0][courseformatoptions][0][name]": "numsections",
            "courses[0][courseformatoptions][0][value]": numsections,
        }
        result = self.call("core_course_create_courses", **params)
        return result[0]

    def upload_file(
        self,
        *,
        filename: str,
        file_bytes: bytes,
        draft_item_id: int = 0,
    ) -> dict:
        """Upload a file to the current user's draft area via upload.php.

        Pass draft_item_id=0 for a new draft area; Moodle assigns an itemid.
        Subsequent calls with the returned itemid add files to the same draft area.
        Returns the upload response dict (keys: itemid, filepath, filename, ...).
        """
        response = self._session.post(
            self._settings.upload_endpoint,
            files={
                "file_1": (filename, io.BytesIO(file_bytes), "application/octet-stream")
            },
            data={
                "token": self._settings.moodle_token,
                "filearea": "draft",
                "itemid": str(draft_item_id),
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "exception" in payload:
            raise MoodleAPIError(
                function="upload_file",
                exception=payload.get("exception", ""),
                errorcode=payload.get("errorcode", ""),
                message=payload.get("message", ""),
            )
        return payload[0]

    def set_course_image(
        self,
        *,
        course_id: int,
        filename: str,
        imagedata: str,
        mimetype: str,
    ) -> Any:
        """Upload and set the course overview image.

        imagedata must be a base64-encoded string of the raw image bytes.
        """
        return self.call(
            "local_moodlecourseloader_set_course_image",
            courseid=course_id,
            filename=filename,
            imagedata=imagedata,
            mimetype=mimetype,
        )

    def update_section(
        self,
        *,
        course_id: int,
        section_number: int,
        name: str = "",
        summary: str = "",
    ) -> Any:
        """Rename/update a course section via local_moodlecourseloader_update_section."""
        return self.call(
            "local_moodlecourseloader_update_section",
            courseid=course_id,
            sectionnum=section_number,
            name=name,
            summary=summary,
        )

    def create_page(
        self,
        *,
        course_id: int,
        section_number: int,
        name: str,
        content: str,
        visible: int = 1,
    ) -> Any:
        """Create a Page activity via local_moodlecourseloader_create_page.

        content must be an HTML string. Images should be embedded as data URIs
        since the plugin stores content as-is without a file area association.
        """
        return self.call(
            "local_moodlecourseloader_create_page",
            courseid=course_id,
            sectionnum=section_number,
            name=name,
            content=content,
            visible=visible,
        )
