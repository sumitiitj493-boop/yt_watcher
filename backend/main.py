import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from typing import Dict, Tuple

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from routes import about, download, library, stream
from services.database import init_db

app = FastAPI(title="YT Private Suite API")


def _load_local_env_file() -> None:
    env_candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env",
    ]

    for env_path in env_candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_local_env_file()

APP_ACCESS_PASSWORD = os.environ.get("APP_ACCESS_PASSWORD", "").strip()
PASSWORD_HEADER = "X-App-Password"

logger = logging.getLogger("yt_suite")
logs_dir = Path(__file__).resolve().parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
file_handler = RotatingFileHandler(
    logs_dir / "app.log",
    maxBytes=2_000_000,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

RATE_LIMIT_PER_MINUTE = 120
WINDOW_SECONDS = 60
rate_limit_state: Dict[Tuple[str, str], Tuple[int, float]] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/stream") or path.startswith("/api/ws"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, path)
        now = time.time()
        count, window_start = rate_limit_state.get(key, (0, now))

        if now - window_start > WINDOW_SECONDS:
            count = 0
            window_start = now

        count += 1
        rate_limit_state[key] = (count, window_start)

        if count > RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again shortly."},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(max(0, RATE_LIMIT_PER_MINUTE - count))
        response.headers["X-RateLimit-Reset"] = str(int(window_start + WINDOW_SECONDS))
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response: Response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "%s %s %s %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class PasswordProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not APP_ACCESS_PASSWORD:
            return await call_next(request)

        path = request.url.path
        if request.method == "OPTIONS" or path in {"/", "/api/health", "/api/auth/login"}:
            return await call_next(request)

        supplied_password = request.headers.get(PASSWORD_HEADER, "").strip()
        if supplied_password != APP_ACCESS_PASSWORD:
            return JSONResponse(
                status_code=401,
                content={"detail": "Password required"},
            )

        return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(PasswordProtectionMiddleware)

app.include_router(download.router, prefix="/api")
app.include_router(about.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(stream.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    await init_db()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": {
                "message": exc.detail,
                "status": exc.status_code,
                "path": request.url.path,
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": {
                "message": "Internal server error",
                "status": 500,
                "path": request.url.path,
            },
        },
    )

@app.get("/")
def read_root():
    return {"message": "Hello World from YT Private Suite Backend!"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "passwordRequired": bool(APP_ACCESS_PASSWORD)}


@app.post("/api/auth/login")
async def login(request: Request):
    if not APP_ACCESS_PASSWORD:
        return {"authenticated": True, "passwordRequired": False}

    payload = await request.json()
    supplied_password = str(payload.get("password", "")).strip()

    if supplied_password != APP_ACCESS_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    return {"authenticated": True, "passwordRequired": True}
