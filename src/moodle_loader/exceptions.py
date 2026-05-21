class MoodleError(Exception):
    """Base error for moodle-loader."""


class MoodleAPIError(MoodleError):
    """The Moodle API returned an object containing `exception`."""

    def __init__(self, function: str, exception: str, errorcode: str, message: str):
        self.function = function
        self.exception = exception
        self.errorcode = errorcode
        self.message = message
        super().__init__(f"{function}: [{errorcode}] {message}")


class SourceError(MoodleError):
    """Error while reading or validating a course source."""
