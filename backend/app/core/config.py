from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "zhiyan-a3-api"
    app_env: str = "development"
    server_host: str = "127.0.0.1"
    server_port: int = 18000
    database_url: str = "postgresql+psycopg://zhiyan:zhiyan@localhost:5432/zhiyan_a3"
    jwt_secret_key: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    llm_provider: str = "qwen"
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_base_url: str = "https://ws-1ulzsdw0gslyucjg.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    qwen_timeout_seconds: int = 180
    xunfei_app_id: str = ""
    xunfei_api_key: str = ""
    xunfei_api_secret: str = ""
    knowledge_upload_dir: str = str(BACKEND_DIR / "uploaded_knowledge")
    knowledge_embedding_provider: str = "qwen"
    knowledge_embedding_model: str = "text-embedding-v3"
    knowledge_embedding_dim: int = 1024
    knowledge_chunk_chars: int = 1200
    knowledge_chunk_overlap: int = 180
    knowledge_max_upload_mb: int = 300
    local_ocr_engine: str = "tesseract"
    tesseract_cmd: str = ""
    libreoffice_path: str = ""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
