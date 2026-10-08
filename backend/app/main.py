from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.bootstrap import bootstrap_content
from app.core.config import Settings
from app.core.time import utc_now
from app.db.database import create_database, initialize_database


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, factory = create_database(configured.database_url)
        try:
            initialize_database(engine)
            with factory.begin() as db:
                bootstrap_content(db, configured.content_mode)
            app.state.session_factory = factory
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="ATLAS — núcleo adaptativo", version="0.1.0-phase1", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(configured.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.state.settings = configured
    app.state.clock = utc_now
    app.include_router(router)
    return app


app = create_app()
