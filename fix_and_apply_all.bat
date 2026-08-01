@echo off
REM ============================================================
REM  Clean recovery for YT Suite source files
REM
REM  What this does:
REM    1. git reset --hard   -> restore tracked source files to the
REM                             original repo.
REM    2. git clean -fd      -> remove leftover untracked files from
REM                             earlier partial patch applications.
REM                             ONLY this script itself is kept.
REM    3. git apply multi_playlist_full.patch -> apply everything.
REM
REM  YOUR DATA IS 100% SAFE:
REM    - videos, playlists, transcripts, database all live in
REM      backend\downloads\  which git ignores entirely.
REM    - node_modules, venv, .env are ignored too.
REM
REM  After this: run start.bat and hard-refresh the browser.
REM ============================================================
cd /d "%~dp0"

echo.
echo  This will reset source files to the original repo and then
echo  re-apply the full feature patch (multi_playlist_full.patch).
echo.
echo  Your downloads, playlists and transcripts are NOT touched.
echo.
echo  If you have ANY hand-made code edits you want to keep, close
echo  this window now and tell the person who gave you this file.
echo.
pause

git reset --hard
if errorlevel 1 (
    echo.
    echo  ERROR: git reset failed. Is this a git repository?
    pause
    exit /b 1
)

if not exist multi_playlist_full.patch (
    echo.
    echo  ERROR: multi_playlist_full.patch is missing from this folder.
    echo  Copy the latest one here first, then run this again.
    pause
    exit /b 1
)

echo.
echo  Cleaning leftover untracked files from previous patch attempts ...
git clean -fd -e "*.patch" -e "fix_and_apply_all.bat"
if errorlevel 1 (
    echo  (git clean reported nothing to remove or a warning - continuing)
)

echo.
echo  Applying multi_playlist_full.patch ...
git apply multi_playlist_full.patch
if errorlevel 1 (
    echo.
    echo  ERROR: the patch did not apply. Tell the person who gave
    echo  you this file and paste them the error text.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   DONE! Source files are restored and updated.
echo   Now run start.bat and hard-refresh the
echo   browser with Ctrl+Shift+R.
echo  ============================================
echo.
pause
