from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import ReviewConfig
from app.core.time import as_utc


@dataclass(frozen=True)
class ReviewDecision:
    stage: int
    due_at: datetime


class ReviewScheduler:
    def __init__(self, config: ReviewConfig = ReviewConfig()):
        if not config.intervals_days or any(d <= 0 for d in config.intervals_days):
            raise ValueError("Intervalos de revisão devem ser positivos")
        self.config = config

    def schedule(self, previous: ReviewDecision | None, now: datetime, *,
                 correct: bool, independent: bool, delayed: bool) -> ReviewDecision:
        now = as_utc(now)
        if previous is None or not correct:
            return ReviewDecision(0, now + timedelta(days=self.config.intervals_days[0]))
        if as_utc(previous.due_at) <= now and correct and independent and delayed:
            stage = min(previous.stage + 1, len(self.config.intervals_days) - 1)
            return ReviewDecision(stage, now + timedelta(days=self.config.intervals_days[stage]))
        return previous
