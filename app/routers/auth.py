import requests
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import templates
from app.security import (
    assert_valid_username,
    clear_session_cookie,
    get_current_user,
    hash_password,
    render_template,
    set_session_cookie,
    verify_password,
)
from app.services.users import fetch_recent_attempts, get_or_create_user
from app.db import get_db_connection

router = APIRouter()


def get_country_code_from_ip(client_ip: str | None) -> str:
    if not client_ip:
        return "??"

    try:
        resp = requests.get(f"https://ipapi.co/{client_ip}/json/", timeout=1.5)
        if resp.status_code != 200:
            return "??"
        data = resp.json()
        code = data.get("country")
        if code and len(code) == 2:
            return code
    except Exception:
        pass

    return "??"


def render_landing_error(request: Request, message: str, username: str):
    return render_template(
        templates,
        "landing_page.html",
        request,
        {"error": message, "prefill_username": username, "current_user": None},
    )


def login_and_redirect(request: Request, user_id: int, remember: bool):
    response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    set_session_cookie(response, user_id, remember)
    return response


@router.post("/signup", response_class=HTMLResponse)
async def signup(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: str | None = Form(None),
):
    assert_valid_username(username)
    if not password or len(password) < 6:
        return render_landing_error(request, "Password must be at least 6 characters long.", username)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
            row = cursor.fetchone()

            if row:
                existing_id, password_hash = row
                if password_hash and verify_password(password, password_hash):
                    remember = (remember_me == "1")
                    return login_and_redirect(request, existing_id, remember)
                return render_landing_error(
                    request,
                    "Username already has a password. Enter the correct password to sign in.",
                    username,
                )

            password_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, country_code, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, "??", password_hash),
            )
            user_id = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    remember = (remember_me == "1")
    return login_and_redirect(request, user_id, remember)


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: str | None = Form(None),
):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, password_hash FROM users WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                conn.commit()
                return render_landing_error(request, "Incorrect username or password.", username)

            user_id, password_hash = row
            if not password_hash or not verify_password(password, password_hash):
                conn.commit()
                return render_landing_error(request, "Incorrect username or password.", username)

        conn.commit()
    finally:
        conn.close()

    remember = (remember_me == "1")
    return login_and_redirect(request, user_id, remember)


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    clear_session_cookie(response)
    return response


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    conn = get_db_connection()
    recent_attempts = []
    insights = {}
    try:
        recent_attempts = fetch_recent_attempts(conn, current_user["id"])
        insights = get_arithmetic_insights(conn, current_user["id"])
    finally:
        conn.close()

    return render_template(
        templates,
        "profile.html",
        request,
        {
            "current_user": current_user,
            "recent_attempts": recent_attempts,
            "arithmetic_insights": insights,
        },
    )


@router.post("/profile/flag", response_class=HTMLResponse)
async def update_country_code(
    request: Request,
    current_user=Depends(get_current_user),
    country: str = Form(None),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    country_code = country.upper() if country else "??"
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET country_code = %s WHERE id = %s",
                (country_code, current_user["id"]),
            )
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse("/profile", status_code=status.HTTP_303_SEE_OTHER)


def get_arithmetic_insights(conn, user_id: int) -> dict:
    round1_rows = []
    round2_rows = []
    best_r1 = None
    best_r2 = None
    with conn.cursor(cursor_factory=None) as cursor:
        cursor.execute(
            "SELECT raw_payload, score FROM yetamax_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 200",
            (user_id,),
        )
        round1_rows = cursor.fetchall()
        cursor.execute("SELECT MAX(score) FROM yetamax_scores WHERE user_id = %s", (user_id,))
        best_r1 = cursor.fetchone()[0]
        cursor.execute(
            "SELECT raw_payload, score FROM maveric_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 200",
            (user_id,),
        )
        round2_rows = cursor.fetchall()
        cursor.execute("SELECT MAX(score) FROM maveric_scores WHERE user_id = %s", (user_id,))
        best_r2 = cursor.fetchone()[0]

    def summarize_math_times(rows, key_name: str):
        averages = {}
        total = 0
        count = 0
        for payload, _score in rows:
            if not payload:
                continue
            per_q = payload.get(key_name) or []
            for entry in per_q:
                q_type = entry.get("category") or entry.get("operator") or entry.get("qtype")
                if q_type is None:
                    continue
                time_ms = entry.get("time_ms")
                if time_ms is None:
                    continue
                averages[q_type] = averages.get(q_type, 0) + time_ms
                total += time_ms
                count += 1
        return averages, (total / count) if count else None

    r1_avgs, r1_overall = summarize_math_times(round1_rows, "per_question_times")
    r2_avgs, r2_overall = summarize_math_times(round2_rows, "per_question")

    def map_rows(avg_map):
        return [
            {"type": key, "avg_time_s": round(val / 1000, 2)}
            for key, val in sorted(avg_map.items(), key=lambda kv: kv[0])
        ]

    return {
        "round1": {
            "best_score": best_r1,
            "overall_avg": round(r1_overall / 1000, 2) if r1_overall else None,
            "averages": map_rows(r1_avgs),
        },
        "round2": {
            "best_score": best_r2,
            "overall_avg": round(r2_overall / 1000, 2) if r2_overall else None,
            "averages": map_rows(r2_avgs),
        },
    }
