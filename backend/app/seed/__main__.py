from sqlalchemy import func, select

from app.bootstrap import bootstrap_content
from app.core.config import Settings
from app.db.database import create_database, initialize_database
from app.models import Concept, Exercise


def main() -> None:
    settings = Settings.from_env()
    if settings.content_mode != "provisional":
        raise SystemExit("O seed provisório só pode ser executado com ATLAS_CONTENT_MODE=provisional")
    engine, factory = create_database(settings.database_url)
    try:
        initialize_database(engine)
        with factory.begin() as db:
            bootstrap_content(db, "provisional")
            print(f"Seed OK: {db.scalar(select(func.count()).select_from(Concept))} conceitos; "
                  f"{db.scalar(select(func.count()).select_from(Exercise))} exercícios.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
