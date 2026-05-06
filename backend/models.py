from pydantic import BaseModel

class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"
    format: str = "mp4"
