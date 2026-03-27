"""
OpenAI-compatible Planner — suporta qualquer API com interface OpenAI.

Compatível com: OpenAI, Groq, Together AI, Mistral API, Perplexity,
e qualquer provider que implemente o schema /v1/chat/completions.

Configuração via scope.yaml:
  planner:
    backend: openai
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1   # ou outro provider
    # api_key lido de variável de ambiente — nunca hardcoded

Variável de ambiente necessária: OPENAI_API_KEY (ou equivalente do provider)
"""
from __future__ import annotations

import json
import os
from typing import List

from core.domain import Action, ActionType, Decision
from planner.interface import Planner
from planner.ollama_planner import _SYSTEM_PROMPT  # reusa o mesmo system prompt


class OpenAIPlanner(Planner):
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai não está instalado. Execute: pip install openai"
            ) from exc

        self._model = model
        self._client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
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

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        return _parse_response(raw, available_actions)


def _build_prompt(snapshot, available_actions: List[Action]) -> str:
    actions_repr = [
        {
            "action_type": a.action_type.value,
            "actor": a.actor,
            "target": a.target,
            "parameters": a.parameters,
        }
        for a in available_actions
    ]
    return json.dumps(
        {
            "objective": str(snapshot.get("objective", "unknown")),
            "graph_summary": snapshot.get("graph_summary", {}),
            "available_actions": actions_repr,
        },
        indent=2,
    )


def _parse_response(raw: str, available_actions: List[Action]) -> Decision:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM retornou JSON inválido: {raw!r}") from exc

    action_type_str = data.get("action_type", "")
    actor = data.get("actor", "")
    target = data.get("target")
    reason = data.get("reason", "no reason provided")

    matched = next(
        (
            a
            for a in available_actions
            if a.action_type.value == action_type_str
            and a.actor == actor
            and a.target == target
        ),
        None,
    )

    if matched is None:
        fallback = available_actions[0]
        return Decision(
            action=fallback,
            reason=(
                f"LLM escolheu ação indisponível ({action_type_str}/{actor}/{target}). "
                f"Fallback para {fallback.action_type.value}. Razão original: {reason}"
            ),
        )

    return Decision(action=matched, reason=reason)
