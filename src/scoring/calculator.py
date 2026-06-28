from dataclasses import dataclass, field
from typing import Dict, List

from src.models.match import Result
from src.models.participant import Participant


@dataclass
class GroupStageScore:
    name: str
    total_error: int  # lower = better
    score: float = 0.0  # fattore di correzione applicato all'errore: più alto = meglio
    per_group: Dict[str, int] = field(default_factory=dict)


@dataclass
class KnockoutRoundScore:
    name: str
    correct_advances: int   # C1 — chi passa il turno corretto (higher = better)
    correct_outcomes: int   # C2 — esito 90' (1/X/2) corretto (higher = better)
    goal_diff_error: int    # C3 — errore differenza reti (lower = better)


def score_group_stage(
    participants: List[Participant],
    actual_group_rankings: Dict[str, List[str]],
) -> List[GroupStageScore]:
    """
    Per ogni partecipante: somma di |pos_predetta - pos_reale| su tutti i gironi
    con risultati disponibili. Errore più basso = previsione migliore.
    Inclusi solo i partecipanti con almeno un valore non-null nei gironi.
    """
    scores = []
    for p in participants:
        if not p.group_rankings:
            continue
        if not any(any(v is not None for v in r) for r in p.group_rankings.values()):
            continue
        total_error = 0
        per_group: Dict[str, int] = {}
        for group, actual in actual_group_rankings.items():
            pred = p.group_rankings.get(group, [])
            error = 0
            for actual_pos, team in enumerate(actual):
                if team in pred:
                    error += abs(pred.index(team) - actual_pos)
                else:
                    # squadra non inserita: penalità massima (max scarto possibile in 4 squadre)
                    error += 3
            per_group[group] = error
            total_error += error
        # Fattore di correzione: trasforma l'errore (più basso = meglio) in un
        # punteggio dove più alto = meglio. Errore 0 → 10.
        score = (96 - total_error) / 9.6
        scores.append(GroupStageScore(
            name=p.name, total_error=total_error, score=score, per_group=per_group
        ))
    return sorted(scores, key=lambda s: -s.score)


def score_knockout_round(
    participants: List[Participant],
    results: Dict[str, Result],
    match_ids: List[str],
) -> List[KnockoutRoundScore]:
    """
    Per ogni partecipante con previsioni per i match_ids dati:
      C1 = passaggi del turno corretti (pred.advances == result.advances)
      C2 = esiti 90' corretti (pred.outcome_90 == result.outcome)
      C3 = somma |diff_reti_predetta - diff_reti_reale| per ogni partita

    Ordinamento: C1 desc, C2 desc, C3 asc.
    Vengono valutate solo le partite con sia la previsione che il risultato reale.
    I campi outcome_90/advances a None non guadagnano C1/C2.
    """
    scores = []
    for p in participants:
        if not any(mid in p.match_predictions for mid in match_ids):
            continue
        correct_advances = 0
        correct_outcomes = 0
        goal_diff_error = 0
        for mid in match_ids:
            pred = p.match_predictions.get(mid)
            result = results.get(mid)
            if pred is None or result is None:
                continue
            if pred.advances is not None and result.advances is not None \
                    and pred.advances == result.advances:
                correct_advances += 1
            if pred.outcome_90 is not None and pred.outcome_90 == result.outcome:
                correct_outcomes += 1
            pred_diff = pred.home_goals - pred.away_goals
            actual_diff = result.home_goals - result.away_goals
            goal_diff_error += abs(pred_diff - actual_diff)
        scores.append(KnockoutRoundScore(
            name=p.name,
            correct_advances=correct_advances,
            correct_outcomes=correct_outcomes,
            goal_diff_error=goal_diff_error,
        ))
    return sorted(scores, key=lambda s: (-s.correct_advances, -s.correct_outcomes, s.goal_diff_error))
