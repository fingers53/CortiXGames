import os
import re
import secrets
from datetime import datetime
from typing import Dict, List

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from scoring import calculate_reaction_game_score

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


csrf_sessions: Dict[str, str] = {}
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    # Supabase wants SSL
    return psycopg2.connect(DATABASE_URL, sslmode="require")


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


def render_template(file_name: str, request: Request) -> HTMLResponse:
    session_id, csrf_token, new_cookie = ensure_session_tokens(request)
    content = read_html(file_name).replace("{{ csrf_token }}", csrf_token)
    response = HTMLResponse(content=content)
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


def compute_memory_scores(question_log: List[Dict]) -> tuple[float, float, float, float]:
    """Compute per-round scores and a total for the memory game.

    Scoring rule:
    +2 for correct on first attempt, +1 for correct with retries, -1 for incorrect.
    Scores can go negative.
    """

    round_scores = {1: 0.0, 2: 0.0, 3: 0.0}
    for entry in question_log:
        round_num = int(entry.get("round", 0))
        if round_num not in round_scores:
            continue
        was_correct = bool(entry.get("wasCorrect", False))
        attempts = int(entry.get("attempts", 1))
        if was_correct:
            round_scores[round_num] += 2.0 if attempts == 1 else 1.0
        else:
            round_scores[round_num] -= 1.0

    r1 = round_scores[1]
    r2 = round_scores[2]
    r3 = round_scores[3]
    total = r1 + r2 + r3
    return total, r1, r2, r3


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return render_template("landing_page.html", request)


@app.get("/memory-game", response_class=HTMLResponse)
async def memory_game(request: Request):
    return render_template("memory_game.html", request)


@app.get("/reaction-game", response_class=HTMLResponse)
async def reaction_game(request: Request):
    return render_template("reaction_game.html", request)


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(request: Request):
    return render_template("leaderboard.html", request)


@app.get("/leaderboard/reaction-game", response_class=HTMLResponse)
async def reaction_game_leaderboard(request: Request):
    return render_template("reaction_leaderboard.html", request)


@app.get("/leaderboard/memory-game", response_class=HTMLResponse)
async def memory_game_leaderboard(request: Request):
    return render_template("memory_leaderboard.html", request)


@app.post("/reaction-game/submit_score")
async def submit_reaction_score(request: Request, _=Depends(csrf_protected)):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    score_data = data.get("scoreData") or {}
    answer_record = score_data.get("answerRecord") or []

    assert_valid_username(username)
    validate_answer_record(answer_record)

    score_result = calculate_reaction_game_score(answer_record)
    country_code = country_input or get_country_code_from_ip(request.client.host)
    final_score = score_result["finalScore"]
    average_time_ms = score_result["averageTime"]
    fastest_time_ms = score_result["fastestTime"]
    slowest_time_ms = score_result["slowestTime"]
    accuracy = score_result["accuracy"]

    conn = get_db_connection()
    try:
        user_id = get_or_create_user(conn, username, country_code)
        created_at = datetime.utcnow().isoformat()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reaction_scores (
                    user_id, score, average_time_ms, fastest_time_ms,
                    slowest_time_ms, accuracy, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
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
        conn.commit()
    finally:
        conn.close()


    return JSONResponse(content={"status": "success", "scoreResult": score_result})


@app.post("/memory-game/submit_score")
async def submit_memory_score(request: Request, _=Depends(csrf_protected)):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    question_log = data.get("questionLog") or []

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
        if round_num not in (1, 2, 3):
            raise HTTPException(status_code=422, detail="Round must be between 1 and 3")
        if seq_len is None or not (1 <= seq_len <= 25):
            raise HTTPException(status_code=422, detail="Sequence length out of bounds")
        if attempts is None or attempts < 1:
            raise HTTPException(status_code=422, detail="Attempts must be at least 1")
        if was_correct not in (True, False):
            raise HTTPException(status_code=422, detail="Each question must include correctness")

    total_score, r1, r2, r3 = compute_memory_scores(question_log)
    country_code = country_input or get_country_code_from_ip(request.client.host)

    conn = get_db_connection()
    try:
        user_id = get_or_create_user(conn, username, country_code)
        created_at = datetime.utcnow().isoformat()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO memory_scores (
                    user_id, total_score, round1_score, round2_score, round3_score, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, total_score, r1, r2, r3, created_at),
            )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(
        content={
            "status": "success",
            "finalScore": total_score,
            "round1Score": r1,
            "round2Score": r2,
            "round3Score": r3,
        }
    )


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


@app.get("/api/my-best-scores")
async def my_best_scores(username: str):
    assert_valid_username(username)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cursor.fetchone()
            if not row:
                return {"username": username, "reaction_best": None, "memory_best": None}

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

        return {
            "username": username,
            "reaction_best": reaction_best,
            "memory_best": memory_best,
        }
    finally:
        conn.close()

