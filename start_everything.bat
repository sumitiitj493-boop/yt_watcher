@echo off
echo Starting local backend only (Cloudflare disabled)...

cd /d D:\semesters\sem4\projects\yt_watcher\backend
call C:\Users\HP\anaconda3\Scripts\activate.bat base

echo Running FastAPI on http://127.0.0.1:8000
echo Press Ctrl+C to stop.
uvicorn main:app --host 127.0.0.1 --port 8000
