from typing import Any, Dict

import psycopg2
import psycopg2.extras

from .db import get_db_connection


def _fetchone(cursor) -> dict | None:
    row = cursor.fetchone()
    return dict(row) if row else None


def get_reaction_metrics(conn, user_id: int) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT
                AVG(average_time_ms) AS avg_reaction_ms,
                MIN(fastest_time_ms) AS best_reaction_ms,
                MAX(slowest_time_ms) AS worst_reaction_ms,
                AVG(accuracy) AS accuracy,
                MAX(score) AS best_score,
                AVG(score) AS mean_score
            FROM reaction_scores
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = _fetchone(cursor) or {}
    return {
        "avg_reaction_ms": row.get("avg_reaction_ms"),
        "best_reaction_ms": row.get("best_reaction_ms"),
        "worst_reaction_ms": row.get("worst_reaction_ms"),
        "accuracy": row.get("accuracy"),
        "best_score": row.get("best_score"),
        "mean_score": row.get("mean_score"),
    }


def get_memory_metrics(conn, user_id: int) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT
                MAX(total_score) AS best_total_score,
                AVG(total_score) AS avg_total_score,
                AVG(round1_score) AS avg_round1_score,
                AVG(round2_score) AS avg_round2_score,
                AVG(round3_score) AS avg_round3_score,
                COUNT(*) AS sessions
            FROM memory_scores
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = _fetchone(cursor) or {}
    return {
        "best_total_score": row.get("best_total_score"),
        "avg_total_score": row.get("avg_total_score"),
        "avg_round1_score": row.get("avg_round1_score"),
        "avg_round2_score": row.get("avg_round2_score"),
        "avg_round3_score": row.get("avg_round3_score"),
        "sessions": row.get("sessions", 0) or 0,
    }


def _math_accuracy(cursor, table: str, user_id: int, extra_where: str = "") -> tuple[float | None, int]:
    cursor.execute(
        f"""
        SELECT SUM(correct_count) AS correct, SUM(wrong_count) AS wrong, COUNT(*) AS rows
        FROM {table}
        WHERE user_id = %s {extra_where}
        """,
        (user_id,),
    )
    row = _fetchone(cursor) or {}
    correct = row.get("correct") or 0
    wrong = row.get("wrong") or 0
    total_rows = row.get("rows") or 0
    total = correct + wrong
    return ((correct / total) if total else None, total_rows)


def _math_qpm(avg_time_ms: float | None) -> float | None:
    if not avg_time_ms:
        return None
    if avg_time_ms <= 0:
        return None
    return 60000.0 / avg_time_ms


def get_math_metrics(conn, user_id: int) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            "SELECT MAX(score) AS best FROM yetamax_scores WHERE user_id = %s",
            (user_id,),
        )
        round1_best = (_fetchone(cursor) or {}).get("best")

        round1_accuracy, round1_rows = _math_accuracy(cursor, "yetamax_scores", user_id)
        cursor.execute(
            "SELECT AVG(avg_time_ms) AS avg_time_ms FROM yetamax_scores WHERE user_id = %s",
            (user_id,),
        )
        round1_qpm = _math_qpm((_fetchone(cursor) or {}).get("avg_time_ms"))

        cursor.execute(
            "SELECT MAX(score) AS best FROM maveric_scores WHERE user_id = %s AND (round_index = 2 OR round_index IS NULL)",
            (user_id,),
        )
        round2_best = (_fetchone(cursor) or {}).get("best")
        round2_accuracy, round2_rows = _math_accuracy(
            cursor, "maveric_scores", user_id, "AND (round_index = 2 OR round_index IS NULL)"
        )
        cursor.execute(
            "SELECT AVG(avg_time_ms) AS avg_time_ms FROM maveric_scores WHERE user_id = %s AND (round_index = 2 OR round_index IS NULL)",
            (user_id,),
        )
        round2_qpm = _math_qpm((_fetchone(cursor) or {}).get("avg_time_ms"))

        cursor.execute(
            "SELECT MAX(score) AS best FROM maveric_scores WHERE user_id = %s AND round_index = 3",
            (user_id,),
        )
        round3_best = (_fetchone(cursor) or {}).get("best")
        round3_accuracy, round3_rows = _math_accuracy(cursor, "maveric_scores", user_id, "AND round_index = 3")
        cursor.execute(
            "SELECT AVG(avg_time_ms) AS avg_time_ms FROM maveric_scores WHERE user_id = %s AND round_index = 3",
            (user_id,),
        )
        round3_qpm = _math_qpm((_fetchone(cursor) or {}).get("avg_time_ms"))

        # Aggregate for totals across all arithmetic rounds
        yetamax_rows = round1_rows
        _, maveric_rows = _math_accuracy(cursor, "maveric_scores", user_id)

        cursor.execute(
            "SELECT COALESCE(SUM(correct_count + wrong_count), 0) AS questions FROM yetamax_scores WHERE user_id = %s",
            (user_id,),
        )
        total_questions = (_fetchone(cursor) or {}).get("questions") or 0
        cursor.execute(
            "SELECT COALESCE(SUM(correct_count + wrong_count), 0) AS questions FROM maveric_scores WHERE user_id = %s",
            (user_id,),
        )
        total_questions += (_fetchone(cursor) or {}).get("questions") or 0
        cursor.execute(
            "SELECT COALESCE(SUM(correct_count + wrong_count), 0) AS questions FROM math_scores WHERE user_id = %s",
            (user_id,),
        )
        total_questions += (_fetchone(cursor) or {}).get("questions") or 0

        cursor.execute(
            "SELECT COUNT(*) AS rows, MAX(combined_score) AS best FROM math_session_scores WHERE user_id = %s",
            (user_id,),
        )
        session_row = _fetchone(cursor) or {"rows": 0, "best": None}

    return {
        "round1_best": round1_best,
        "round1_accuracy": round1_accuracy,
        "round1_qpm": round1_qpm,
        "round2_best": round2_best,
        "round2_accuracy": round2_accuracy,
        "round2_qpm": round2_qpm,
        "round3_best": round3_best,
        "round3_accuracy": round3_accuracy,
        "round3_qpm": round3_qpm,
        "total_questions": total_questions,
        "total_math_sessions": yetamax_rows + maveric_rows + (session_row.get("rows") or 0),
        "session_best_combined": session_row.get("best"),
    }


