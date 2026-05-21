from __future__ import annotations

from typing import Any

import requests

from moodle_loader.config import Settings
from moodle_loader.exceptions import MoodleAPIError


class MoodleClient:
    """Wrapper around the Moodle Web Services API."""

    def __init__(self, settings: Settings, timeout: float = 30.0):
        self._settings = settings
        self._timeout = timeout
        self._session = requests.Session()

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
        result = self.call("core_course_get_courses_by_field", field="shortname", value=shortname)
        courses = result.get("courses", []) if isinstance(result, dict) else []
        return courses[0] if courses else None
