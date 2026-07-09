import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
VUE_INDEX = ROOT_DIR / "frontend" / "dist" / "index.html"


def relaunch_with_backend_venv() -> None:
    if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        raise SystemExit(subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve())]))


def run_server() -> None:
    sys.path.insert(0, str(BACKEND_DIR))
    try:
        import uvicorn
        from app.core.config import get_settings
    except ModuleNotFoundError as exc:
        if exc.name != "uvicorn":
            raise
        print(
            "Missing backend dependency: uvicorn\n\n"
            "Run these commands first:\n"
            "  cd backend\n"
            "  python -m venv .venv\n"
            "  .\\.venv\\Scripts\\Activate.ps1\n"
            "  pip install -r requirements.txt\n"
            "  cd ..\n"
            "  python run.py",
            file=sys.stderr,
        )
        raise SystemExit(1)

    settings = get_settings()
    if not VUE_INDEX.exists():
        print(
            "Warning: frontend/dist/index.html not found. "
            "Page routes will return 503 until you run: cd frontend && npm install && npm run build",
            file=sys.stderr,
        )

    uvicorn.run("app.main:app", host=settings.server_host, port=settings.server_port, reload=True)


if __name__ == "__main__":
    relaunch_with_backend_venv()
    run_server()
