from pydantic import BaseModel, Field, HttpUrl, field_validator

ALLOWED_FORMATS = {"mp4", "webm", "mkv", "mp3", "m4a"}
ALLOWED_SOCIAL_FORMATS = ALLOWED_FORMATS | {"best"}
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


class PlaylistEntriesRequest(BaseModel):
    """Request the full entry list of a playlist from a single playlist URL."""
    url: HttpUrl


class PlaylistDownloadRequest(BaseModel):
    """Queue selected videos from a playlist as a batch download.

    ``indices`` are 1-based positions in the playlist (e.g. [3, 4, 5] for
    videos 3 to 5, or [1, 3, 7] for specific videos). The user only ever
    pastes the playlist link — the backend resolves each video itself.
    """
    url: HttpUrl
    indices: list[int] = Field(default_factory=list)
    quality: str = Field(default="best")
    format: str = Field(default="mp4")
    target_playlist_id: int | None = Field(default=None)
    sequential: bool = Field(default=True)
    fetch_transcripts: bool = Field(default=False)
    transcript_folder: str = Field(default="", max_length=120)
    transcripts_only: bool = Field(default=False)

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


class MultiDownloadRequest(BaseModel):
    """Queue many individual URLs (any platform) as one batch download.

    URLs keep their order in the queue. Optionally fetch YouTube auto
    transcripts for each (parallel), auto-save downloads into a local
    playlist, and group transcripts under a folder.
    """
    urls: list[str] = Field(min_length=1, max_length=200)
    quality: str = Field(default="best")
    format: str = Field(default="mp4")
    target_playlist_id: int | None = Field(default=None)
    sequential: bool = Field(default=True)
    fetch_transcripts: bool = Field(default=False)
    transcript_folder: str = Field(default="", max_length=120)
    transcripts_only: bool = Field(default=False)

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


class TranscriptUrlRequest(BaseModel):
    url: HttpUrl
    force: bool = Field(default=False)


class WhisperLibraryRequest(BaseModel):
    """Transcribe a file that is already saved in the library (e.g. from a playlist)."""
    filename: str = Field(min_length=1, max_length=500)
    force: bool = Field(default=False)


class TranscriptSaverCreateRequest(BaseModel):
    """Manually save (or update) a transcript in the Transcript Saver."""
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=1_000_000)
    url: str = Field(default="", max_length=2000)
    folder: str = Field(default="", max_length=120)


class TranscriptSaverFetchRequest(BaseModel):
    """Fetch a YouTube auto transcript and save it into the saver."""
    url: HttpUrl
    folder: str = Field(default="", max_length=120)


class TranscriptSaverUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    text: str | None = Field(default=None, min_length=1, max_length=1_000_000)
    url: str | None = Field(default=None, max_length=2000)
    folder: str | None = Field(default=None, max_length=120)


class PlaylistTranscriptsRequest(BaseModel):
    """Re-fetch YouTube transcripts for a saved playlist's videos (no download).

    ``indices`` are 1-based positions in the playlist (None = all videos).
    """
    indices: list[int] | None = Field(default=None)
    transcript_folder: str = Field(default="", max_length=120)


class ConvertFormatsRequest(BaseModel):
    """Ask which target formats are available for a source extension."""
    ext: str = Field(default="", max_length=10)


class ConvertRequest(BaseModel):
    """Convert a library file to any supported format (free, ffmpeg)."""
    filename: str = Field(min_length=1, max_length=500)
    target_format: str = Field(default="mp4", max_length=10)
    bitrate: str = Field(default="192k", max_length=10)
    resolution: str = Field(default="", max_length=10)


class ClipAnalyzeRequest(BaseModel):
    """Ask for a video's duration/metadata (no cutting)."""
    filename: str = Field(min_length=1, max_length=500)


class ClipCreateRequest(BaseModel):
    """Cut a clip from a downloaded video between two timestamps."""
    filename: str = Field(min_length=1, max_length=500)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    title: str = Field(default="", max_length=200)
    collection: str = Field(default="", max_length=120)
    target_playlist_id: int | None = Field(default=None)
    mode: str = Field(default="smart", max_length=20)


class SocialDownloadRequest(BaseModel):
    url: HttpUrl
    quality: str = Field(default="best")
    format: str = Field(default="best")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_SOCIAL_FORMATS:
            raise ValueError("Unsupported format")
        return normalized

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, value: str) -> str:
        normalized = value.strip().lower().replace("p", "")
        if normalized not in ALLOWED_QUALITIES:
            raise ValueError("Unsupported quality")
        return normalized
