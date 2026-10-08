"""Production startup checks schema version without mutating tables."""

from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine


def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))


def require_current_schema(engine: Engine) -> None:
    head = ScriptDirectory.from_config(migration_config()).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    if current != head:
        raise RuntimeError("Schema desatualizado: execute alembic upgrade head antes de iniciar o backend")
