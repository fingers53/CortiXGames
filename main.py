import json
import math
import os
import re
import secrets
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from app.achievements import check_and_award_achievements, seed_achievements
from app.db import (
    ensure_achievements_tables,
    ensure_memory_score_payload_column,
    ensure_user_profile_columns,
)
from app.routers import profile as profile_router

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext

from scoring import calculate_reaction_game_score
from app.services.users import normalize_profile_fields

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_NAME = "session_user_id"
SESSION_COOKIE_NAME = "session_user_id"

# Short vs long sessions
SESSION_MAX_AGE_SHORT = 60 * 60 * 12          # 12 hours
SESSION_MAX_AGE_LONG = 60 * 60 * 24 * 30      # 30 days


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=["templates", "math-games/templates"])
app.mount(
    "/math-games/static",
    StaticFiles(directory="math-games/static"),
    name="math-games-static",
)


csrf_sessions: Dict[str, str] = {}
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    # Supabase wants SSL
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def ensure_yetamax_scores_table():
    conn = get_db_connection()
    new_id = None
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS yetamax_scores (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    score INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL,
                    wrong_count INTEGER NOT NULL,
                    avg_time_ms DOUBLE PRECISION NOT NULL,
                    min_time_ms DOUBLE PRECISION NOT NULL,
                    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
                    raw_payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_yetamax_scores_score_created_at
                ON yetamax_scores (score DESC, created_at ASC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_yetamax_scores_user_recent
                ON yetamax_scores (user_id, created_at DESC)
                """
            )

            # Optional migration from the older math_scores table to avoid data loss
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'math_scores'
                )
                """
            )
            old_table_exists = cursor.fetchone()[0]

            if old_table_exists:
                cursor.execute("SELECT COUNT(*) FROM yetamax_scores")
                new_count = cursor.fetchone()[0]
                if new_count == 0:
                    cursor.execute(
                        """
                        INSERT INTO yetamax_scores (
                            user_id, score, correct_count, wrong_count,
                            avg_time_ms, min_time_ms, is_valid, raw_payload, created_at
                        )
                        SELECT user_id, score, correct_count, wrong_count,
                               avg_time_ms, min_time_ms, is_valid, raw_payload, created_at
                        FROM math_scores
                        """
                    )
        conn.commit()
    finally:
        conn.close()


# Ensure Yetamax storage exists on startup
ensure_yetamax_scores_table()


def ensure_maveric_scores_table():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS maveric_scores (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    score INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL,
                    wrong_count INTEGER NOT NULL,
                    avg_time_ms DOUBLE PRECISION NOT NULL,
                    min_time_ms DOUBLE PRECISION NOT NULL,
                    total_questions INTEGER NOT NULL,
                    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
                    raw_payload JSONB,
                    round_index INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                ALTER TABLE public.maveric_scores
                    ADD COLUMN IF NOT EXISTS round_index INTEGER;
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_maveric_scores_score_created_at
                ON maveric_scores (score DESC, created_at ASC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_maveric_scores_user_recent
                ON maveric_scores (user_id, created_at DESC)
                """
            )
        conn.commit()
    finally:
        conn.close()


def ensure_math_session_scores_table():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS math_session_scores (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    round1_score_id INTEGER NOT NULL REFERENCES yetamax_scores(id),
                    round2_score_id INTEGER NOT NULL REFERENCES maveric_scores(id),
                    round3_score_id INTEGER REFERENCES maveric_scores(id),
                    combined_score INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                ALTER TABLE public.math_session_scores
                    ADD COLUMN IF NOT EXISTS round3_score_id INTEGER REFERENCES maveric_scores(id);
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_math_sessions_user_recent
                ON math_session_scores (user_id, created_at DESC)
                """
            )
        conn.commit()
    finally:
        conn.close()


# Ensure Round 2 and combined storage exist on startup
ensure_maveric_scores_table()
ensure_math_session_scores_table()
ensure_user_profile_columns()
ensure_memory_score_payload_column()
ensure_achievements_tables()
seed_achievements()
app.include_router(profile_router.router)


def read_html(file_name: str) -> str:
    with open(os.path.join("templates", file_name), "r", encoding="utf-8") as f:
        return f.read()



def assert_valid_username(username: str):
    if not USERNAME_RE.match(username or ""):
        raise HTTPException(status_code=400, detail="Invalid username")


def get_country_code_from_ip(client_ip: str | None) -> str:
    """
    Map IP -> ISO country code (e.g. 'IE', 'GB').
    We do NOT store the IP anywhere, just use it transiently.
    """
    if not client_ip:
        return "??"

    try:
        # Example using ipapi.co – swap if you prefer another service
        resp = requests.get(f"https://ipapi.co/{client_ip}/json/", timeout=1.5)
        if resp.status_code != 200:
            return "??"
        data = resp.json()
        code = data.get("country")  # 'IE', 'GB', 'ES', ...
        if code and len(code) == 2:
            return code
    except Exception:
        pass

    return "??"


def hash_password(password: str) -> str:
    # DEBUG
    print(f"DEBUG password={repr(password)} len={len(password)} bytes={len(password.encode('utf-8'))}")
    return pwd_context.hash(password)



def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def get_or_create_user(conn, username: str, country_code: str | None) -> int:
    """
    Find an existing user by username or create a new one.

    Uses the provided DB connection and does NOT commit; callers are
    responsible for committing after this call.
    """
    assert_valid_username(username)

    with conn.cursor() as cursor:
        # Try to find existing user
        cursor.execute(
            "SELECT id, country_code FROM users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()
        if row:
            user_id, existing_country = row
            # Update country_code if we learned something new
            if country_code and country_code != existing_country:
                cursor.execute(
                    "UPDATE users SET country_code = %s WHERE id = %s",
                    (country_code, user_id),
                )
            return user_id

        # No existing user → create one
        created_country = country_code or "??"
        cursor.execute(
            "INSERT INTO users (username, country_code) VALUES (%s, %s) RETURNING id",
            (username, created_country),
        )
        user_id = cursor.fetchone()[0]
        return user_id


def get_user_by_id(conn, user_id: int) -> Optional[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT
                id,
                username,
                country_code,
                password_hash,
                COALESCE(sex, gender) AS sex,
                COALESCE(age_band, age_range) AS age_band,
                CASE handedness WHEN 'ambi' THEN 'ambidextrous' ELSE handedness END AS handedness,
                is_public,
                created_at
            FROM users WHERE id = %s
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None




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


def get_current_user_from_request(request: Request) -> Optional[dict]:
    raw_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_id:
        return None

    try:
        user_id = int(raw_id)
    except ValueError:
        return None

    conn = get_db_connection()
    try:
        return get_user_by_id(conn, user_id)
    finally:
        conn.close()


async def get_current_user(request: Request) -> Optional[dict]:
    return get_current_user_from_request(request)


def render_template(
    file_name: str, request: Request, context: Optional[dict] = None
) -> HTMLResponse:
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


def csrf_protected(request: Request):
    session_id = request.cookies.get("session_id")
    csrf_header = request.headers.get("X-CSRF-Token")
    expected = csrf_sessions.get(session_id)
    if not session_id or expected is None or expected != csrf_header:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def validate_answer_record(answer_record: List[Dict]):
    if not isinstance(answer_record, list) or not (1 <= len(answer_record) <= 200):
        raise HTTPException(status_code=422, detail="Invalid answer record length")

    for item in answer_record:
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail="Answer record entries must be objects")
        reaction_time = item.get("reactionTime")
        if reaction_time is None or not (80 <= reaction_time <= 5000):
            raise HTTPException(status_code=422, detail="Reaction times must be between 80 and 5000 ms")
        if item.get("isCorrect") not in (True, False):
            raise HTTPException(status_code=422, detail="Each answer must include correctness")


def enforce_range(value: float, minimum: float, maximum: float, label: str):
    if value is None or not math.isfinite(value) or value < minimum or value > maximum:
        raise HTTPException(
            status_code=422,
            detail=f"{label} must be between {minimum} and {maximum}",
        )


def calculate_yetamax_score(
    correct_count: int, wrong_count: int, avg_time_ms: float, per_questions=None
) -> int:
    base_score = correct_count * 10
    penalty = wrong_count * 2

    streak_penalty = 0
    if per_questions:
        for entry in per_questions:
            wrong_attempts = int(entry.get("wrong_attempts") or 0)
            if wrong_attempts > 1:
                streak_penalty += wrong_attempts - 1

    return base_score - penalty - streak_penalty


def compute_memory_scores(question_log: List[Dict]) -> dict:
    """Compute per-round scores, partial credit, and timing insights.

    Scoring rule:
    +2 for correct on first attempt, +1 for correct with retries, -1 for incorrect.
    Partial credit is awarded for near misses (within 1–2 grid cells) based on the
    closest incorrect click. Timing metrics capture within-question pacing.
    """

    round_scores = {1: 0.0, 2: 0.0, 3: 0.0}
    near_miss_count = 0
    total_clicks = 0
    durations = []
    intervals = []

    for entry in question_log:
        round_num = int(entry.get("round", 0))
        if round_num not in round_scores:
            continue

        was_correct = bool(entry.get("wasCorrect", False))
        attempts = max(int(entry.get("attempts", 1) or 1), 1)
        targets = entry.get("targets") or entry.get("targetCells") or []
        clicks = entry.get("clicks") or []

        if not isinstance(targets, (list, tuple)):
            targets = []
        targets_list = list(targets)

        correct_cells = {(int(x), int(y)) for x, y in targets_list if isinstance(targets_list, list)}
        best_distance = None
        click_times = []

        for click in clicks:
            try:
                cx = int(click.get("x"))
                cy = int(click.get("y"))
            except (TypeError, ValueError):
                continue
            total_clicks += 1

            if correct_cells:
                distances = [abs(cx - tx) + abs(cy - ty) for tx, ty in correct_cells]
                min_dist = min(distances)
                best_distance = min(best_distance, min_dist) if best_distance is not None else min_dist
                if min_dist == 1:
                    near_miss_count += 1

            t_ms = click.get("tMs")
            if t_ms is None:
                t_ms = click.get("timeMs")
            if t_ms is not None:
                try:
                    click_times.append(float(t_ms))
                except (TypeError, ValueError):
                    pass

        base_score = 2.0 if was_correct and attempts == 1 else 1.0 if was_correct else -1.0
        partial_credit = 0.0
        if best_distance is not None and best_distance > 0:
            if best_distance <= 1:
                partial_credit = 0.5
            elif best_distance <= 2:
                partial_credit = 0.25

        round_scores[round_num] += base_score + partial_credit

        if click_times:
            click_times.sort()
            durations.append(click_times[-1] - click_times[0])
            intervals.extend([b - a for a, b in zip(click_times, click_times[1:])])

    r1 = round_scores[1]
    r2 = round_scores[2]
    r3 = round_scores[3]
    total = r1 + r2 + r3

    avg_duration_ms = sum(durations) / len(durations) if durations else 0.0
    avg_interval_ms = sum(intervals) / len(intervals) if intervals else 0.0

    return {
        "total": total,
        "round1": r1,
        "round2": r2,
        "round3": r3,
        "near_misses": near_miss_count,
        "guess_count": total_clicks,
        "avg_duration_ms": avg_duration_ms,
        "avg_interval_ms": avg_interval_ms,
    }


def resolve_user_id(
    conn, current_user: Optional[dict], username: Optional[str], country_code: str | None
) -> int:
    if current_user:
        user_id = current_user["id"]
        if country_code and country_code != current_user.get("country_code"):
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET country_code = %s WHERE id = %s",
                    (country_code, user_id),
                )
        return user_id

    assert_valid_username(username or "")
    return get_or_create_user(conn, username, country_code)


def fetch_recent_attempts(conn, user_id: int) -> List[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT 'reaction' AS game, score AS score, created_at
            FROM reaction_scores
            WHERE user_id = %s
            UNION ALL
            SELECT 'memory' AS game, total_score AS score, created_at
            FROM memory_scores
            WHERE user_id = %s
            UNION ALL
            SELECT 'arithmetic_r1' AS game, score AS score, created_at
            FROM yetamax_scores
            WHERE user_id = %s
            UNION ALL
            SELECT 'arithmetic_r2' AS game, score AS score, created_at
            FROM maveric_scores
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id, user_id, user_id, user_id),
        )
        return cursor.fetchall()


def fetch_reaction_insights(conn, user_id: int) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT score, average_time_ms, accuracy
            FROM reaction_scores
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 25
            """,
            (user_id,),
        )
        rows = cursor.fetchall()

    if not rows:
        return {
            "best_score": None,
            "average_time_ms": None,
            "accuracy": None,
            "cognitive_score": None,
            "strengths": ["Play a round to unlock insights."],
            "weaknesses": [],
        }

    scores = [r["score"] for r in rows]
    avg_time = sum(r["average_time_ms"] for r in rows) / len(rows)
    avg_accuracy = sum(r["accuracy"] for r in rows) / len(rows)
    best_score = max(scores)

    time_factor = max(0.25, min(1.0, 380.0 / max(avg_time, 1)))
    cognitive_score = int(round((avg_accuracy * 0.6 + time_factor * 0.4) * 100))

    strengths = []
    weaknesses = []
    if avg_accuracy >= 0.9:
        strengths.append("Precise clicking accuracy")
    elif avg_accuracy < 0.8:
        weaknesses.append("Accuracy drops on harder rounds")

    if avg_time <= 260:
        strengths.append("Lightning-fast reactions")
    elif avg_time > 420:
        weaknesses.append("Improve reaction speed under pressure")

    if not strengths:
        strengths.append("Steady performance across attempts")

    return {
        "best_score": best_score,
        "average_time_ms": round(avg_time, 1),
        "accuracy": round(avg_accuracy * 100, 1),
        "cognitive_score": cognitive_score,
        "strengths": strengths,
        "weaknesses": weaknesses,
    }


def fetch_memory_insights(conn, user_id: int) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT total_score, round1_score, round2_score, round3_score
            FROM memory_scores
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 25
            """,
            (user_id,),
        )
        rows = cursor.fetchall()

    if not rows:
        return {
            "best_total": None,
            "average_total": None,
            "round_averages": None,
            "cognitive_score": None,
            "strengths": ["Play a memory round to see insights."],
            "weaknesses": [],
        }

    totals = [r["total_score"] for r in rows]
    best_total = max(totals)
    avg_total = sum(totals) / len(totals)

    r1_avg = sum((r["round1_score"] or 0) for r in rows) / len(rows)
    r2_avg = sum((r["round2_score"] or 0) for r in rows) / len(rows)
    r3_avg = sum((r["round3_score"] or 0) for r in rows) / len(rows)
    round_avgs = {1: round(r1_avg, 2), 2: round(r2_avg, 2), 3: round(r3_avg, 2)}

    normalized_total = min(100.0, max(0.0, (avg_total / 30.0) * 100.0))
    peak_bonus = min(10.0, best_total)
    cognitive_score = int(round(normalized_total + peak_bonus))

    strengths = []
    weaknesses = []
    best_round = max(round_avgs, key=round_avgs.get)
    weakest_round = min(round_avgs, key=round_avgs.get)

    strengths.append(f"Strongest in round {best_round} patterns")
    if round_avgs[weakest_round] < round_avgs[best_round]:
        weaknesses.append(f"Round {weakest_round} needs more repetition")

    if avg_total >= best_total * 0.9:
        strengths.append("Consistent memory recall")
    elif avg_total < best_total * 0.6:
        weaknesses.append("Work on sustaining peak memory scores")

    return {
        "best_total": round(best_total, 2),
        "average_total": round(avg_total, 2),
        "round_averages": round_avgs,
        "cognitive_score": cognitive_score,
        "strengths": strengths,
        "weaknesses": weaknesses,
    }


