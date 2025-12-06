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
from app.services.users import normalize_profile_fields
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
    sex: str | None = Form(None),
    age_band: str | None = Form(None),
    handedness: str | None = Form(None),
    is_public: str | None = Form("1"),
):
    assert_valid_username(username)
    if not password or len(password) < 6:
        return render_landing_error(request, "Password must be at least 6 characters long.", username)

    try:
        sex_value, age_value, handed_value, is_public_value = normalize_profile_fields(
            sex, age_band, handedness, is_public
        )
    except ValueError as exc:
        return render_landing_error(request, str(exc), username)

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
                """
                INSERT INTO users (username, country_code, password_hash, sex, age_band, handedness, is_public)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (username, "??", password_hash, sex_value, age_value, handed_value, is_public_value),
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


