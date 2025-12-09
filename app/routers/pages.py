from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import templates
from app.security import get_current_user, render_template

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, current_user=Depends(get_current_user)):
    return render_template(templates, "landing_page.html", request, {"current_user": current_user})


@router.get("/memory-game", response_class=HTMLResponse)
async def memory_game(request: Request, current_user=Depends(get_current_user)):
    return render_template(templates, "games/memory_game.html", request, {"current_user": current_user})


@router.get("/reaction-game", response_class=HTMLResponse)
async def reaction_game(request: Request, current_user=Depends(get_current_user)):
    return render_template(templates, "games/reaction_game.html", request, {"current_user": current_user})


@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template(templates, "leaderboards/leaderboard.html", request, {"current_user": current_user})


@router.get("/leaderboard/reaction-game", response_class=HTMLResponse)
async def reaction_game_leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template(templates, "leaderboards/reaction_leaderboard.html", request, {"current_user": current_user})


@router.get("/leaderboard/memory-game", response_class=HTMLResponse)
async def memory_game_leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template(templates, "leaderboards/memory_leaderboard.html", request, {"current_user": current_user})


@router.get("/leaderboard/math", response_class=HTMLResponse)
async def math_leaderboard_redirect(request: Request, current_user=Depends(get_current_user)):
    return render_template(templates, "round1/math_round1_leaderboard.html", request, {"current_user": current_user})


@router.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
