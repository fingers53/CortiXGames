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
