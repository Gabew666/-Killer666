from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MasteryConfig:
    prior: float = 0.35
    alpha: float = 0.28
    independence_hours: float = 24.0
    confidence_scale: float = 8.0
    immediate_weight: float = 0.65


@dataclass(frozen=True)
class ReviewConfig:
    intervals_days: tuple[int, ...] = (1, 3, 7, 14, 30)


@dataclass(frozen=True)
class PlannerConfig:
    exam_urgency: float = 5.0
    knowledge_gap: float = 2.0
    review_urgency: float = 3.0
    importance: float = 1.0
    prerequisite_value: float = 1.5
    recent_errors: float = 2.0
    mastery_penalty: float = 2.0
    prerequisite_gap: float = 2.0
    prerequisite_threshold: float = 0.6
    hard_gate_threshold: float = 0.2
    exam_horizon_days: float = 14.0
    inherited_exam_discount: float = 0.9
    time_margin: float = 0.08
    min_minutes: int = 10
    max_minutes: int = 240
    block_minutes: int = 20


@dataclass(frozen=True)
class Settings:
    database_url: str
    timezone: str = "America/Sao_Paulo"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    content_mode: Literal["provisional", "real"] = "provisional"

    def __post_init__(self) -> None:
        ZoneInfo(self.timezone)  # Falha cedo se houver configuração inválida.
        if any(origin == "*" or not origin.startswith(("http://", "https://")) for origin in self.cors_origins):
            raise ValueError("ATLAS_CORS_ORIGINS exige origens HTTP(S) explícitas")
        if self.content_mode not in ("provisional", "real"):
            raise ValueError("ATLAS_CONTENT_MODE deve ser provisional ou real")

    @classmethod
    def from_env(cls) -> "Settings":
        path = Path(__file__).resolve().parents[3] / "data" / "atlas.db"
        return cls(
            os.getenv("ATLAS_DATABASE_URL", f"sqlite:///{path}"),
            os.getenv("ATLAS_TIMEZONE", "America/Sao_Paulo"),
            tuple(origin.strip() for origin in os.getenv(
                "ATLAS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",") if origin.strip()),
            os.getenv("ATLAS_CONTENT_MODE", "provisional"),
        )
