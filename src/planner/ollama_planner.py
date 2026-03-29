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

Important:
- avoid repeating pivots already marked as failed unless there is new evidence
- if multiple roles are assumable, prefer the role that best advances toward the objective
- after a failed pivot, try a different valid branch instead of looping on the same discovery step

You MUST respond with valid JSON only. No explanation, no markdown, no preamble.

Response schema:
{
  "action_index": <integer index from available_actions>,
  "reason": "<one sentence explaining why this action advances the objective>"
}

If no action is viable, respond with action_index -1 and explain in reason.
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
            decision = self._parse_response(raw, available_actions)
            decision.planner_metadata.update(
                {
                    "planner_backend": "ollama",
                    "planner_model": self._model,
                    "raw_response": raw,
                }
            )
            return decision
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
        actions_repr = [a.model_dump() for a in available_actions]

        return json.dumps(
            {
                "objective": {
                    "description": snapshot.objective.description,
                    "target": snapshot.objective.target,
                },
                "flags": snapshot.fixture_state.get("flags", []),
                "steps_taken": snapshot.steps_taken,
                "path_memory": {
                    "tested_assume_roles": getattr(snapshot, "tested_assume_roles", []),
                    "failed_assume_roles": getattr(snapshot, "failed_assume_roles", []),
                },
                "available_actions": [
                    {"index": idx, **action} for idx, action in enumerate(actions_repr)
                ],
            },
            indent=2,
        )

    def _call_ollama(self, user_message: str) -> str:
        import httpx

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

        reason = data.get("reason", "no reason provided")
        action_index = data.get("action_index", None)
        if isinstance(action_index, int):
            if action_index == -1:
                return Decision(
                    action=Action(
                        action_type=ActionType.ANALYZE,
                        actor="system",
                        target=None,
                        parameters={"note": "no_viable_action"},
                    ),
                    reason=reason,
                    planner_metadata={},
                )
            if action_index >= 0 and action_index < len(available_actions):
                return Decision(
                    action=available_actions[action_index],
                    reason=reason,
                    planner_metadata={},
                )

        # Backward compatibility: try action_type/actor/target matching.
        action_type_str = data.get("action_type", "")
        actor = data.get("actor", "")
        target = data.get("target")

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
                planner_metadata={},
            )

        return Decision(action=matched, reason=reason, planner_metadata={})