def get_global_metrics(conn, user_id: int) -> dict:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM (
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
            ) AS all_rows
            """,
            (user_id,) * 6,
        )
        total_rounds = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT DATE(created_at) FROM reaction_scores WHERE user_id = %s
                UNION
                SELECT DISTINCT DATE(created_at) FROM memory_scores WHERE user_id = %s
                UNION
                SELECT DISTINCT DATE(created_at) FROM yetamax_scores WHERE user_id = %s
                UNION
                SELECT DISTINCT DATE(created_at) FROM maveric_scores WHERE user_id = %s
                UNION
                SELECT DISTINCT DATE(created_at) FROM math_scores WHERE user_id = %s
                UNION
                SELECT DISTINCT DATE(created_at) FROM math_session_scores WHERE user_id = %s
            ) AS dates
            """,
            (user_id,) * 6,
        )
        sessions_played = cursor.fetchone()[0]

    avg_rounds_per_session = (total_rounds / sessions_played) if sessions_played else 0
    return {
        "sessions_played": sessions_played,
        "total_rounds": total_rounds,
        "avg_rounds_per_session": avg_rounds_per_session,
    }


def _clamp(value: float, min_v: float = 0, max_v: float = 100) -> int:
    return int(max(min_v, min(max_v, round(value))))


def _scale_inverse(value: float | None, best: float, worst: float) -> int:
    if value is None:
        return 0
    if value <= best:
        return 100
    if value >= worst:
        return 0
    ratio = (worst - value) / (worst - best)
    return _clamp(ratio * 100)


def _scale_linear(value: float | None, max_value: float) -> int:
    if value is None:
        return 0
    return _clamp((value / max_value) * 100)


def get_profile_metrics(conn, user_id: int) -> Dict[str, Any]:
    reaction = get_reaction_metrics(conn, user_id)
    memory = get_memory_metrics(conn, user_id)
    math_metrics = get_math_metrics(conn, user_id)
    global_metrics = get_global_metrics(conn, user_id)

    processing_speed = _scale_inverse(reaction.get("avg_reaction_ms"), best=200, worst=800)
    accuracy_score = _scale_linear(reaction.get("accuracy"), 1.0)
    working_memory = _scale_linear(memory.get("best_total_score"), 150.0)
    engagement = _clamp(
        (global_metrics.get("sessions_played", 0) * 5)
        + (global_metrics.get("avg_rounds_per_session", 0) * 10)
    )
    consistency = _scale_linear(math_metrics.get("total_math_sessions"), 50.0)

    radar = {
        "processing_speed": processing_speed,
        "accuracy": accuracy_score,
        "working_memory": working_memory,
        "consistency": consistency,
        "engagement": engagement,
    }

    return {
        "reaction": reaction,
        "memory": memory,
        "math": math_metrics,
        "global": global_metrics,
        "radar": radar,
    }


def get_profile_metrics_for_user(user_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        return get_profile_metrics(conn, user_id)
    finally:
        conn.close()
