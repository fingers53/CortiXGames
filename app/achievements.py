from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

import psycopg2
import psycopg2.extras

from .db import get_db_connection

ACHIEVEMENTS_SEED: list[dict[str, str]] = [
    # Volume
    {"code": "PLAY_10_GAMES", "name": "Getting Started", "description": "Play 10 total rounds across any game.", "category": "Volume"},
    {"code": "PLAY_50_GAMES", "name": "On a Roll", "description": "Play 50 total rounds across any game.", "category": "Volume"},
    {"code": "PLAY_100_GAMES", "name": "Centurion", "description": "Play 100 total rounds across any game.", "category": "Volume"},
    {"code": "MATH_100_QS", "name": "Mathlete", "description": "Answer 100 math questions in total.", "category": "Volume"},
    {"code": "MATH_1000_QS", "name": "Number Cruncher", "description": "Answer 1000 math questions in total.", "category": "Volume"},
    # Skill
    {"code": "REACTION_SUB_300_MS", "name": "Quick Reflexes", "description": "Average reaction speed under 300ms.", "category": "Skill"},
    {"code": "REACTION_SUB_250_MS", "name": "Lightning Fast", "description": "Average reaction speed under 250ms.", "category": "Skill"},
    {"code": "REACTION_PERFECT_ROUND", "name": "Perfect Response", "description": "Near-perfect accuracy on a reaction round.", "category": "Skill"},
    {"code": "MEMORY_1K_TOTAL", "name": "Memory Master", "description": "Accumulate 1000 total memory points.", "category": "Skill"},
    {"code": "MATH_50_QPM", "name": "Mental Velocity", "description": "Average 50 questions per minute in maths.", "category": "Skill"},
    {"code": "MATH_PERFECT_ROUND", "name": "Flawless Maths", "description": "Finish a maths round without a mistake.", "category": "Skill"},
    # Consistency
    {"code": "STREAK_3_DAYS", "name": "Three Day Streak", "description": "Play on three consecutive days.", "category": "Consistency"},
    {"code": "STREAK_7_DAYS", "name": "Seven Day Streak", "description": "Play on seven consecutive days.", "category": "Consistency"},
    # Exploration
    {"code": "PLAYED_ALL_GAMES", "name": "Explorer", "description": "Try every game type at least once.", "category": "Exploration"},
    # Easter eggs
    {"code": "NIGHT_OWL", "name": "Night Owl", "description": "Play between 01:00 and 04:00 UTC.", "category": "Easter Egg"},
    {"code": "EARLY_BIRD", "name": "Early Bird", "description": "Play before 06:00 UTC.", "category": "Easter Egg"},
    {"code": "TILT_5_WRONG", "name": "Tilt-Proof", "description": "Keep going despite 5+ wrong maths answers.", "category": "Easter Egg"},
    {"code": "COMEBACK", "name": "Comeback Kid", "description": "Bounce back with a 20%+ improvement over your last maths session.", "category": "Easter Egg"},
]


def seed_achievements(conn=None) -> None:
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM achievements")
            if (cursor.fetchone() or {}).get("count"):
                return
            cursor.executemany(
                """
                INSERT INTO achievements (code, name, description, category)
                VALUES (%(code)s, %(name)s, %(description)s, %(category)s)
                ON CONFLICT (code) DO NOTHING
                """,
                ACHIEVEMENTS_SEED,
            )
        conn.commit()
    finally:
        if close_conn:
            conn.close()


def _award(cursor, user_id: int, code: str, achievement_map: Dict[str, int]):
    achievement_id = achievement_map.get(code)
    if not achievement_id:
        return
    cursor.execute(
        """
        INSERT INTO user_achievements (user_id, achievement_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, achievement_id) DO NOTHING
        """,
        (user_id, achievement_id),
    )


def _load_achievement_map(cursor) -> Dict[str, int]:
    cursor.execute("SELECT id, code FROM achievements")
    return {row[1]: row[0] for row in cursor.fetchall()}


