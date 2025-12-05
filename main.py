import os
import re
import secrets
from datetime import datetime
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext

from scoring import calculate_reaction_game_score

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
templates = Jinja2Templates(directory=["templates", "math-games/yetamax/templates"])
app.mount(
    "/math-games/yetamax/static",
    StaticFiles(directory="math-games/yetamax/static"),
    name="yetamax-static",
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
            "SELECT id, username, country_code, password_hash FROM users WHERE id = %s",
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


def calculate_yetamax_score(correct_count: int, wrong_count: int, avg_time_ms: float) -> int:
    speed_bonus = 0
    if avg_time_ms > 0:
        speed_bonus = max(0, int(3000 / avg_time_ms))
    base_score = correct_count * 10
    penalty = wrong_count * 2
    return base_score - penalty + speed_bonus

    r1 = round_scores[1]
    r2 = round_scores[2]
    r3 = round_scores[3]
    total = r1 + r2 + r3
    return total, r1, r2, r3


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
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id, user_id),
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


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, current_user=Depends(get_current_user)):
    return render_template("landing_page.html", request, {"current_user": current_user})


@app.get("/memory-game", response_class=HTMLResponse)
async def memory_game(request: Request, current_user=Depends(get_current_user)):
    return render_template("memory_game.html", request, {"current_user": current_user})


@app.get("/reaction-game", response_class=HTMLResponse)
async def reaction_game(request: Request, current_user=Depends(get_current_user)):
    return render_template("reaction_game.html", request, {"current_user": current_user})


@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template("leaderboard.html", request, {"current_user": current_user})


@app.get("/leaderboard/reaction-game", response_class=HTMLResponse)
async def reaction_game_leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template("reaction_leaderboard.html", request, {"current_user": current_user})


@app.get("/leaderboard/memory-game", response_class=HTMLResponse)
async def memory_game_leaderboard(request: Request, current_user=Depends(get_current_user)):
    return render_template("memory_leaderboard.html", request, {"current_user": current_user})


@app.get("/leaderboard/yetamax", response_class=HTMLResponse)
async def yetamax_leaderboard_redirect(request: Request, current_user=Depends(get_current_user)):
    return render_template("yetamax_leaderboard.html", request, {"current_user": current_user})


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
):

    assert_valid_username(username)
    if not password or len(password) < 6:
        return render_landing_error(
            request, "Password must be at least 6 characters long.", username
        )

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
                "INSERT INTO users (username, country_code, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, "??", password_hash),
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


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    conn = get_db_connection()
    try:
        attempts = fetch_recent_attempts(conn, current_user["id"])
        reaction_insights = fetch_reaction_insights(conn, current_user["id"])
        memory_insights = fetch_memory_insights(conn, current_user["id"])
    finally:
        conn.close()

    return render_template(
        "profile.html",
        request,
        {
            "current_user": current_user,
            "attempts": attempts,
            "reaction_insights": reaction_insights,
            "memory_insights": memory_insights,
        },
    )


@app.post("/profile/flag", response_class=HTMLResponse)
async def update_flag(
    request: Request,
    country_code: str = Form(...),
    current_user=Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    code = (country_code or "").strip().upper()
    if not re.match(r"^[A-Z]{2}$", code):
        conn = get_db_connection()
        try:
            attempts = fetch_recent_attempts(conn, current_user["id"])
            reaction_insights = fetch_reaction_insights(conn, current_user["id"])
            memory_insights = fetch_memory_insights(conn, current_user["id"])
        finally:
            conn.close()
        return render_template(
            "profile.html",
            request,
            {
                "current_user": current_user,
                "attempts": attempts,
                "reaction_insights": reaction_insights,
                "memory_insights": memory_insights,
                "error": "Please provide a two-letter country code (e.g., US, GB).",
            },
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET country_code = %s WHERE id = %s",
                (code, current_user["id"]),
            )
        conn.commit()
        attempts = fetch_recent_attempts(conn, current_user["id"])
        reaction_insights = fetch_reaction_insights(conn, current_user["id"])
        memory_insights = fetch_memory_insights(conn, current_user["id"])
    finally:
        conn.close()

    updated_user = dict(current_user)
    updated_user["country_code"] = code
    return render_template(
        "profile.html",
        request,
        {
            "current_user": updated_user,
            "attempts": attempts,
            "reaction_insights": reaction_insights,
            "memory_insights": memory_insights,
            "message": "Flag updated for your account.",
        },
    )


@app.post("/reaction-game/submit_score")
async def submit_reaction_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    score_data = data.get("scoreData") or {}
    answer_record = score_data.get("answerRecord") or []

    if not current_user:
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
        user_id = resolve_user_id(conn, current_user, username, country_code)
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
async def submit_memory_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    question_log = data.get("questionLog") or []

    if not current_user:
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
        user_id = resolve_user_id(conn, current_user, username, country_code)
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


@app.get("/math-game/yetamax", response_class=HTMLResponse)
async def yetamax_game(request: Request, current_user=Depends(get_current_user)):
    if not current_user:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    return render_template(
        "math_game_yetamax.html",
        request,
        {
            "current_user": current_user,
        },
    )


@app.get("/math-game/yetamax/leaderboard", response_class=HTMLResponse)
async def yetamax_leaderboard_page(
    request: Request, current_user=Depends(get_current_user)
):
    return render_template(
        "yetamax_leaderboard.html",
        request,
        {
            "current_user": current_user,
        },
    )


@app.get("/math-game/yetamax/stats", response_class=HTMLResponse)
async def yetamax_stats_page(request: Request, current_user=Depends(get_current_user)):
    return render_template(
        "yetamax_stats.html",
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

    is_valid = not (min_time_ms < 150)
    score_value = calculate_yetamax_score(correct_count, wrong_count, avg_time_ms)

    raw_payload = data.copy()
    raw_payload.update({"score": score_value, "is_valid": is_valid})

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO yetamax_scores (
                    user_id, score, correct_count, wrong_count,
                    avg_time_ms, min_time_ms, is_valid, raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(
        content={
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
    )


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

