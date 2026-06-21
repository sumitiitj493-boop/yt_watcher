from pydantic import BaseModel, Field, HttpUrl, field_validator

ALLOWED_FORMATS = {"mp4", "webm", "mkv", "mp3", "m4a"}
ALLOWED_QUALITIES = {"best", "2160", "1440", "1080", "720", "480", "360", "240", "144"}
class DownloadRequest(BaseModel):
    url: HttpUrl
    quality: str = Field(default="best")
    format: str = Field(default="mp4")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_FORMATS:
            raise ValueError("Unsupported format")
        return normalized

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, value: str) -> str:
        normalized = value.strip().lower().replace("p", "")
        if normalized not in ALLOWED_QUALITIES:
            raise ValueError("Unsupported quality")
        return normalized


class MetadataRequest(BaseModel):
    url: HttpUrl


class SocialDownloadRequest(BaseModel):
    url: HttpUrl
    quality: str = Field(default="best")
    format: str = Field(default="mp4")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_FORMATS:
            raise ValueError("Unsupported format")
        return normalized

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, value: str) -> str:
        normalized = value.strip().lower().replace("p", "")
        if normalized not in ALLOWED_QUALITIES:
            raise ValueError("Unsupported quality")
        return normalized