def summarize_math_times(rows: list, question_key: str) -> tuple[dict, float]:
    type_totals: dict[str, float] = {}
    type_counts: dict[str, int] = {}
    overall_total = 0.0
    overall_count = 0

    for row in rows:
        payload = row.get("raw_payload") or {}
        questions = payload.get(question_key) or payload.get("per_question_times") or []
        for q in questions:
            if q.get("timed_out"):
                continue
            key = q.get("category") or q.get("operator")
            if not key:
                continue
            time_val = q.get("time_ms")
            if time_val is None:
                continue
            type_totals[key] = type_totals.get(key, 0) + float(time_val)
            type_counts[key] = type_counts.get(key, 0) + 1
            overall_total += float(time_val)
            overall_count += 1

    type_avgs = {
        key: (type_totals[key] / type_counts[key]) for key in type_totals if type_counts.get(key)
    }
    overall_avg = overall_total / overall_count if overall_count else None
    return type_avgs, overall_avg


def fetch_math_insights(conn, user_id: int) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT raw_payload, score FROM yetamax_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        )
        round1_rows = cursor.fetchall()

        cursor.execute(
            "SELECT raw_payload, score FROM maveric_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        )
        round2_rows = cursor.fetchall()

        cursor.execute(
            "SELECT MAX(score) FROM yetamax_scores WHERE user_id = %s",
            (user_id,),
        )
        best_r1 = cursor.fetchone()[0]

        cursor.execute(
            "SELECT MAX(score) FROM maveric_scores WHERE user_id = %s",
            (user_id,),
        )
        best_r2 = cursor.fetchone()[0]

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


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, current_user=Depends(get_current_user)):
    return render_template("landing_page.html", request, {"current_user": current_user})


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request, current_user=Depends(get_current_user)):
    return render_template("privacy.html", request, {"current_user": current_user})


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password(request: Request, current_user=Depends(get_current_user)):
    return render_template("forgot_password.html", request, {"current_user": current_user})


