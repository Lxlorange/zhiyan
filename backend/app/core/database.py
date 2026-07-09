from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _apply_lightweight_migrations() -> None:
    if engine.dialect.name != "postgresql":
        return
    statements = [
        "ALTER TABLE research_directions ADD COLUMN IF NOT EXISTS analysis_revision INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE research_directions ADD COLUMN IF NOT EXISTS review_status VARCHAR(32) NOT NULL DEFAULT 'pending'",
        "ALTER TABLE research_directions ADD COLUMN IF NOT EXISTS review_notes TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE research_directions ADD COLUMN IF NOT EXISTS reviewed_by_user_id INTEGER NULL",
        "ALTER TABLE research_directions ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP NULL",
        "ALTER TABLE learning_projects ADD COLUMN IF NOT EXISTS deadline TIMESTAMP NULL",
        "ALTER TABLE learning_projects ADD COLUMN IF NOT EXISTS teacher_notes TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512) NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS school VARCHAR(128) NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS major VARCHAR(128) NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio VARCHAR(512) NOT NULL DEFAULT ''",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def init_db() -> None:
    import app.models.learning  # noqa: F401
    import app.models.user  # noqa: F401
    from app.services.direction_service import seed_direction_templates
    from app.services.knowledge_service import seed_course_knowledge

    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
    db = SessionLocal()
    try:
        seed_course_knowledge(db)
        seed_direction_templates(db)
    finally:
        db.close()
