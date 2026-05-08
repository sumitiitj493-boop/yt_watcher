import re
import subprocess
import os

import requests


# Config
VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
PROJECT_ID = "prj_E55zGt0GxM2iLtBNuGcMnPishXXP"
ENV_VAR_ID = "JPyRcS55y3qwpaGW"
CLOUDFLARED_PATH = "C:\\Users\\HP\\cloudflared.exe"


def update_vercel(url):
    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Step 1: Update env variable
    r = requests.patch(
        f"https://api.vercel.com/v9/projects/{PROJECT_ID}/env/{ENV_VAR_ID}",
        headers=headers,
        json={"value": f"{url}/api"}
    )
    if r.status_code == 200:
        print(f"Vercel env updated: {url}/api ✅")
    else:
        print(f"Env update failed: {r.text}")
        return False

    # Step 2: Trigger redeploy via git push
    import subprocess
    result = subprocess.run(
        ['git', '-C', r'D:\\semesters\\sem4\\projects\\yt_watcher', 
         'commit', '--allow-empty', '-m', 'auto: update tunnel url'],
        capture_output=True, text=True
    )
    
    result2 = subprocess.run(
        ['git', '-C', r'D:\\semesters\\sem4\\projects\\yt_watcher', 
         'push'],
        capture_output=True, text=True
    )
    
    if result2.returncode == 0:
        print("Redeploy triggered via git push ✅")
        print("App will be ready in ~2 minutes")
    else:
        print(f"Git push failed: {result2.stderr}")
    
    return True


def start_tunnel():
    print("Starting Cloudflare tunnel...")
    process = subprocess.Popen(
        [CLOUDFLARED_PATH, "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    url = None
    for line in process.stderr:
        print(line.strip())
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if match:
          url = match.group(0)
          print(f"\nGot URL: {url}")
          update_vercel(url)
          break

    if url:
        print("\nTunnel running. Keeping alive...")
        process.wait()
    else:
        print("Could not get tunnel URL!")


if __name__ == "__main__":
    start_tunnel()