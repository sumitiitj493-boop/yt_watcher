# YT Private Suite

Self-hosted YouTube downloader and private viewer built for local disk storage.

## Production setup

This repo is now wired for a self-hosted Docker deployment:

- Backend runs as a single FastAPI container because download state is kept in memory.
- Frontend is built as a static nginx container.
- Downloads and logs are persisted in Docker volumes.
- The frontend proxies `/api` to the backend, so the app works on a single public origin.

## Run locally with Docker

```bash
docker compose up -d --build
```

Open the app at `http://localhost:8080`.

## Coolify deployment

Use the same Docker setup in Coolify:

1. Deploy this repo as a Docker Compose app.
2. Expose only the frontend service publicly on port `80`.
3. Keep the backend service internal.
4. Attach persistent volumes for `downloads` and `logs`.
5. Keep the backend at a single replica.

If you want a public URL without opening ports on your machine, use Cloudflare Tunnel.

### Cloudflare Tunnel

1. Create a tunnel in Cloudflare Zero Trust.
2. Point the public hostname to `http://frontend:80`.
3. Copy the tunnel token into `CLOUDFLARED_TUNNEL_TOKEN`.
4. Start the tunnel with:

```bash
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml --profile tunnel up -d --build
```

That keeps the app private on your machine while still giving you a public URL.

## Important note

Do not scale the backend to multiple replicas unless you move download state out of memory and into a shared store. The current code keeps job status in process memory.