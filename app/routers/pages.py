from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import get_templates
from app.security import get_current_user, render_template

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def landing_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    return render_template(
        templates,
        "landing_page.html",
        request,
        {"current_user": current_user},
    )


@router.get("/memory-game", response_class=HTMLResponse)
async def memory_game_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    return render_template(
        templates,
        "memory/memory_game.html",
        request,
        {"current_user": current_user},
    )


@router.get("/reaction-game", response_class=HTMLResponse)
async def reaction_game_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    return render_template(
        templates,
        "reaction/reaction_game.html",
        request,
        {"current_user": current_user},
    )


@router.get("/math-game", response_class=HTMLResponse)
async def maths_game_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    # This is the main timed maths game page
    return render_template(
        templates,
        "maths/round1/math_rounds_game.html",
        request,
        {"current_user": current_user},
    )


@router.get("/math-game/stats", response_class=HTMLResponse)
async def maths_stats_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    # Per-user maths stats page
    if not current_user:
        return RedirectResponse("/", status_code=302)

    return render_template(
        templates,
        "maths/round1/math_round1_stats.html",
        request,
        {"current_user": current_user},
    )


@router.get("/math-game/leaderboard", response_class=HTMLResponse)
async def maths_leaderboard_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    # Main maths leaderboard; linked from /leaderboard
    if not current_user:
        return RedirectResponse("/", status_code=302)

    return render_template(
        templates,
        "leaderboards/math_round1_leaderboard.html",
        request,
        {"current_user": current_user},
    )


@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_hub(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    if not current_user:
        return RedirectResponse("/", status_code=302)

    return render_template(
        templates,
        "leaderboards/leaderboard.html",
        request,
        {"current_user": current_user},
    )


@router.get("/leaderboard/reaction-game", response_class=HTMLResponse)
async def reaction_leaderboard_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    if not current_user:
        return RedirectResponse("/", status_code=302)

    return render_template(
        templates,
        "leaderboards/reaction_leaderboard.html",
        request,
        {"current_user": current_user},
    )


@router.get("/leaderboard/memory-game", response_class=HTMLResponse)
async def memory_leaderboard_page(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    if not current_user:
        return RedirectResponse("/", status_code=302)

    return render_template(
        templates,
        "leaderboards/memory_leaderboard.html",
        request,
        {"current_user": current_user},
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(
    request: Request,
    current_user=Depends(get_current_user),
    templates=Depends(get_templates),
):
    # NOTE: correct signature: render_template(templates, file_name, request, ctx)
    return render_template(
        templates,
        "privacy.html",
        request,
        {"current_user": current_user},
    )


# Convenience redirects – keep old URLs working if they exist in templates/JS

@router.get("/login", response_class=HTMLResponse)
async def login_redirect():
    return RedirectResponse("/", status_code=302)


@router.get("/signup", response_class=HTMLResponse)
async def signup_redirect():
    return RedirectResponse("/", status_code=302)
