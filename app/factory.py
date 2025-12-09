from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import STATIC_DIR
from .achievements import seed_achievements
from .db import (
    init_db_schema
)
from .dependencies import templates
from .routers import (
    auth,
    pages,
    profile,
    api_leaderboards,
    reaction,
    memory,
    maths_game,
)

def create_app() -> FastAPI:
    app = FastAPI()

    # Static + templates (whatever you already had)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Run DB + achievements init on startup
    @app.on_event("startup")
    def startup() -> None:
        init_db_schema()
        seed_achievements()

    # Include routers
    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(reaction.router)
    app.include_router(memory.router)
    app.include_router(maths_game.router)
    app.include_router(api_leaderboards.router)

    return app