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
from app.services.users import normalize_profile_fields

router = APIRouter()


def _get_user_by_username(conn, username: str):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT id, username, country_code, COALESCE(sex, gender) AS sex, COALESCE(age_band, age_range) AS age_band, CASE handedness WHEN 'ambi' THEN 'ambidextrous' ELSE handedness END AS handedness, is_public, created_at
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
                SELECT id, username, country_code, COALESCE(sex, gender) AS sex, COALESCE(age_band, age_range) AS age_band, CASE handedness WHEN 'ambi' THEN 'ambidextrous' ELSE handedness END AS handedness, is_public, created_at
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
    sex: str = Form(None),
    age_band: str = Form(None),
    handedness: str = Form(None),
    is_public: bool = Form(False),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        sex_value, age_value, handed_value, is_public_value = normalize_profile_fields(
            sex, age_band, handedness, is_public
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET country_code = %s, sex = %s, age_band = %s, handedness = %s, is_public = %s
                WHERE id = %s
                """,
                (
                    (country_code or "??").upper(),
                    sex_value,
                    age_value,
                    handed_value,
                    is_public_value,
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
