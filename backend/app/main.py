from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import Settings
from app.core.time import utc_now
from app.db.database import create_database, initialize_database
from app.seed import seed_database


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, factory = create_database(configured.database_url)
        initialize_database(engine)
        with factory.begin() as db:
            seed_database(db)
        app.state.session_factory = factory
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="ATLAS — núcleo adaptativo", version="0.1.0-phase1", lifespan=lifespan)
    app.state.settings = configured
    app.state.clock = utc_now
    app.include_router(router)
    return app


app = create_app()
