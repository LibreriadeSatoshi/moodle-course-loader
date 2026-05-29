from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    moodle_url: str = Field(..., description="Moodle base URL, no trailing slash")
    moodle_token: str = Field(..., description="Web Services token")
    default_template_id: int = Field(
        20, description="Template course ID used when sheet row has no template_id"
    )
    default_category_name: str = Field(
        "Bitcoin 4 Everyone",
        description="Fallback category name when Path is not found in Moodle",
    )
    moodle_source_address: str | None = Field(
        None,
        description="Bind outgoing connections to this local IP (e.g. your ZeroTier address on macOS)",
    )
    sheets_worksheet: str = Field(
        "Sheet1", description="Worksheet name to read from Google Sheets"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def rest_endpoint(self) -> str:
        return f"{self.moodle_url.rstrip('/')}/webservice/rest/server.php"

    @property
    def upload_endpoint(self) -> str:
        return f"{self.moodle_url.rstrip('/')}/webservice/upload.php"
