from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import MATH_STATIC_DIR, STATIC_DIR
from .db import ensure_math_session_scores_table, ensure_maveric_scores_table, ensure_yetamax_scores_table
from .dependencies import templates
from .routers import api_scores, auth, math_routes, pages


def create_app() -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/math-games/static", StaticFiles(directory=str(MATH_STATIC_DIR)), name="math-games-static")

    ensure_yetamax_scores_table()
    ensure_maveric_scores_table()
    ensure_math_session_scores_table()

    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(api_scores.router)
    app.include_router(math_routes.router)

    return app
