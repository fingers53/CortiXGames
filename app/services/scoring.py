from typing import Dict, List, Optional


def calculate_memory_scores(question_log: List[Dict]) -> tuple[float, float, float, float]:
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

    r1 = round_scores[1]
    r2 = round_scores[2]
    r3 = round_scores[3]
    total = r1 + r2 + r3
    return total, r1, r2, r3


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


# Backwards-compatible alias
calculate_yetamax_score = calculate_arithmetic_score
