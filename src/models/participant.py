from dataclasses import dataclass, field
from typing import Dict, List, Optional
from src.models.match import MatchPrediction, Outcome


@dataclass
class Participant:
    name: str
    match_predictions: Dict[str, MatchPrediction] = field(default_factory=dict)
    # group -> [1st, 2nd, 3rd, 4th]
    group_rankings: Dict[str, List[str]] = field(default_factory=dict)
    total_score: int = 0
    score_breakdown: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "match_predictions": {
                mid: {
                    "home_goals": p.home_goals,
                    "away_goals": p.away_goals,
                    "outcome_90": p.outcome_90.token if p.outcome_90 else None,
                    "advances": p.advances,
                }
                for mid, p in self.match_predictions.items()
            },
            "group_rankings": self.group_rankings,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Participant":
        p = cls(name=data["name"])
        p.match_predictions = {
            mid: MatchPrediction(
                match_id=mid,
                home_goals=v["home_goals"],
                away_goals=v["away_goals"],
                outcome_90=Outcome.from_token(v["outcome_90"]) if v.get("outcome_90") else None,
                advances=v.get("advances"),
            )
            for mid, v in data.get("match_predictions", {}).items()
        }
        p.group_rankings = data.get("group_rankings", {})
        return p