@app.get("/memory-game", response_class=HTMLResponse)
async def memory_game(request: Request, current_user=Depends(get_current_user)):
    return render_template("games/memory_game.html", request, {"current_user": current_user})


@app.get("/reaction-game", response_class=HTMLResponse)
async def reaction_game(request: Request, current_user=Depends(get_current_user)):
    return render_template("games/reaction_game.html", request, {"current_user": current_user})


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template("leaderboards/leaderboard.html", request, {"current_user": current_user})


@app.get("/leaderboard/reaction-game", response_class=HTMLResponse)
async def reaction_game_leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template("leaderboards/reaction_leaderboard.html", request, {"current_user": current_user})


@app.get("/leaderboard/memory-game", response_class=HTMLResponse)
async def memory_game_leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template("leaderboards/memory_leaderboard.html", request, {"current_user": current_user})


@app.get("/leaderboard/yetamax", response_class=HTMLResponse)
async def yetamax_leaderboard_redirect(request: Request, current_user=Depends(get_current_user)):
    return render_template("round1/yetamax_leaderboard.html", request, {"current_user": current_user})


@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)


def render_landing_error(request: Request, message: str, username: str):
    return render_template(
        "landing_page.html",
        request,
        {"error": message, "prefill_username": username, "current_user": None},
    )


