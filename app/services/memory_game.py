
#FIXME

from typing import Dict, List

def compute_memory_scores(question_log: List[Dict]) -> dict:
    """Compute per-round scores, partial credit, and timing insights.

    Scoring rule:
    +2 for correct on first attempt, +1 for correct with retries, -1 for incorrect.
    Partial credit is awarded for near misses (within 1-2 grid cells) based on the
    closest incorrect click. Timing metrics capture within-question pacing.
    """

    round_scores = {1: 0.0, 2: 0.0, 3: 0.0}
    near_miss_count = 0
    total_clicks = 0
    durations = []
    intervals = []

    for entry in question_log:
        round_num = int(entry.get("round", 0))
        if round_num not in round_scores:
            continue

        was_correct = bool(entry.get("wasCorrect", False))
        attempts = max(int(entry.get("attempts", 1) or 1), 1)
        targets = entry.get("targets") or entry.get("targetCells") or []
        clicks = entry.get("clicks") or []

        if not isinstance(targets, (list, tuple)):
            targets = []
        targets_list = list(targets)

        correct_cells = {(int(x), int(y)) for x, y in targets_list if isinstance(targets_list, list)}
        best_distance = None
        click_times = []

        for click in clicks:
            try:
                cx = int(click.get("x"))
                cy = int(click.get("y"))
            except (TypeError, ValueError):
                continue
            total_clicks += 1

            if correct_cells:
                distances = [abs(cx - tx) + abs(cy - ty) for tx, ty in correct_cells]
                min_dist = min(distances)
                best_distance = min(best_distance, min_dist) if best_distance is not None else min_dist
                if min_dist == 1:
                    near_miss_count += 1

            t_ms = click.get("tMs")
            if t_ms is None:
                t_ms = click.get("timeMs")
            if t_ms is not None:
                try:
                    click_times.append(float(t_ms))
                except (TypeError, ValueError):
                    pass

        base_score = 2.0 if was_correct and attempts == 1 else 1.0 if was_correct else -1.0
        partial_credit = 0.0
        if best_distance is not None and best_distance > 0:
            if best_distance <= 1:
                partial_credit = 0.5
            elif best_distance <= 2:
                partial_credit = 0.25

        round_scores[round_num] += base_score + partial_credit

        if click_times:
            click_times.sort()
            durations.append(click_times[-1] - click_times[0])
            intervals.extend([b - a for a, b in zip(click_times, click_times[1:])])

    r1 = round_scores[1]
    r2 = round_scores[2]
    r3 = round_scores[3]
    total = r1 + r2 + r3

    avg_duration_ms = sum(durations) / len(durations) if durations else 0.0
    avg_interval_ms = sum(intervals) / len(intervals) if intervals else 0.0

    return {
        "total": total,
        "round1": r1,
        "round2": r2,
        "round3": r3,
        "near_misses": near_miss_count,
        "guess_count": total_clicks,
        "avg_duration_ms": avg_duration_ms,
        "avg_interval_ms": avg_interval_ms,
    }


def fetch_memory_insights(conn, user_id: int) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT total_score, round1_score, round2_score, round3_score
            FROM memory_scores
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 25
            """,
            (user_id,),
        )
        rows = cursor.fetchall()

    if not rows:
        return {
            "best_total": None,
            "average_total": None,
            "round_averages": None,
            "cognitive_score": None,
            "strengths": ["Play a memory round to see insights."],
            "weaknesses": [],
        }

    totals = [r["total_score"] for r in rows]
    best_total = max(totals)
    avg_total = sum(totals) / len(totals)

    r1_avg = sum((r["round1_score"] or 0) for r in rows) / len(rows)
    r2_avg = sum((r["round2_score"] or 0) for r in rows) / len(rows)
    r3_avg = sum((r["round3_score"] or 0) for r in rows) / len(rows)
    round_avgs = {1: round(r1_avg, 2), 2: round(r2_avg, 2), 3: round(r3_avg, 2)}

    normalized_total = min(100.0, max(0.0, (avg_total / 30.0) * 100.0))
    peak_bonus = min(10.0, best_total)
    cognitive_score = int(round(normalized_total + peak_bonus))

    strengths = []
    weaknesses = []
    best_round = max(round_avgs, key=round_avgs.get)
    weakest_round = min(round_avgs, key=round_avgs.get)

    strengths.append(f"Strongest in round {best_round} patterns")
    if round_avgs[weakest_round] < round_avgs[best_round]:
        weaknesses.append(f"Round {weakest_round} needs more repetition")

    if avg_total >= best_total * 0.9:
        strengths.append("Consistent memory recall")
    elif avg_total < best_total * 0.6:
        weaknesses.append("Work on sustaining peak memory scores")

    return {
        "best_total": round(best_total, 2),
        "average_total": round(avg_total, 2),
        "round_averages": round_avgs,
        "cognitive_score": cognitive_score,
        "strengths": strengths,
        "weaknesses": weaknesses,
    }
