from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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

app_dir = Path(__file__).resolve().parent
repo_root = app_dir.parents[1]
vue_dist_dir = repo_root / "frontend" / "dist"
vue_index = vue_dist_dir / "index.html"

if (vue_dist_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=vue_dist_dir / "assets"), name="vue_assets")


def ensure_vue_dist() -> Path:
    if not vue_index.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Vue frontend build not found. Run `cd frontend && npm install && npm run build` "
                "before starting the integrated FastAPI server."
            ),
        )
    return vue_dist_dir


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{exc.__class__.__name__}: {exc}",
            "path": str(request.url.path),
        },
    )


@app.get("/")
def root() -> FileResponse:
    dist_dir = ensure_vue_dist()
    return FileResponse(dist_dir / "index.html")


@app.get("/{full_path:path}")
def spa_route(full_path: str) -> FileResponse:
    reserved_prefixes = ("api", "docs", "redoc", "openapi.json", "assets")
    if full_path.startswith(reserved_prefixes):
        raise HTTPException(status_code=404, detail="Not found")

    dist_dir = ensure_vue_dist()
    target = dist_dir / full_path
    if target.is_file():
        return FileResponse(target)
    return FileResponse(dist_dir / "index.html")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