def login_and_redirect(request: Request, user_id: int, remember: bool):
    session_id, _, new_cookie = ensure_session_tokens(request)
    response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    set_session_cookie(response, user_id, remember)
    if new_cookie:
        response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response



@app.post("/signup", response_class=HTMLResponse)
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
        return render_landing_error(
            request, "Password must be at least 6 characters long.", username
        )

    try:
        sex_value, age_value, handed_value, is_public_value = normalize_profile_fields(
            sex, age_band, handedness, is_public
        )
    except ValueError as exc:
        return render_landing_error(request, str(exc), username)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, password_hash FROM users WHERE username = %s", (username,)
            )
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



@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: str | None = Form(None),
):

    assert_valid_username(username)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id, password_hash FROM users WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()

        if not row:
            return render_landing_error(
                request,
                "No account found for that username. Enter a password on the landing page to create one.",
                username,
            )

        if not verify_password(password, row.get("password_hash")):
            return render_landing_error(
                request,
                "Incorrect password. Try again on the landing page.",
                username,
            )

        user_id = row["id"]
    finally:
        conn.close()

    remember = (remember_me == "1")
    return login_and_redirect(request, user_id, remember)



@app.get("/logout")
async def logout(request: Request):
    session_id, _, new_cookie = ensure_session_tokens(request)
    response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    clear_session_cookie(response)
    if new_cookie:
        response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


