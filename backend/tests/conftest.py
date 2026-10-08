from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.db.database import create_database, initialize_database
from app.seed import seed_database


@pytest.fixture
def now():
    return datetime(2026, 10, 11, 22, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):
    engine, factory = create_database(f"sqlite:///{tmp_path / 'test.db'}")
    initialize_database(engine)
    with factory() as session:
        seed_database(session)
        session.commit()
        yield session
        session.rollback()
    engine.dispose()


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}", timezone="America/Sao_Paulo")
