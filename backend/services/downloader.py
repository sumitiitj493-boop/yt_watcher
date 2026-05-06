import yt_dlp
import asyncio
import os
import uuid
from typing import Dict

# Dictionary to hold the download progress of tasks
# Structure: { video_id: {"status": "downloading", "percent": 0.0, "title": "", ...} }
download_tasks: Dict[str, dict] = {}

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def progress_hook(d):
    video_id = d.get('info_dict', {}).get('id', 'unknown')
    # Using our own internal track ID if we pass it, but for simplicity let's rely on extraction.
    # Actually, better to pass standard ID by accessing the current state.
    pass

def start_download_sync(url: str, task_id: str, quality: str, format_ext: str):
    download_tasks[task_id] = {"status": "starting", "percent": 0, "title": "Unknown"}

    def hook(d):
        if d['status'] == 'downloading':
            # clean ansi escape characters from percent_str if any
            pct_str = d.get('_percent_str', '0%').strip()
            # simple strip of ANSI codes (not perfect but works for yt-dlp standard output)
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            pct_str = ansi_escape.sub('', pct_str)
            
            download_tasks[task_id]['status'] = 'downloading'
            download_tasks[task_id]['percent'] = pct_str
            download_tasks[task_id]['speed'] = ansi_escape.sub('', d.get('_speed_str', ''))
            download_tasks[task_id]['eta'] = ansi_escape.sub('', d.get('_eta_str', ''))
            
        elif d['status'] == 'finished':
            download_tasks[task_id]['status'] = 'processing'
            download_tasks[task_id]['percent'] = '100%'

    format_string = 'bestvideo+bestaudio/best'
    if quality != 'best':
        # simplification: limits video height. e.g. "1080"
        format_string = f'bestvideo[height<={quality}]+bestaudio/best'

    ydl_opts = {
        'format': format_string,
        'merge_output_format': format_ext,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s (%(id)s).%(ext)s'),
        'progress_hooks': [hook],
        'quiet': True,
        'noplaylist': True, # by default, let's keep it single video for now
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            download_tasks[task_id]['title'] = info.get('title', 'Unknown')
            ydl.download([url])
            
        download_tasks[task_id]['status'] = 'completed'
    except Exception as e:
        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = str(e)


async def initiate_download(url: str, quality: str = "best", format_ext: str = "mp4"):
    task_id = str(uuid.uuid4())
    # Runs the synchronous yt-dlp in a background thread so it doesn't block FastAPI
    asyncio.create_task(asyncio.to_thread(start_download_sync, url, task_id, quality, format_ext))
    return task_id

def get_download_status(task_id: str):
    return download_tasks.get(task_id, {"status": "not_found"})