@app.post("/reaction-game/submit_score")
async def submit_reaction_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    score_data = data.get("scoreData") or {}
    answer_record = score_data.get("answerRecord") or []

    if not current_user and username:
        assert_valid_username(username)
    validate_answer_record(answer_record)

    score_result = calculate_reaction_game_score(answer_record)
    country_code = country_input or get_country_code_from_ip(request.client.host)
    final_score = score_result["finalScore"]
    average_time_ms = score_result["averageTime"]
    fastest_time_ms = score_result["fastestTime"]
    slowest_time_ms = score_result["slowestTime"]
    accuracy = score_result["accuracy"]

    enforce_range(final_score, -5000, 20000, "Final score")
    enforce_range(average_time_ms, 0, 5000, "Average time")
    enforce_range(fastest_time_ms, 50, 5000, "Fastest time")
    enforce_range(slowest_time_ms, 50, 5000, "Slowest time")
    enforce_range(accuracy, 0, 100, "Accuracy")

    if not current_user:
        return JSONResponse(
            content={
                "status": "success",
                "scoreResult": score_result,
                "message": "Login to save your reaction score",
            }
        )

    conn = get_db_connection()
    try:
        user_id = resolve_user_id(conn, current_user, username, country_code)
        created_at = datetime.utcnow().isoformat()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reaction_scores (
                    user_id, score, average_time_ms, fastest_time_ms,
                    slowest_time_ms, accuracy, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    user_id,
                    final_score,
                    average_time_ms,
                    fastest_time_ms,
                    slowest_time_ms,
                    accuracy,
                    created_at,
                ),
            )
            inserted = cursor.fetchone()
        check_and_award_achievements(
            conn,
            user_id,
            "reaction",
            {
                "average_time_ms": average_time_ms,
                "accuracy": accuracy,
                "created_at": inserted[1] if inserted else created_at,
            },
        )
        conn.commit()
    finally:
        conn.close()


    return JSONResponse(content={"status": "success", "scoreResult": score_result})


@app.post("/memory-game/submit_score")
async def submit_memory_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    question_log = data.get("questionLog") or []

    if not current_user and username:
        assert_valid_username(username)

    if not isinstance(question_log, list) or not (1 <= len(question_log) <= 200):
        raise HTTPException(status_code=422, detail="Invalid question log length")

    for entry in question_log:
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail="Question entries must be objects")
        round_num = entry.get("round")
        seq_len = entry.get("sequenceLength")
        attempts = entry.get("attempts")
        was_correct = entry.get("wasCorrect")
        targets = entry.get("targets") or entry.get("targetCells") or []
        clicks = entry.get("clicks") or []
        if round_num not in (1, 2, 3):
            raise HTTPException(status_code=422, detail="Round must be between 1 and 3")
        if seq_len is None or not (1 <= seq_len <= 25):
            raise HTTPException(status_code=422, detail="Sequence length out of bounds")
        if attempts is None or attempts < 1:
            raise HTTPException(status_code=422, detail="Attempts must be at least 1")
        if was_correct not in (True, False):
            raise HTTPException(status_code=422, detail="Each question must include correctness")
        if targets and not all(isinstance(t, (list, tuple)) and len(t) >= 2 for t in targets):
            raise HTTPException(status_code=422, detail="Targets must be coordinates")
        if clicks and not all(isinstance(c, dict) for c in clicks):
            raise HTTPException(status_code=422, detail="Clicks must be objects")

    score_result = compute_memory_scores(question_log)
    total_score = max(0, score_result["total"])
    r1 = max(0, score_result["round1"])
    r2 = max(0, score_result["round2"])
    r3 = max(0, score_result["round3"])
    country_code = country_input or get_country_code_from_ip(request.client.host)

    enforce_range(total_score, 0, 200000, "Total score")
    enforce_range(r1, 0, 80000, "Round 1 score")
    enforce_range(r2, 0, 80000, "Round 2 score")
    enforce_range(r3, 0, 80000, "Round 3 score")

    response_payload = {
        "status": "success",
        "finalScore": total_score,
        "round1Score": r1,
        "round2Score": r2,
        "round3Score": r3,
        "nearMisses": score_result["near_misses"],
        "guessCount": score_result["guess_count"],
        "avgDurationMs": score_result["avg_duration_ms"],
        "avgIntervalMs": score_result["avg_interval_ms"],
    }

    if not current_user:
        response_payload["message"] = "Login to save your memory score"
        return JSONResponse(content=response_payload)

    conn = get_db_connection()
    try:
        user_id = resolve_user_id(conn, current_user, username, country_code)
        created_at = datetime.utcnow().isoformat()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO memory_scores (
                    user_id, total_score, round1_score, round2_score, round3_score, raw_payload, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    user_id,
                    total_score,
                    r1,
                    r2,
                    r3,
                    json.dumps(
                        {
                            "near_misses": score_result["near_misses"],
                            "guess_count": score_result["guess_count"],
                            "avg_duration_ms": score_result["avg_duration_ms"],
                            "avg_interval_ms": score_result["avg_interval_ms"],
                        }
                    ),
                    created_at,
                ),
            )
            inserted = cursor.fetchone()
            cursor.execute(
                "SELECT COALESCE(SUM(total_score), 0) FROM memory_scores WHERE user_id = %s",
                (user_id,),
            )
            running_total = cursor.fetchone()[0] or 0
        check_and_award_achievements(
            conn,
            user_id,
            "memory",
            {
                "total_score": total_score,
                "running_total": running_total,
                "created_at": inserted[1] if inserted else created_at,
            },
        )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content=response_payload)


