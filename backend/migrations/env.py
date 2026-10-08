"""Alembic uses the same URL and driver resolution as the application."""

from alembic import context

from app.core.config import Settings
from app.db.database import create_database
from app.models import Base


if context.is_offline_mode():
    raise RuntimeError("A baseline verifica bancos existentes; execute migrations online")

engine, _ = create_database(Settings.from_env().database_url)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata,
                          compare_type=True, render_as_batch=engine.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
