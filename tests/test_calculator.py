"""Test per src/scoring/calculator.py — scoring knockout C1/C2/C3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.match import MatchPrediction, Outcome, Result
from src.models.participant import Participant
from src.scoring.calculator import score_knockout_round


def _p(name, preds):
    p = Participant(name=name)
    p.match_predictions = preds
    return p


def test_criteria_are_independent_on_discordant_match():
    # Reale: 90' = 2-2 (esito X), passa "home". Diff reti reale = 0.
    results = {"S01": Result("S01", 2, 2, advances="home")}
    # Pronostico discordante ma con passaggio e esito corretti, punteggio diverso
    pred = MatchPrediction("S01", 1, 1, outcome_90=Outcome.DRAW, advances="home")
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 1      # C1: home == home
    assert s.correct_outcomes == 1      # C2: X == X (esito esplicito)
    assert s.goal_diff_error == 0       # C3: diff prevista 0, reale 0


def test_wrong_advance_right_outcome():
    results = {"S01": Result("S01", 0, 0, advances="away")}
    pred = MatchPrediction("S01", 0, 0, outcome_90=Outcome.DRAW, advances="home")
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 0      # home != away
    assert s.correct_outcomes == 1      # X == X
    assert s.goal_diff_error == 0


def test_none_fields_earn_nothing_on_c1_c2():
    results = {"S01": Result("S01", 1, 0, advances="home")}
    pred = MatchPrediction("S01", 1, 0)  # outcome_90 e advances = None
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 0
    assert s.correct_outcomes == 0
    assert s.goal_diff_error == 0       # diff prevista +1, reale +1


def test_ordering_c1_then_c2_then_c3():
    results = {
        "S01": Result("S01", 1, 0, advances="home"),
        "S02": Result("S02", 2, 0, advances="home"),
    }
    # alice: 2 passaggi giusti
    alice = _p("alice", {
        "S01": MatchPrediction("S01", 1, 0, outcome_90=Outcome.HOME, advances="home"),
        "S02": MatchPrediction("S02", 2, 0, outcome_90=Outcome.HOME, advances="home"),
    })
    # bob: 1 passaggio giusto
    bob = _p("bob", {
        "S01": MatchPrediction("S01", 1, 0, outcome_90=Outcome.HOME, advances="home"),
        "S02": MatchPrediction("S02", 0, 1, outcome_90=Outcome.AWAY, advances="away"),
    })
    ranking = score_knockout_round([bob, alice], results, ["S01", "S02"])
    assert [s.name for s in ranking] == ["alice", "bob"]  # C1 alice(2) > bob(1)


if __name__ == "__main__":
    test_criteria_are_independent_on_discordant_match()
    test_wrong_advance_right_outcome()
    test_none_fields_earn_nothing_on_c1_c2()
    test_ordering_c1_then_c2_then_c3()
    print("OK")