@app.get("/api/leaderboard/reaction-game")
async def reaction_leaderboard_api():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    u.username,
                    u.country_code,
                    MAX(r.score) AS best_score,
                    AVG(r.average_time_ms) AS avg_time,
                    MAX(r.created_at) AS last_played
                FROM reaction_scores r
                JOIN users u ON u.id = r.user_id
                GROUP BY u.username, u.country_code
                ORDER BY best_score DESC
                """
            )
            rows = cursor.fetchall()

            # Convert to list-of-lists, same order as before:
            # [username, country_code, best_score, avg_time, last_played]
            scores = []
            for row in rows:
                username, country_code, best_score, avg_time, last_played = row
                scores.append([
                    username,
                    country_code,
                    float(best_score) if best_score is not None else None,
                    float(avg_time) if avg_time is not None else None,
                    last_played.isoformat() if last_played else None,
                ])

            cursor.execute("SELECT MAX(created_at) FROM reaction_scores")
            last_updated_row = cursor.fetchone()
            last_updated = (
                last_updated_row[0].date().isoformat()
                if last_updated_row and last_updated_row[0]
                else None
            )

        return JSONResponse(content={"scores": scores, "last_updated": last_updated})
    finally:
        conn.close()

@app.get("/api/leaderboard/memory-game")
async def memory_leaderboard_api():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    u.username,
                    u.country_code,
                    MAX(m.total_score) AS best_total,
                    MAX(m.round1_score) AS best_r1,
                    MAX(m.round2_score) AS best_r2,
                    MAX(m.round3_score) AS best_r3,
                    MAX(m.created_at) AS last_played
                FROM memory_scores m
                JOIN users u ON u.id = m.user_id
                GROUP BY u.username, u.country_code
                ORDER BY best_total DESC
                """
            )
            rows = cursor.fetchall()

            # Again: list-of-lists, in the exact order your old JS expects:
            # [username, country_code, best_total, best_r1, best_r2, best_r3, last_played]
            scores = []
            for row in rows:
                (
                    username,
                    country_code,
                    best_total,
                    best_r1,
                    best_r2,
                    best_r3,
                    last_played,
                ) = row
                scores.append([
                    username,
                    country_code,
                    float(best_total) if best_total is not None else None,
                    float(best_r1) if best_r1 is not None else None,
                    float(best_r2) if best_r2 is not None else None,
                    float(best_r3) if best_r3 is not None else None,
                    last_played.isoformat() if last_played else None,
                ])

            cursor.execute("SELECT MAX(created_at) FROM memory_scores")
            last_updated_row = cursor.fetchone()
            last_updated = (
                last_updated_row[0].date().isoformat()
                if last_updated_row and last_updated_row[0]
                else None
            )

        return JSONResponse(content={"scores": scores, "last_updated": last_updated})
    finally:
        conn.close()


@app.get("/math-game", response_class=HTMLResponse)
@app.get("/math-game/yetamax", response_class=HTMLResponse)
async def yetamax_game(request: Request, current_user=Depends(get_current_user)):
    return render_template(
        "round1/math_game_yetamax.html",
        request,
        {
            "current_user": current_user,
        },
    )


@app.get("/math-game/leaderboard", response_class=HTMLResponse)
@app.get("/math-game/yetamax/leaderboard", response_class=HTMLResponse)
async def yetamax_leaderboard_page(
    request: Request, current_user=Depends(get_current_user)
):
    return render_template(
        "round1/yetamax_leaderboard.html",
        request,
        {
            "current_user": current_user,
        },
    )


@app.get("/math-game/stats", response_class=HTMLResponse)
@app.get("/math-game/yetamax/stats", response_class=HTMLResponse)
async def yetamax_stats_page(request: Request, current_user=Depends(get_current_user)):
    return render_template(
        "round1/yetamax_stats.html",
        request,
        {
            "current_user": current_user,
        },
    )


@app.get("/math-game/maveric/leaderboard", response_class=HTMLResponse)
async def maveric_leaderboard_page(
    request: Request, current_user=Depends(get_current_user)
):
    return render_template(
        "round2/maveric_leaderboard.html",
        request,
        {
            "current_user": current_user,
        },
    )


