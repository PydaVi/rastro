"""
Claude Planner — Anthropic API (opcional).

NÃO é o backend padrão. Use apenas se tiver razão específica para isso.
Para a maioria dos casos, prefira ollama_planner (self-hosted) ou
openai_planner (API OpenAI-compatible).

Configuração via scope.yaml:
  planner:
    backend: claude
    model: claude-3-5-haiku-20241022

Variável de ambiente necessária: ANTHROPIC_API_KEY
"""
from __future__ import annotations

import json
import os
from typing import List

from core.domain import Action, ActionType, Decision
from planner.interface import Planner
from planner.openai_planner import _build_prompt, _parse_response
from planner.ollama_planner import _SYSTEM_PROMPT


class ClaudePlanner(Planner):
    def __init__(
        self,
        model: str = "claude-3-5-haiku-20241022",
        api_key: str | None = None,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic não está instalado. Execute: pip install anthropic"
            ) from exc

        self._model = model
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    def decide(self, snapshot, available_actions: List[Action]) -> Decision:
        if not available_actions:
            return Decision(
                action=Action(
                    action_type=ActionType.ANALYZE,
                    actor="system",
                    target=None,
                    parameters={"note": "no_actions_available"},
                ),
                reason="No available actions; halting step.",
            )

        user_message = _build_prompt(snapshot, available_actions)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text
        decision = _parse_response(raw, available_actions)
        decision.planner_metadata.update(
            {
                "planner_backend": "claude",
                "planner_model": self._model,
                "raw_response": raw,
            }
        )
        return decision
