from __future__ import annotations

from typing import Any

import psycopg2.extras
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.achievements import get_all_achievements, get_user_achievements
from app.analytics import get_profile_metrics
from app.db import get_db_connection
from app.dependencies import templates
from app.security import get_current_user, render_template

router = APIRouter()


def _get_user_by_username(conn, username: str):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT id, username, country_code, gender, age_range, handedness, is_public, created_at
            FROM users
            WHERE username = %s
            """,
            (username,),
        )
        return cursor.fetchone()


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, username, country_code, gender, age_range, handedness, is_public, created_at
                FROM users WHERE id = %s
                """,
                (current_user["id"],),
            )
            profile_user = cursor.fetchone()
        metrics = get_profile_metrics(conn, current_user["id"])
        user_achievements = get_user_achievements(conn, current_user["id"])
        all_achievements = get_all_achievements(conn)
    finally:
        conn.close()

    return render_template(
        templates,
        "profile.html",
        request,
        {
            "current_user": current_user,
            "profile_user": profile_user,
            "metrics": metrics,
            "user_achievements": user_achievements,
            "all_achievements": all_achievements,
            "is_owner": True,
        },
    )


@router.post("/profile", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    current_user=Depends(get_current_user),
    country_code: str = Form(None),
    gender: str = Form(None),
    age_range: str = Form(None),
    handedness: str = Form(None),
    is_public: bool = Form(False),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET country_code = %s, gender = %s, age_range = %s, handedness = %s, is_public = %s
                WHERE id = %s
                """,
                (
                    (country_code or "??").upper(),
                    gender,
                    age_range,
                    handedness,
                    bool(is_public),
                    current_user["id"],
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse("/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/profile/{username}", response_class=HTMLResponse)
async def public_profile(request: Request, username: str, current_user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        profile_user = _get_user_by_username(conn, username)
        if not profile_user:
            raise HTTPException(status_code=404, detail="User not found")
        if not profile_user.get("is_public") and not (current_user and current_user.get("id") == profile_user.get("id")):
            raise HTTPException(status_code=404, detail="Profile is private")

        metrics = get_profile_metrics(conn, profile_user["id"])
        user_achievements = get_user_achievements(conn, profile_user["id"])
        all_achievements = get_all_achievements(conn)
    finally:
        conn.close()

    return render_template(
        templates,
        "profile.html",
        request,
        {
            "current_user": current_user,
            "profile_user": profile_user,
            "metrics": metrics,
            "user_achievements": user_achievements,
            "all_achievements": all_achievements,
            "is_owner": current_user and current_user.get("id") == profile_user.get("id"),
        },
    )


@router.get("/api/profile/{username}/metrics", response_class=JSONResponse)
async def profile_metrics_api(username: str, current_user=Depends(get_current_user)):
    conn = get_db_connection()
    try:
        profile_user = _get_user_by_username(conn, username)
        if not profile_user:
            raise HTTPException(status_code=404, detail="User not found")
        if not profile_user.get("is_public") and not (current_user and current_user.get("id") == profile_user.get("id")):
            raise HTTPException(status_code=404, detail="Profile is private")

        metrics = get_profile_metrics(conn, profile_user["id"])
        earned = get_user_achievements(conn, profile_user["id"])
        all_achievements = get_all_achievements(conn)
        earned_codes = {a["code"] for a in earned}
        locked = [a for a in all_achievements if a["code"] not in earned_codes]
    finally:
        conn.close()

    return JSONResponse(
        content=jsonable_encoder(
            {
                "metrics": metrics,
                "achievements": {"earned": earned, "locked": locked},
            }
        )
    )