@app.post("/api/math-game/yetamax/submit")
async def submit_yetamax_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    data = await request.json()
    correct_count = int(data.get("correct_count") or 0)
    wrong_count = int(data.get("wrong_count") or 0)
    avg_time_ms = float(data.get("avg_time_ms") or 0)
    min_time_ms = float(data.get("min_time_ms") or 0)
    per_question_times = data.get("per_question_times") or []
    avg_time_by_operator = data.get("avg_time_by_operator") or {}

    if correct_count < 0 or wrong_count < 0:
        raise HTTPException(status_code=422, detail="Counts must be non-negative")
    if correct_count > 200 or wrong_count > 200:
        raise HTTPException(status_code=422, detail="Counts too large")
    if len(per_question_times) > 400:
        raise HTTPException(status_code=422, detail="Too many timing entries")

    is_valid = not (min_time_ms < 150)
    enforce_range(avg_time_ms, 0, 10000, "Average time")
    enforce_range(min_time_ms, 50, 5000, "Minimum time")

    score_value = calculate_yetamax_score(
        correct_count, wrong_count, avg_time_ms, per_question_times
    )

    enforce_range(score_value, -2000, 50000, "Score")

    raw_payload = data.copy()
    raw_payload.update({"score": score_value, "is_valid": is_valid})

    response_payload = {
        "status": "success",
        "score": score_value,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "avg_time_ms": avg_time_ms,
        "min_time_ms": min_time_ms,
        "is_valid": is_valid,
        "avg_time_by_operator": avg_time_by_operator,
        "per_question_times": per_question_times,
    }

    if not current_user:
        response_payload["yetamax_score_id"] = None
        response_payload["message"] = "Login to save your Round 1 score"
        return JSONResponse(content=response_payload)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO yetamax_scores (
                    user_id, score, correct_count, wrong_count,
                    avg_time_ms, min_time_ms, is_valid, raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    current_user["id"],
                    score_value,
                    correct_count,
                    wrong_count,
                    avg_time_ms,
                    min_time_ms,
                    is_valid,
                    psycopg2.extras.Json(raw_payload),
                ),
            )
            inserted = cursor.fetchone()
            new_id = inserted[0]
        check_and_award_achievements(
            conn,
            current_user["id"],
            "math_round1",
            {
                "avg_time_ms": avg_time_ms,
                "wrong_count": wrong_count,
                "correct_count": correct_count,
                "created_at": inserted[1] if inserted else None,
            },
        )
        conn.commit()
    finally:
        conn.close()

    response_payload["yetamax_score_id"] = new_id
    return JSONResponse(content=response_payload)


async def _submit_maveric_score(
    request: Request,
    current_user,
    round_index: int,
):
    data = await request.json()
    correct_count = int(data.get("correct_count") or 0)
    wrong_count = int(data.get("wrong_count") or 0)
    avg_time_ms = float(data.get("avg_time_ms") or 0)
    min_time_ms = float(data.get("min_time_ms") or 0)
    total_questions = int(data.get("total_questions") or 0)
    per_question = data.get("per_question") or []

    if correct_count < 0 or wrong_count < 0:
        raise HTTPException(status_code=422, detail="Counts must be non-negative")
    if correct_count > 200 or wrong_count > 200 or total_questions > 300:
        raise HTTPException(status_code=422, detail="Counts too large")
    if (correct_count + wrong_count) and total_questions and total_questions != (correct_count + wrong_count):
        raise HTTPException(status_code=422, detail="Total questions mismatch")
    if len(per_question) > 400:
        raise HTTPException(status_code=422, detail="Too many per-question entries")

    is_valid = not (min_time_ms < 150)
    enforce_range(avg_time_ms, 0, 10000, "Average time")
    enforce_range(min_time_ms, 50, 5000, "Minimum time")

    score_value = calculate_yetamax_score(
        correct_count, wrong_count, avg_time_ms, per_question
    )

    enforce_range(score_value, -2000, 50000, "Score")

    raw_payload = data.copy()
    raw_payload.update({"score": score_value, "is_valid": is_valid, "round_index": round_index})

    score_key = "round2_score" if round_index == 2 else "round3_score"
    response_payload = {
        "status": "success",
        score_key: score_value,
        "is_valid": is_valid,
        "per_question": per_question,
    }

    if not current_user:
        response_payload["maveric_score_id"] = None
        response_payload["message"] = "Login to save your Round %d score" % round_index
        return response_payload

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO maveric_scores (
                    user_id, score, correct_count, wrong_count,
                    avg_time_ms, min_time_ms, total_questions, is_valid, raw_payload, round_index, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id, created_at
                """,
                (
                    current_user["id"],
                    score_value,
                    correct_count,
                    wrong_count,
                    avg_time_ms,
                    min_time_ms,
                    total_questions,
                    is_valid,
                    psycopg2.extras.Json(raw_payload),
                    round_index,
                ),
            )
            inserted = cursor.fetchone()
            new_id = inserted[0]
        check_and_award_achievements(
            conn,
            current_user["id"],
            "math_round2" if round_index == 2 else "math_round3",
            {
                "avg_time_ms": avg_time_ms,
                "wrong_count": wrong_count,
                "correct_count": correct_count,
                "created_at": inserted[1] if inserted else None,
            },
        )
        conn.commit()
    finally:
        conn.close()

    response_payload["maveric_score_id"] = new_id
    return response_payload


@app.post("/api/math-game/yetamax/round2/submit")
async def submit_maveric_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    response = await _submit_maveric_score(request, current_user, 2)
    return JSONResponse(content=response)


@app.post("/api/math-game/yetamax/round3/submit")
async def submit_maveric_score_round3(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    response = await _submit_maveric_score(request, current_user, 3)
    return JSONResponse(content=response)


@app.post("/api/math-game/yetamax/session/submit")
async def submit_math_session(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    data = await request.json()
    round1_score_id = int(data.get("round1_score_id") or 0)
    round2_score_id = int(data.get("round2_score_id") or 0)
    round3_score_id = int(data.get("round3_score_id") or 0)
    combined_score = int(data.get("combined_score") or 0)

    if not (round1_score_id and round2_score_id and round3_score_id):
        raise HTTPException(status_code=400, detail="Round IDs required")
    if combined_score < 0 or combined_score > 200000:
        raise HTTPException(status_code=422, detail="Combined score out of range")

    if not current_user:
        return JSONResponse(
            content={
                "status": "success",
                "message": "Login to save your math session",
                "combined_score": combined_score,
            }
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO math_session_scores (
                    user_id, round1_score_id, round2_score_id, round3_score_id, combined_score
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    current_user["id"],
                    round1_score_id,
                    round2_score_id,
                    round3_score_id or None,
                    combined_score,
                ),
            )
            inserted = cursor.fetchone()
            new_id = inserted[0]
        check_and_award_achievements(
            conn,
            current_user["id"],
            "math_session",
            {"combined_score": combined_score, "created_at": inserted[1] if inserted else None},
        )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content={"status": "success", "session_id": new_id})


@app.get("/api/math-game/yetamax/leaderboard")
async def yetamax_leaderboard_api():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    u.username,
                    s.score,
                    s.correct_count,
                    s.wrong_count,
                    s.avg_time_ms,
                    s.created_at
                FROM yetamax_scores s
                JOIN users u ON u.id = s.user_id
                WHERE s.is_valid = TRUE
                ORDER BY s.score DESC, s.created_at ASC
                LIMIT 20
                """
            )
            rows = cursor.fetchall()
        scores = []
        for row in rows:
            scores.append(
                {
                    "username": row["username"],
                    "score": int(row["score"]),
                    "correct_count": int(row["correct_count"]),
                    "wrong_count": int(row["wrong_count"]),
                    "avg_time_ms": float(row["avg_time_ms"]),
                    "created_at": row["created_at"].isoformat(),
                }
            )
        return JSONResponse(content={"scores": scores})
    finally:
        conn.close()


