"""In-process end-to-end test of playlist batch auto-save.

Runs inside the backend's own process so ``download_tasks`` mutations are real.
The sandbox cannot download YouTube media (datacenter bot check), so we let the
first queued video fail naturally, then simulate a successful download by
patching its queue record to 'completed' with a dummy file, and confirm the
batch supervisor auto-adds it to the chosen local playlist.
"""
"""In-process end-to-end test of playlist batch auto-save.

Runs inside the backend's own process so ``download_tasks`` mutations are real.
The sandbox cannot download YouTube media (datacenter bot check), so we let the
first queued video fail naturally, then simulate a successful download by
patching its queue record to 'completed' with a dummy file, and confirm the
batch supervisor auto-adds it to the chosen local playlist.

Run from the project root:  python testing/test_playlist_batch_autosave.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.database import create_playlist, get_playlist_items, list_playlists
from services.downloader import download_tasks
from services.files import DOWNLOAD_DIR
from services.playlist_batch import create_batch, _reconcile

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL590L5WQmH8fJ54F369BLDSqIwcs-TCfs"


async def wait_terminal(batch, index, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        _reconcile(batch)
        item = next(t for t in batch["tasks"] if t["index"] == index)
        if item["status"] in ("completed", "error", "cancelled"):
            return item
        await asyncio.sleep(1)
    raise TimeoutError("task did not reach a terminal state")


async def main():
    target = next((p for p in list_playlists() if p["name"] == "Test Batch Playlist"), None)
    if not target:
        target = create_playlist("Test Batch Playlist")
    print("target playlist:", target["id"], target["name"])

    batch = await create_batch(PLAYLIST_URL, [1, 2], "360", "mp4", target["id"], True)
    print("batch:", batch["id"], "| tasks:", len(batch["tasks"]))

    # Video 1 will fail (YouTube bot check on this sandbox IP) — fine.
    v1 = await wait_terminal(batch, 1)
    print("v1 natural status:", v1["status"], "(expected error on sandbox)")

    # Simulate video 1 finishing successfully.
    dummy = DOWNLOAD_DIR / "Test Video A (KIViy7L_lo8).mp4"
    dummy.write_bytes(b"fake media bytes" * 100)
    download_tasks[v1["task_id"]].update(status="completed", filename=str(dummy))
    print("simulated completion ->", dummy.name)

    # Let the supervisor logic pick it up.
    _reconcile(batch)
    v1 = next(t for t in batch["tasks"] if t["index"] == 1)
    print("after reconcile -> v1:", v1["status"], "| added:", v1.get("added"),
          "| filename:", v1.get("filename"))
    print("batch -> done:", batch["done_count"], "completed:", batch["completed_count"],
          "added:", batch["added_count"], "phase:", batch["phase"])

    items = get_playlist_items(target["id"])
    print("playlist items:", items)
    ok = dummy.name in items and v1.get("added") is True
    print("AUTO-SAVE TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
