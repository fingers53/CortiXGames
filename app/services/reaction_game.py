from fastapi import HTTPException
from typing import Dict, List

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

from typing import Dict, List


def calculate_reaction_game_score(answer_record: List[Dict]):
    """Calculate the reaction game score strictly from the validated answer log."""

    correct_clicks = sum(1 for answer in answer_record if answer.get("isCorrect"))
    total_questions = len(answer_record)
    incorrect_clicks = total_questions - correct_clicks

    reaction_times = [answer.get("reactionTime", 0) for answer in answer_record]
    total_reaction_time = sum(reaction_times)
    fastest_time = min(reaction_times) if reaction_times else 0
    slowest_time = max(reaction_times) if reaction_times else 0

    average_time = total_reaction_time / correct_clicks if correct_clicks > 0 else 0
    speed_bonus = (correct_clicks - incorrect_clicks) * (1000 / average_time) if average_time > 0 else 0
    fastest_time_bonus = 300 / fastest_time if fastest_time and fastest_time < 300 else 0
    slowest_time_penalty = slowest_time / 500 if slowest_time > 500 else 0

    streak_penalty = calculate_streak_penalty(answer_record)

    final_score = correct_clicks - incorrect_clicks + speed_bonus + fastest_time_bonus - slowest_time_penalty - streak_penalty
    accuracy = (correct_clicks / total_questions) * 100 if total_questions > 0 else 0

    return {
        "finalScore": round(final_score, 2),
        "averageTime": round(average_time, 2),
        "accuracy": round(accuracy, 2),
        "speedBonus": round(speed_bonus, 2),
        "fastestTimeBonus": round(fastest_time_bonus, 2),
        "slowestTimePenalty": round(slowest_time_penalty, 2),
        "streakPenalty": round(streak_penalty, 2),
        "fastestTime": round(fastest_time, 2),
        "slowestTime": round(slowest_time, 2),
        "penaltyMessage": "Penalized for a streak of incorrect answers." if streak_penalty > 0 else "Great job! No penalty for consecutive incorrect answers.",
    }


def calculate_streak_penalty(answer_record: List[Dict]):
    """Calculate penalty based on streaks of incorrect answers."""
    max_streak = 0
    current_streak = 0

    for answer in answer_record:
        if not answer.get("isCorrect", False):
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return max_streak if max_streak > 1 else 0
