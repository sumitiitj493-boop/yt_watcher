from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import download, library, stream

app = FastAPI(title="YT Private Suite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(download.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(stream.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Hello World from YT Private Suite Backend!"}
