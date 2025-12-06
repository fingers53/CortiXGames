from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import MATH_STATIC_DIR, STATIC_DIR
from .achievements import seed_achievements
from .db import (
    ensure_achievements_tables,
    ensure_math_session_scores_table,
    ensure_math_round_mixed_scores_table,
    ensure_memory_score_payload_column,
    ensure_user_profile_columns,
    ensure_math_round1_scores_table,
)
from .dependencies import templates
from .routers import api_scores, auth, math_routes, pages, profile


def create_app() -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/math-games/static", StaticFiles(directory=str(MATH_STATIC_DIR)), name="math-games-static")

    ensure_user_profile_columns()
    ensure_math_round1_scores_table()
    ensure_math_round_mixed_scores_table()
    ensure_math_session_scores_table()
    ensure_memory_score_payload_column()
    ensure_achievements_tables()
    seed_achievements()

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(api_scores.router)
    app.include_router(math_routes.router)
    app.include_router(profile.router)

    return app
