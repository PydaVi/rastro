"""
Ollama Planner — backend padrão recomendado para Rastro.

Roda localmente via Ollama (https://ollama.com).
Sem internet, sem custo, sem vendor lock-in.
Compatível com Llama, Qwen, Mistral, Phi e qualquer modelo suportado pelo Ollama.

Requisito: `ollama serve` rodando e o modelo configurado em scope.yaml disponível.
  ollama pull llama3.1:8b
"""
from __future__ import annotations

import json
from typing import List


from core.domain import Action, ActionType, Decision
from planner.interface import Planner

# Prompt do sistema enviado a cada decisão.
# Instrui o modelo a retornar JSON estruturado — nunca texto livre.
_SYSTEM_PROMPT = """\
You are an autonomous red team agent reasoning about attack paths.

You will receive:
- The current objective
- The current attack graph state
- A list of available actions with their parameters

Your task: choose the single best next action to advance toward the objective.

You MUST respond with valid JSON only. No explanation, no markdown, no preamble.

Response schema:
{
  "action_type": "<one of the available action_type values>",
  "actor": "<actor from the available action>",
  "target": "<target from the available action or null>",
  "parameters": {},
  "reason": "<one sentence explaining why this action advances the objective>"
}

If no action is viable, respond with action_type "analyze" and explain in reason.
"""


class OllamaPlanner(Planner):
    """
    Planner usando Ollama como backend LLM.

    Configuração via scope.yaml:
      planner:
        backend: ollama
        model: llama3.1:8b
        base_url: http://localhost:11434
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        timeout: int = 60,
    ) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "httpx não está instalado. Execute: pip install httpx"
            ) from exc

        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

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

        user_message = self._build_prompt(snapshot, available_actions)

        try:
            import httpx
            raw = self._call_ollama(user_message)
            return self._parse_response(raw, available_actions)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            # Ollama não está rodando ou não responde — falha explícita.
            raise RuntimeError(
                f"Ollama não está acessível em {self._base_url}. "
                f"Verifique se `ollama serve` está rodando. Erro: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_prompt(self, snapshot, available_actions: List[Action]) -> str:
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

    def _call_ollama(self, user_message: str) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "format": "json",  # força JSON nativo no Ollama >= 0.1.9
        }

        response = httpx.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def _parse_response(
        self, raw: str, available_actions: List[Action]
    ) -> Decision:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Ollama retornou JSON inválido: {raw!r}"
            ) from exc

        # Valida que a ação escolhida pelo LLM existe nas ações disponíveis.
        # Se o LLM alucinar uma ação fora do conjunto, fallback para analyze.
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
            # LLM escolheu algo fora do conjunto disponível — fallback seguro.
            fallback = available_actions[0]
            return Decision(
                action=fallback,
                reason=(
                    f"LLM escolheu ação indisponível ({action_type_str}/{actor}/{target}). "
                    f"Fallback para {fallback.action_type.value}. Razão original: {reason}"
                ),
            )

        return Decision(action=matched, reason=reason)