def _total_rounds(cursor, user_id: int) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT id FROM reaction_scores WHERE user_id = %s
            UNION ALL
            SELECT id FROM memory_scores WHERE user_id = %s
            UNION ALL
            SELECT id FROM yetamax_scores WHERE user_id = %s
            UNION ALL
            SELECT id FROM maveric_scores WHERE user_id = %s
            UNION ALL
            SELECT id FROM math_scores WHERE user_id = %s
        ) AS rounds
        """,
        (user_id,) * 5,
    )
    return cursor.fetchone()[0]


def _math_question_total(cursor, user_id: int) -> int:
    cursor.execute(
        """
        SELECT COALESCE(SUM(total_questions), 0) FROM (
            SELECT COALESCE(SUM(correct_count + wrong_count), 0) AS total_questions FROM math_scores WHERE user_id = %s
            UNION ALL
            SELECT COALESCE(SUM(correct_count + wrong_count), 0) AS total_questions FROM yetamax_scores WHERE user_id = %s
            UNION ALL
            SELECT COALESCE(SUM(correct_count + wrong_count), 0) AS total_questions FROM maveric_scores WHERE user_id = %s
        ) AS totals
        """,
        (user_id, user_id, user_id),
    )
    return cursor.fetchone()[0] or 0


def _played_all_games(cursor, user_id: int) -> bool:
    cursor.execute(
        """
        SELECT
            EXISTS(SELECT 1 FROM reaction_scores WHERE user_id = %s) AS has_reaction,
            EXISTS(SELECT 1 FROM memory_scores WHERE user_id = %s) AS has_memory,
            EXISTS(SELECT 1 FROM yetamax_scores WHERE user_id = %s) AS has_yetamax,
            EXISTS(SELECT 1 FROM maveric_scores WHERE user_id = %s) AS has_maveric
        """,
        (user_id, user_id, user_id, user_id),
    )
    result = cursor.fetchone()
    return all(result) if result else False


def _streak_length(cursor, user_id: int) -> int:
    cursor.execute(
        """
        SELECT DISTINCT DATE(created_at) AS day
        FROM (
            SELECT created_at FROM reaction_scores WHERE user_id = %s
            UNION ALL
            SELECT created_at FROM memory_scores WHERE user_id = %s
            UNION ALL
            SELECT created_at FROM yetamax_scores WHERE user_id = %s
            UNION ALL
            SELECT created_at FROM maveric_scores WHERE user_id = %s
            UNION ALL
            SELECT created_at FROM math_scores WHERE user_id = %s
            UNION ALL
            SELECT created_at FROM math_session_scores WHERE user_id = %s
        ) t
        ORDER BY day DESC
        LIMIT 14
        """,
        (user_id,) * 6,
    )
    days = [row[0] for row in cursor.fetchall()]
    if not days:
        return 0
    streak = 1
    for idx in range(1, len(days)):
        if (days[idx - 1] - days[idx]) == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def check_and_award_achievements(conn, user_id: int, game_type: str, score_row: Dict[str, Any]):
    if conn.closed:
        raise RuntimeError("Connection must remain open for achievement checks")

    with conn.cursor() as cursor:
        achievement_map = _load_achievement_map(cursor)

        # Volume achievements
        total_rounds = _total_rounds(cursor, user_id)
        if total_rounds >= 10:
            _award(cursor, user_id, "PLAY_10_GAMES", achievement_map)
        if total_rounds >= 50:
            _award(cursor, user_id, "PLAY_50_GAMES", achievement_map)
        if total_rounds >= 100:
            _award(cursor, user_id, "PLAY_100_GAMES", achievement_map)

        # Maths totals
        total_qs = _math_question_total(cursor, user_id)
        if total_qs >= 100:
            _award(cursor, user_id, "MATH_100_QS", achievement_map)
        if total_qs >= 1000:
            _award(cursor, user_id, "MATH_1000_QS", achievement_map)

        # Skill checks
        if game_type == "reaction":
            avg_time = score_row.get("average_time_ms")
            accuracy = score_row.get("accuracy")
            if avg_time is not None:
                if avg_time < 300:
                    _award(cursor, user_id, "REACTION_SUB_300_MS", achievement_map)
                if avg_time < 250:
                    _award(cursor, user_id, "REACTION_SUB_250_MS", achievement_map)
            if accuracy is not None and accuracy >= 0.99:
                _award(cursor, user_id, "REACTION_PERFECT_ROUND", achievement_map)

        if game_type == "memory":
            if score_row.get("running_total") and score_row.get("running_total") >= 1000:
                _award(cursor, user_id, "MEMORY_1K_TOTAL", achievement_map)

        if game_type in {"math_round1", "math_round2", "math_round3", "math"}:
            avg_time_ms = score_row.get("avg_time_ms")
            wrong_count = score_row.get("wrong_count") or 0
            correct_count = score_row.get("correct_count") or 0
            if wrong_count == 0 and correct_count > 0:
                _award(cursor, user_id, "MATH_PERFECT_ROUND", achievement_map)
            if avg_time_ms and avg_time_ms > 0:
                qpm = 60000 / avg_time_ms
                if qpm >= 50:
                    _award(cursor, user_id, "MATH_50_QPM", achievement_map)
            if wrong_count >= 5 and (correct_count + wrong_count) > 0:
                _award(cursor, user_id, "TILT_5_WRONG", achievement_map)

        # Exploration
        if _played_all_games(cursor, user_id):
            _award(cursor, user_id, "PLAYED_ALL_GAMES", achievement_map)

        # Streaks
        streak = _streak_length(cursor, user_id)
        if streak >= 3:
            _award(cursor, user_id, "STREAK_3_DAYS", achievement_map)
        if streak >= 7:
            _award(cursor, user_id, "STREAK_7_DAYS", achievement_map)

        # Time-of-day easter eggs
        created_at = score_row.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None
        if created_at:
            hour = created_at.hour
            if 1 <= hour < 4:
                _award(cursor, user_id, "NIGHT_OWL", achievement_map)
            if hour < 6:
                _award(cursor, user_id, "EARLY_BIRD", achievement_map)

        # Comeback check: compare last two math sessions
        if game_type == "math_session":
            cursor.execute(
                """
                SELECT combined_score FROM math_session_scores
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 2
                """,
                (user_id,),
            )
            rows = [r[0] for r in cursor.fetchall()]
            if len(rows) == 2 and rows[0] and rows[1] and rows[0] > rows[1] * 1.2:
                _award(cursor, user_id, "COMEBACK", achievement_map)

    conn.commit()


def get_user_achievements(conn, user_id: int):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT a.code, a.name, a.description, a.category, ua.earned_at
            FROM achievements a
            JOIN user_achievements ua ON ua.achievement_id = a.id
            WHERE ua.user_id = %s
            ORDER BY ua.earned_at DESC
            """,
            (user_id,),
        )
        return cursor.fetchall()


def get_all_achievements(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT id, code, name, description, category FROM achievements ORDER BY category, id"
        )
        return cursor.fetchall()