@app.get("/api/math-game/maveric/leaderboard")
async def maveric_leaderboard_api(request: Request):
    round_index_param = request.query_params.get("round_index")
    round_index = None
    try:
        round_index = int(round_index_param) if round_index_param else None
    except ValueError:
        round_index = None

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    u.username,
                    s.score,
                    s.correct_count,
                    s.wrong_count,
                    s.avg_time_ms,
                    s.created_at
                FROM maveric_scores s
                JOIN users u ON u.id = s.user_id
                WHERE s.is_valid = TRUE
                  AND (%s IS NULL OR s.round_index = %s OR (s.round_index IS NULL AND %s = 2))
                ORDER BY s.score DESC, s.created_at ASC
                LIMIT 20
                """,
                (round_index, round_index, round_index),
            )
            rows = cursor.fetchall()
        scores = []
        for row in rows:
            scores.append(
                {
                    "username": row["username"],
                    "score": int(row["score"]),
                    "correct_count": int(row["correct_count"]),
                    "wrong_count": int(row["wrong_count"]),
                    "avg_time_ms": float(row["avg_time_ms"]),
                    "created_at": row["created_at"].isoformat(),
                }
            )
        return JSONResponse(content={"scores": scores})
    finally:
        conn.close()


@app.get("/api/math-game/yetamax/score-distribution")
async def yetamax_score_distribution():
    bucket_width = 20
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT FLOOR(score::numeric / %s) AS bucket, COUNT(*)
                FROM yetamax_scores
                WHERE is_valid = TRUE
                GROUP BY bucket
                ORDER BY bucket
                """,
                (bucket_width,),
            )
            rows = cursor.fetchall()
        buckets = []
        for bucket, count in rows:
            min_val = int(bucket) * bucket_width
            max_val = min_val + bucket_width - 1
            buckets.append({"min": min_val, "max": max_val, "count": count})
        return JSONResponse(content={"buckets": buckets})
    finally:
        conn.close()


@app.get("/api/math-game/yetamax/difficulty-summary")
async def yetamax_difficulty_summary():
    return JSONResponse(content={"hardest_questions": [], "easiest_questions": []})


@app.get("/api/my-best-scores")
async def my_best_scores(username: str):
    assert_valid_username(username)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cursor.fetchone()
            if not row:
                return {
                    "username": username,
                    "reaction_best": None,
                    "memory_best": None,
                    "arithmetic_best": None,
                }

            user_id = row[0]

            cursor.execute(
                "SELECT MAX(score) FROM reaction_scores WHERE user_id = %s",
                (user_id,),
            )
            reaction_best = cursor.fetchone()[0]

            cursor.execute(
                "SELECT MAX(total_score) FROM memory_scores WHERE user_id = %s",
                (user_id,),
            )
            memory_best = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT GREATEST(
                    COALESCE((SELECT MAX(score) FROM yetamax_scores WHERE user_id = %s), 0),
                    COALESCE((SELECT MAX(score) FROM maveric_scores WHERE user_id = %s), 0),
                    COALESCE((SELECT MAX(score) FROM math_scores WHERE user_id = %s), 0),
                    COALESCE((SELECT MAX(combined_score) FROM math_session_scores WHERE user_id = %s), 0)
                )
                """,
                (user_id, user_id, user_id, user_id),
            )
            arithmetic_best = cursor.fetchone()[0]

        return {
            "username": username,
            "reaction_best": reaction_best,
            "memory_best": memory_best,
            "arithmetic_best": arithmetic_best if arithmetic_best != 0 else None,
        }
    finally:
        conn.close()

