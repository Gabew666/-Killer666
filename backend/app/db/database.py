from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base


def create_database(url: str) -> tuple[Engine, sessionmaker[Session]]:
    # Hosted services often provide postgres:// or driverless postgresql://.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    parsed = make_url(url)
    if parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg")
    kwargs: dict = {"pool_pre_ping": True}
    if parsed.get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
        if parsed.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(parsed, **kwargs)
    if parsed.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def set_sqlite_options(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine, sessionmaker(engine, expire_on_commit=False)


def initialize_database(engine: Engine) -> None:
    # Atualização aditiva limitada do SQLite v0.1. Não substitui migrations versionadas.
    Base.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":
        return
    additions = {
        "exercises": {
            "origin_type": "VARCHAR(40)",
            "provenance": "JSON",
        },
        "concepts": {
            "unit_id": "INTEGER REFERENCES curriculum_units(id)",
            "parent_concept_id": "INTEGER REFERENCES concepts(id)",
            "learning_objectives": "JSON",
        },
        "study_sessions": {
            "planned_at": "DATETIME", "started_at": "DATETIME", "used_minutes": "INTEGER DEFAULT 0",
            "actual_minutes": "INTEGER", "current_activity_id": "INTEGER",
            "strategy": "VARCHAR(20)", "adaptation_reason": "TEXT",
        },
        "session_activities": {
            "block_index": "INTEGER",
            "planned_at": "DATETIME", "started_at": "DATETIME", "status": "VARCHAR(20) DEFAULT 'PLANNED'",
            "actual_minutes": "INTEGER", "strategy": "VARCHAR(20)", "executed": "BOOLEAN DEFAULT 0",
            "adaptation_reason": "TEXT", "is_conditional": "BOOLEAN DEFAULT 0",
            "decision_after": "BOOLEAN DEFAULT 0", "execution_order": "FLOAT",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
