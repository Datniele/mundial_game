"""Test per src/scoring/calculator.py — scoring knockout C1/C2/C3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.match import MatchPrediction, Result
from src.models.participant import Participant
from src.scoring.calculator import score_knockout_round


def _p(name, preds):
    p = Participant(name=name)
    p.match_predictions = preds
    return p


def test_advance_and_exact_are_independent():
    # Reale: 2-2, passa "home". Diff reti reale = 0.
    results = {"S01": Result("S01", 2, 2, advances="home")}
    # Pronostico: passaggio corretto, risultato esatto, diff 0
    pred = MatchPrediction("S01", 2, 2, advances="home")
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 1      # C1: home == home
    assert s.exact_scores == 1          # C2: 2-2 == 2-2
    assert s.goal_diff_error == 0       # C3


def test_right_advance_wrong_exact_score():
    # Reale 2-1, passa home. Pronostico 3-1 (passa home), diff prevista +2 vs reale +1
    results = {"S01": Result("S01", 2, 1, advances="home")}
    pred = MatchPrediction("S01", 3, 1, advances="home")
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 1
    assert s.exact_scores == 0          # 3-1 != 2-1
    assert s.goal_diff_error == 1       # |2 - 1|


def test_none_advance_earns_no_c1():
    results = {"S01": Result("S01", 1, 0, advances="home")}
    pred = MatchPrediction("S01", 1, 0)  # advances = None, ma punteggio esatto
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 0
    assert s.exact_scores == 1          # 1-0 == 1-0
    assert s.goal_diff_error == 0


def test_ordering_c1_then_c2_then_c3():
    results = {
        "S01": Result("S01", 1, 0, advances="home"),
        "S02": Result("S02", 2, 0, advances="home"),
    }
    # alice: 2 passaggi giusti
    alice = _p("alice", {
        "S01": MatchPrediction("S01", 1, 0, advances="home"),
        "S02": MatchPrediction("S02", 2, 0, advances="home"),
    })
    # bob: 1 passaggio giusto
    bob = _p("bob", {
        "S01": MatchPrediction("S01", 1, 0, advances="home"),
        "S02": MatchPrediction("S02", 0, 1, advances="away"),
    })
    ranking = score_knockout_round([bob, alice], results, ["S01", "S02"])
    assert [s.name for s in ranking] == ["alice", "bob"]  # C1 alice(2) > bob(1)


def test_exact_scores_breaks_c1_tie():
    # Entrambi 1 passaggio giusto; alice ha 1 risultato esatto in più
    results = {"S01": Result("S01", 2, 1, advances="home")}
    alice = _p("alice", {"S01": MatchPrediction("S01", 2, 1, advances="home")})  # esatto
    bob = _p("bob", {"S01": MatchPrediction("S01", 3, 0, advances="home")})      # non esatto
    ranking = score_knockout_round([bob, alice], results, ["S01"])
    assert [s.name for s in ranking] == ["alice", "bob"]  # tie su C1, C2 alice > bob


if __name__ == "__main__":
    test_advance_and_exact_are_independent()
    test_right_advance_wrong_exact_score()
    test_none_advance_earns_no_c1()
    test_ordering_c1_then_c2_then_c3()
    test_exact_scores_breaks_c1_tie()
    print("OK")
