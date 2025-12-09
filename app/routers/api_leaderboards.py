import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.db import get_db_connection
from app.security import get_current_user

router = APIRouter()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def assert_valid_username(username: str) -> None:
    if not USERNAME_RE.match(username or ""):
        raise HTTPException(status_code=400, detail="Invalid username")
    

@router.get("/api/leaderboard/reaction-game")
async def reaction_leaderboard_api(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Sign in required")

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

            scores = []
            for username, country_code, best_score, avg_time, last_played in rows:
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


@router.get("/api/leaderboard/memory-game")
async def memory_leaderboard_api(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Sign in required")

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

            scores = []
            for (
                username,
                country_code,
                best_total,
                best_r1,
                best_r2,
                best_r3,
                last_played,
            ) in rows:
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


@router.get("/api/my-best-scores")
async def my_best_scores(username: str):
    """
    Used on landing page to show a user's 'best ever' scores across games.
    """
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
                    COALESCE((SELECT MAX(score) FROM math_round1_scores WHERE user_id = %s), 0),
                    COALESCE((SELECT MAX(score) FROM math_round_mixed_scores WHERE user_id = %s), 0),
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
