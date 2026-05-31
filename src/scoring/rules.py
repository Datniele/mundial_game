import yaml
from pathlib import Path
from dataclasses import dataclass

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


@dataclass
class ScoringRules:
    exact_score: int
    correct_outcome: int
    group_ranking_exact: int
    group_ranking_partial: int
    knockout_correct_winner: int
    knockout_exact_score: int


def load_rules() -> ScoringRules:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    gs = cfg["scoring"]["group_stage"]
    ko = cfg["scoring"]["knockout"]

    return ScoringRules(
        exact_score=gs["exact_score"],
        correct_outcome=gs["correct_outcome"],
        group_ranking_exact=gs["group_ranking_exact"],
        group_ranking_partial=gs["group_ranking_partial"],
        knockout_correct_winner=ko["correct_winner"],
        knockout_exact_score=ko["exact_score"],
    )
