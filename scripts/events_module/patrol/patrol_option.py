from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class PatrolOption:
    text: str = ""
    chance_of_success: Optional[int] = None
    success_outcomes: list = field(default_factory=list)
    fail_outcomes: list = field(default_factory=list)

    def __post_init__(self):
        from scripts.events_module.text_pool_event.text_pool_event import TextPoolEvent

        self.success_outcomes = [
            outcome
            if isinstance(outcome, TextPoolEvent)
            else TextPoolEvent(**outcome)
            for outcome in self.success_outcomes
        ]
        self.fail_outcomes = [
            outcome
            if isinstance(outcome, TextPoolEvent)
            else TextPoolEvent(**outcome)
            for outcome in self.fail_outcomes
        ]