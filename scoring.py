def calculate_reaction_game_score(data):
    """Calculate the score for the reaction game."""
    correct_clicks = data.get("correctClicks", 0)
    incorrect_clicks = data.get("incorrectClicks", 0)
    total_reaction_time = data.get("totalReactionTime", 0)
    slow_answers = data.get("slowAnswers", 0)
    fastest_time = data.get("fastestTime", 0)
    slowest_time = data.get("slowestTime", 0)

    average_time = total_reaction_time / correct_clicks if correct_clicks > 0 else 0
    speed_bonus = (correct_clicks - incorrect_clicks) * (1000 / average_time) if average_time > 0 else 0
    fastest_time_bonus = 300 / fastest_time if fastest_time < 300 else 0
    slowest_time_penalty = slowest_time / 500 if slowest_time > 500 else 0

    # Calculate streak penalty
    streak_penalty = calculate_streak_penalty(data.get("answerRecord", []))

    final_score = (correct_clicks - incorrect_clicks + speed_bonus + fastest_time_bonus - slowest_time_penalty - streak_penalty)
    accuracy = (correct_clicks / (correct_clicks + incorrect_clicks)) * 100 if (correct_clicks + incorrect_clicks) > 0 else 0

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
        "penaltyMessage": "Penalized for a streak of incorrect answers." if streak_penalty > 0 else "Great job! No penalty for consecutive incorrect answers."
    }

def calculate_streak_penalty(answer_record):
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

# Add similar functions for memory game scoring if needed 