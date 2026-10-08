from sqlalchemy import func, select

from app.core.config import Settings
from app.db.database import create_database, initialize_database
from app.models import Concept, Exercise
from app.seed import seed_database


def main() -> None:
    engine, factory = create_database(Settings.from_env().database_url)
    initialize_database(engine)
    with factory.begin() as db:
        seed_database(db)
        print(f"Seed OK: {db.scalar(select(func.count()).select_from(Concept))} conceitos; "
              f"{db.scalar(select(func.count()).select_from(Exercise))} exercícios.")
    engine.dispose()


if __name__ == "__main__":
    main()
