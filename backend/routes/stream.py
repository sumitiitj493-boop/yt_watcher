import hashlib
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from services.files import resolve_download_path
from services.stream_state import active_streams

router = APIRouter()

CHUNK_SIZE = 1024 * 1024


def _etag_for_file(file_path: Path) -> str:
    stat = file_path.stat()
    payload = f"{file_path.name}:{stat.st_mtime}:{stat.st_size}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _iter_file(file_path: Path, start: int, end: int):
    # Register that this filename is actively being streamed. This allows
    # other routes to attempt to release or force-close streams when needed.
    active_streams.add(file_path.name)
    try:
        with open(file_path, 'rb') as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = handle.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
    finally:
        # Ensure we always discard on generator completion / cancellation
        try:
            active_streams.discard(file_path.name)
        except Exception:
            pass


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    if not range_header.startswith('bytes='):
        raise ValueError('Invalid range')

    range_value = range_header.removeprefix('bytes=').strip()
    start_text, _, end_text = range_value.partition('-')

    if not start_text:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError('Invalid range')
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1

    if start < 0 or end < start or start >= file_size:
        raise ValueError('Invalid range')

    return start, min(end, file_size - 1)


def build_stream_response(video_id: str, request: Request) -> Response:
    try:
        file_path = resolve_download_path(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid filename')

    if not file_path.exists():
        raise HTTPException(status_code=404, detail='Video not found')

    stat = file_path.stat()
    file_size = stat.st_size
    media_type, _ = mimetypes.guess_type(file_path.name)
    media_type = media_type or 'application/octet-stream'
    etag = _etag_for_file(file_path)

    headers = {
        'Accept-Ranges': 'bytes',
        'ETag': etag,
        'Cache-Control': 'public, max-age=300',
    }

    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers=headers)

    range_header = request.headers.get('range')
    if range_header:
        try:
            start, end = _parse_range(range_header, file_size)
        except (ValueError, TypeError):
            return Response(
                status_code=416,
                headers={
                    **headers,
                    'Content-Range': f'bytes */{file_size}',
                },
            )

        content_length = end - start + 1
        return StreamingResponse(
            _iter_file(file_path, start, end),
            status_code=206,
            media_type=media_type,
            headers={
                **headers,
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Content-Length': str(content_length),
            },
        )

    return StreamingResponse(
        _iter_file(file_path, 0, file_size - 1),
        status_code=200,
        media_type=media_type,
        headers={
            **headers,
            'Content-Length': str(file_size),
        },
    )


@router.get('/stream/{video_id}')
async def stream_video(video_id: str, request: Request):
    return build_stream_response(video_id, request)


@router.head('/stream/{video_id}')
async def stream_video_head(video_id: str, request: Request):
    try:
        file_path = resolve_download_path(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid filename')

    if not file_path.exists():
        raise HTTPException(status_code=404, detail='Video not found')

    stat = file_path.stat()
    media_type, _ = mimetypes.guess_type(file_path.name)
    return Response(
        status_code=200,
        headers={
            'Accept-Ranges': 'bytes',
            'Content-Length': str(stat.st_size),
            'Content-Type': media_type or 'application/octet-stream',
            'ETag': _etag_for_file(file_path),
            'Cache-Control': 'public, max-age=300',
        },
    )
