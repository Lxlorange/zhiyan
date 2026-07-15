from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
if engine.dialect.name == "postgresql":
    from pgvector.psycopg import register_vector
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _register_pgvector(dbapi_connection, connection_record) -> None:
        register_vector(dbapi_connection)

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
        "CREATE EXTENSION IF NOT EXISTS vector",
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
        "ALTER TABLE classroom_sessions ADD COLUMN IF NOT EXISTS slides_completed BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE classroom_sessions ADD COLUMN IF NOT EXISTS slide_progress JSONB NOT NULL DEFAULT '{}'",
        "ALTER TABLE daily_learning_plans ADD COLUMN IF NOT EXISTS study_weekends BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE daily_learning_plans ADD COLUMN IF NOT EXISTS study_weekdays JSONB NOT NULL DEFAULT '[0, 1, 2, 3, 4]'::jsonb",
        "ALTER TABLE daily_learning_plan_items ADD COLUMN IF NOT EXISTS planned_date TIMESTAMP NOT NULL DEFAULT now()",
        """
        CREATE TABLE IF NOT EXISTS literature_papers (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            project_id INTEGER NULL REFERENCES learning_projects(id),
            title VARCHAR(255) NOT NULL,
            authors JSONB NOT NULL DEFAULT '[]'::jsonb,
            venue VARCHAR(255) NOT NULL DEFAULT '',
            year VARCHAR(32) NOT NULL DEFAULT '',
            source_uri VARCHAR(512) NOT NULL DEFAULT '',
            abstract TEXT NOT NULL DEFAULT '',
            keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
            reading_status VARCHAR(32) NOT NULL DEFAULT 'unread',
            notes TEXT NOT NULL DEFAULT '',
            citation_text TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_literature_papers_user_id ON literature_papers(user_id)",
        """
        CREATE TABLE IF NOT EXISTS research_tool_runs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            project_id INTEGER NULL REFERENCES learning_projects(id),
            tool_type VARCHAR(64) NOT NULL,
            title VARCHAR(255) NOT NULL,
            input_text TEXT NOT NULL,
            output_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            agent_trace JSONB NOT NULL DEFAULT '[]'::jsonb,
            status VARCHAR(32) NOT NULL DEFAULT 'completed',
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_research_tool_runs_user_id ON research_tool_runs(user_id)",
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS file_path VARCHAR(1024) NOT NULL DEFAULT ''",
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS file_name VARCHAR(512) NOT NULL DEFAULT ''",
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS file_hash VARCHAR(128) NOT NULL DEFAULT ''",
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS course_code VARCHAR(64) NOT NULL DEFAULT ''",
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS parse_status VARCHAR(32) NOT NULL DEFAULT 'ready'",
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS parse_meta JSONB NOT NULL DEFAULT '{}'::jsonb",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_file_hash ON knowledge_documents(file_hash)",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_course_code ON knowledge_documents(course_code)",
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_no INTEGER NULL",
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS slide_no INTEGER NULL",
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_title VARCHAR(255) NOT NULL DEFAULT ''",
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS token_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(1024) NULL",
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS retrieval_weight DOUBLE PRECISION NOT NULL DEFAULT 1.0",
        "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS extra_meta JSONB NOT NULL DEFAULT '{}'::jsonb",
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)",
        """
        CREATE TABLE IF NOT EXISTS knowledge_import_jobs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            course_code VARCHAR(64) NOT NULL,
            course_title VARCHAR(255) NOT NULL,
            source_name VARCHAR(512) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'running',
            total_files INTEGER NOT NULL DEFAULT 0,
            parsed_files INTEGER NOT NULL DEFAULT 0,
            failed_files INTEGER NOT NULL DEFAULT 0,
            total_chunks INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NOT NULL DEFAULT '',
            options JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_knowledge_import_jobs_user_id ON knowledge_import_jobs(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_import_jobs_course_code ON knowledge_import_jobs(course_code)",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_import_jobs_status ON knowledge_import_jobs(status)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_postgres_extensions() -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def init_db() -> None:
    import app.models.learning  # noqa: F401
    import app.models.user  # noqa: F401
    from app.services.direction_service import seed_direction_templates
    from app.services.knowledge_service import seed_course_knowledge

    _ensure_postgres_extensions()
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
    db = SessionLocal()
    try:
        seed_course_knowledge(db)
        seed_direction_templates(db)
    finally:
        db.close()
