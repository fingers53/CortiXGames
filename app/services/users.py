from typing import Optional

import psycopg2
import psycopg2.extras

from app.security import assert_valid_username
from app.db import get_db_connection


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
        rows = cursor.fetchall() or []
        return [dict(r) for r in rows]
