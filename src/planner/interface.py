from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from core.domain import Action, Decision


class Planner(ABC):
    @abstractmethod
    def decide(self, snapshot, available_actions: List[Action]) -> Decision:
        raise NotImplementedError
