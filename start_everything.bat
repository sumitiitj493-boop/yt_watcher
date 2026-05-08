@echo off
echo Starting YT Suite...
timeout /t 15 /nobreak >nul

:: Vercel token is read from the permanent Windows environment variable
if not defined VERCEL_TOKEN (
	echo VERCEL_TOKEN is not set. Open a new terminal after setting it permanently.
	pause
	exit /b 1
)

:: Optional named Cloudflare tunnel config
:: set CLOUDFLARED_TUNNEL_NAME=yt-suite
:: set CLOUDFLARED_PUBLIC_URL=https://your-permanent-url.example.com

:: Start Backend
cd /d D:\semesters\sem4\projects\yt_watcher\backend
start "YT Backend" cmd /k "C:\Users\HP\anaconda3\Scripts\activate.bat base && uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 8 /nobreak >nul

:: Start Auto Tunnel
cd /d D:\semesters\sem4\projects\yt_watcher
start "YT Tunnel" cmd /k "if defined VERCEL_TOKEN set VERCEL_TOKEN=%VERCEL_TOKEN% && if defined CLOUDFLARED_TUNNEL_NAME set CLOUDFLARED_TUNNEL_NAME=%CLOUDFLARED_TUNNEL_NAME% && if defined CLOUDFLARED_PUBLIC_URL set CLOUDFLARED_PUBLIC_URL=%CLOUDFLARED_PUBLIC_URL% && C:\Users\HP\anaconda3\Scripts\activate.bat base && python auto_tunnel.py"

echo Done! App ready in ~2 minutes.
pause
