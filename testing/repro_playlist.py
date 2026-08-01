from pathlib import Path
import tempfile, shutil, sys
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'backend'))

import services.files as files_mod
from fastapi import FastAPI
from fastapi.testclient import TestClient

# prepare temp downloads
tmp_dir = Path(tempfile.mkdtemp(prefix='yt_repro_'))
files_mod.DOWNLOAD_DIR = tmp_dir
(tmp_dir / 'Song One.mp3').write_bytes(b'0'*2048)
(tmp_dir / 'Video Two.mp4').write_bytes(b'0'*2048)
(tmp_dir / 'Clip Three.webm').write_bytes(b'0'*2048)
(tmp_dir / 'ignore.tmp').write_bytes(b'0'*2048)

from routes import library as library_routes
app = FastAPI()
app.include_router(library_routes.router, prefix='/api')
client = TestClient(app)

print('GET playlists', client.get('/api/playlists').status_code, client.get('/api/playlists').json())
resp = client.post('/api/playlists', json={'name':'Workout'})
print('create Workout', resp.status_code, resp.json())
workout_id = resp.json()['playlist']['id']

resp = client.post(f'/api/playlists/{workout_id}/items', json={'filename':'Song One.mp3'})
print('add Song One to workout', resp.status_code, resp.json())

resp = client.post(f'/api/playlists/{workout_id}/items/batch', json={'filenames':['Video Two.mp4','Clip Three.webm','Video Two.mp4','missing.mp4','Song One.mp3']})
print('batch to workout', resp.status_code, resp.json())

default_id = client.get('/api/playlists').json()['playlists'][0]['id']
resp = client.post(f'/api/playlists/{default_id}/items/batch', json={'filenames':['Song One.mp3','Video Two.mp4']})
print('batch to default', resp.status_code, resp.json())

print('default items', client.get(f'/api/playlists/{default_id}/items').json())
print('workout items', client.get(f'/api/playlists/{workout_id}/items').json())

shutil.rmtree(tmp_dir)
