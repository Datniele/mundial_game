from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Phase(str, Enum):
    GROUP = "group"
    ROUND_OF_32 = "sedicesimi"
    ROUND_OF_16 = "ottavi"
    QUARTER = "quarti"
    SEMI = "semifinali"
    THIRD_PLACE = "finale_3posto"
    FINAL = "finale"


class Outcome(str, Enum):
    HOME = "home"
    AWAY = "away"
    DRAW = "draw"

    @property
    def token(self) -> str:
        """Rappresentazione 1/X/2 dell'esito."""
        return {"home": "1", "draw": "X", "away": "2"}[self.value]

    @classmethod
    def from_token(cls, token: str) -> "Outcome":
        """Costruisce un Outcome dal token 1/X/2."""
        return {"1": cls.HOME, "X": cls.DRAW, "2": cls.AWAY}[token]


@dataclass
class Match:
    id: str
    phase: Phase
    home_team: str
    away_team: str
    group: Optional[str] = None
    date: Optional[str] = None


@dataclass
class Result:
    match_id: str
    home_goals: int
    away_goals: int
    advances: Optional[str] = None  # "home" | "away" — chi passa il turno

    @property
    def outcome(self) -> Outcome:
        if self.home_goals > self.away_goals:
            return Outcome.HOME
        if self.away_goals > self.home_goals:
            return Outcome.AWAY
        return Outcome.DRAW

    @property
    def winner(self) -> Optional[str]:
        """Returns winning team name, None if draw."""
        return None  # resolved externally with match context


@dataclass
class MatchPrediction:
    match_id: str
    home_goals: int
    away_goals: int
    outcome_90: Optional["Outcome"] = None  # esito esplicito 1/X/2 a 90'
    advances: Optional[str] = None           # "home" | "away" — chi passa il turno

    @property
    def outcome(self) -> Outcome:
        if self.home_goals > self.away_goals:
            return Outcome.HOME
        if self.away_goals > self.home_goals:
            return Outcome.AWAY
        return Outcome.DRAW
