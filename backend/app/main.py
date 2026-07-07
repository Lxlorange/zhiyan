from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import init_db


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

web_dir = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=web_dir), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
