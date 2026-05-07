from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

ALLOWED_FORMATS = {"mp4", "webm", "mkv", "mp3", "m4a"}
ALLOWED_QUALITIES = {"best", "2160", "1440", "1080", "720", "480", "360", "240", "144"}
ALLOWED_SOCIAL_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.watch",
    "www.fb.watch",
}


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


class SocialDownloadRequest(BaseModel):
    url: HttpUrl
    quality: str = Field(default="best")
    format: str = Field(default="mp4")

    @model_validator(mode="after")
    def validate_social_host(self):
        host = urlparse(str(self.url)).netloc.lower()
        if host not in ALLOWED_SOCIAL_HOSTS and not host.endswith(".instagram.com") and not host.endswith(".facebook.com"):
            raise ValueError("Only public Instagram or Facebook links are supported")
        return self

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
