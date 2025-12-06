from typing import Optional

import psycopg2
import psycopg2.extras

from app.security import assert_valid_username
from app.db import get_db_connection

ALLOWED_SEX = {"male", "female", "other", "prefer_not_to_say"}
ALLOWED_AGE_BANDS = {
    "18-20",
    "21-23",
    "24-26",
    "27-29",
    "30-32",
    "33-35",
    "36-38",
    "39-41",
    "42-44",
    "45+",
    "prefer_not_to_say",
}
ALLOWED_HANDEDNESS = {"left", "right", "ambidextrous"}


def normalize_profile_fields(
    sex: str | None,
    age_band: str | None,
    handedness: str | None,
    is_public: bool | str | None,
):
    sex_normalized = (sex or "prefer_not_to_say").strip()
    age_normalized = (age_band or "prefer_not_to_say").strip()
    handedness_normalized = (handedness or "ambidextrous").strip() if handedness else "ambidextrous"

    if sex_normalized not in ALLOWED_SEX:
        raise ValueError("Invalid sex value")
    if age_normalized not in ALLOWED_AGE_BANDS:
        raise ValueError("Invalid age band")
    if handedness_normalized not in ALLOWED_HANDEDNESS:
        raise ValueError("Invalid handedness")

    return (
        sex_normalized,
        age_normalized,
        handedness_normalized,
        bool(is_public) if isinstance(is_public, bool) else str(is_public or "").lower() in {"1", "true", "on"},
    )


def get_or_create_user(conn, username: str, country_code: str | None) -> int:
    assert_valid_username(username)
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, country_code FROM users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()
        if row:
            user_id, existing_country = row
            if country_code and country_code != existing_country:
                cursor.execute(
                    "UPDATE users SET country_code = %s WHERE id = %s",
                    (country_code, user_id),
                )
            return user_id

        created_country = country_code or "??"
        cursor.execute(
            "INSERT INTO users (username, country_code) VALUES (%s, %s) RETURNING id",
            (username, created_country),
        )
        return cursor.fetchone()[0]


def get_user_by_id(conn, user_id: int) -> Optional[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT id, username, country_code, password_hash FROM users WHERE id = %s",
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def resolve_user_id(conn, current_user: Optional[dict], username: Optional[str], country_code: str | None) -> int:
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


def fetch_recent_attempts(conn, user_id: int) -> list[dict]:
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
            FROM math_round1_scores
            WHERE user_id = %s
            UNION ALL
            SELECT 'arithmetic_r2' AS game, score AS score, created_at
            FROM math_round_mixed_scores
            WHERE user_id = %s AND (round_index = 2 OR round_index IS NULL)
            UNION ALL
            SELECT 'arithmetic_r3' AS game, score AS score, created_at
            FROM math_round_mixed_scores
            WHERE user_id = %s AND round_index = 3
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id, user_id, user_id, user_id, user_id),
        )
        rows = cursor.fetchall() or []
        return [dict(r) for r in rows]
