from typing import Dict, List
from src.models.match import Match, MatchPrediction, Result, Phase
from src.models.participant import Participant
from src.scoring.rules import ScoringRules, load_rules


def _score_match(
    prediction: MatchPrediction,
    result: Result,
    phase: Phase,
    rules: ScoringRules,
) -> tuple[int, str]:
    """Returns (points, reason)."""
    is_group = phase == Phase.GROUP

    if prediction.home_goals == result.home_goals and prediction.away_goals == result.away_goals:
        pts = rules.exact_score if is_group else rules.knockout_exact_score
        return pts, "risultato esatto"

    if prediction.outcome == result.outcome:
        pts = rules.correct_outcome if is_group else rules.knockout_correct_winner
        return pts, "esito corretto"

    return 0, "errato"


def _score_group_rankings(
    predicted: Dict[str, List[str]],
    actual: Dict[str, List[str]],
    rules: ScoringRules,
) -> tuple[int, Dict[str, int]]:
    """Returns (total_points, per_group_breakdown)."""
    total = 0
    breakdown: Dict[str, int] = {}

    for group, actual_ranking in actual.items():
        pred_ranking = predicted.get(group, [])
        if not pred_ranking:
            breakdown[group] = 0
            continue

        if pred_ranking == actual_ranking:
            pts = rules.group_ranking_exact
            breakdown[group] = pts
        elif set(pred_ranking) == set(actual_ranking):
            # entrambe le squadre giuste ma ordine invertito
            pts = rules.group_ranking_partial
            breakdown[group] = pts
        elif pred_ranking[0] == actual_ranking[0] or pred_ranking[1] == actual_ranking[1]:
            pts = rules.group_ranking_partial
            breakdown[group] = pts
        else:
            breakdown[group] = 0

        total += breakdown[group]

    return total, breakdown


def calculate_scores(
    participants: List[Participant],
    results: Dict[str, Result],
    matches: Dict[str, Match],
    actual_group_rankings: Dict[str, List[str]],
) -> List[Participant]:
    rules = load_rules()

    for participant in participants:
        total = 0
        breakdown: Dict[str, int] = {}

        # Punteggio partite
        for match_id, prediction in participant.match_predictions.items():
            if match_id not in results:
                continue
            result = results[match_id]
            match = matches.get(match_id)
            if not match:
                continue

            pts, reason = _score_match(prediction, result, match.phase, rules)
            breakdown[match_id] = pts
            total += pts

        # Punteggio classifiche gironi
        if actual_group_rankings:
            ranking_pts, ranking_breakdown = _score_group_rankings(
                participant.group_rankings, actual_group_rankings, rules
            )
            for g, pts in ranking_breakdown.items():
                breakdown[f"ranking_{g}"] = pts
            total += ranking_pts

        participant.total_score = total
        participant.score_breakdown = breakdown

    return sorted(participants, key=lambda p: p.total_score, reverse=True)
