from typing import Dict, List, Optional
import psycopg2.extras

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
            "SELECT raw_payload, score FROM math_round1_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        )
        round1_rows = cursor.fetchall()

        cursor.execute(
            "SELECT raw_payload, score FROM math_round_mixed_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        )
        round2_rows = cursor.fetchall()

        cursor.execute(
            "SELECT MAX(score) FROM math_round1_scores WHERE user_id = %s",
            (user_id,),
        )
        best_r1 = cursor.fetchone()[0]

        cursor.execute(
            "SELECT MAX(score) FROM math_round_mixed_scores WHERE user_id = %s",
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

def _streak_penalty_from_questions(per_questions: Optional[List[Dict]]) -> int:
    if not per_questions:
        return 0
    penalty = 0
    for question in per_questions:
        wrong_attempts = int(question.get("wrong_attempts") or 0)
        if wrong_attempts > 1:
            penalty += wrong_attempts - 1
    return penalty


def calculate_arithmetic_score(correct_count: int, wrong_count: int, per_questions: Optional[List[Dict]] = None) -> int:
    base_score = correct_count * 10
    penalty = wrong_count * 2
    penalty += _streak_penalty_from_questions(per_questions)
    return base_score - penalty
