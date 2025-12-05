import re
import secrets
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext

from .config import SESSION_COOKIE_NAME, SESSION_COOKIE_SECURE, SESSION_MAX_AGE_LONG, SESSION_MAX_AGE_SHORT
from .db import get_db_connection

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
csrf_sessions: dict[str, str] = {}


def assert_valid_username(username: str):
    if not USERNAME_RE.match(username or ""):
        raise HTTPException(status_code=400, detail="Invalid username")


def hash_password(password: str) -> str:
    print(f"DEBUG password={repr(password)} len={len(password)} bytes={len(password.encode('utf-8'))}")
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def ensure_session_tokens(request: Request):
    session_id = request.cookies.get("session_id")
    csrf_token = csrf_sessions.get(session_id)
    new_cookie = False

    if not session_id:
        session_id = secrets.token_urlsafe(16)
        new_cookie = True

    if csrf_token is None:
        csrf_token = secrets.token_urlsafe(32)
        csrf_sessions[session_id] = csrf_token

    return session_id, csrf_token, new_cookie


def csrf_protected(request: Request):
    session_id = request.cookies.get("session_id")
    csrf_header = request.headers.get("X-CSRF-Token")
    expected = csrf_sessions.get(session_id)
    if not session_id or expected is None or expected != csrf_header:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def set_session_cookie(response, user_id: int, remember: bool):
    max_age = SESSION_MAX_AGE_LONG if remember else SESSION_MAX_AGE_SHORT
    response.set_cookie(
        SESSION_COOKIE_NAME,
        str(user_id),
        httponly=True,
        max_age=max_age,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
    )


def clear_session_cookie(response):
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=SESSION_COOKIE_SECURE,
    )


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, username, country_code, password_hash, gender, age_range, handedness, is_public, created_at
                FROM users WHERE id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_current_user_from_request(request: Request) -> Optional[dict]:
    raw_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_id:
        return None

    try:
        user_id = int(raw_id)
    except ValueError:
        return None

    return get_user_by_id(user_id)


async def get_current_user(request: Request) -> Optional[dict]:
    return get_current_user_from_request(request)


def render_template(templates: Jinja2Templates, file_name: str, request: Request, context: Optional[dict] = None):
    session_id, csrf_token, new_cookie = ensure_session_tokens(request)
    base_context = {
        "request": request,
        "csrf_token": csrf_token,
    }
    if context:
        base_context.update(context)

    response = templates.TemplateResponse(file_name, base_context)
    if new_cookie:
        response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response
