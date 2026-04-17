"""
Planner backends disponíveis.

Padrão recomendado: OllamaPlanner (self-hosted, sem vendor lock-in).

Uso via factory:
  from planner import get_planner
  planner = get_planner(backend="ollama", model="llama3.1:8b")
"""
from __future__ import annotations

from planner.interface import Planner
from planner.mock_planner import DeterministicPlanner
from planner.strategic_planner import AttackHypothesis, StrategicPlanner
from planner.strategic_mock import MockStrategicPlanner


def get_planner(backend: str = "mock", **kwargs) -> Planner:
    """
    Factory de planners. Backend configurado via scope.yaml.

    backends:
      mock    — determinístico, sem LLM, padrão para testes
      ollama  — self-hosted, recomendado para produção
      openai  — qualquer API OpenAI-compatible
      claude  — Anthropic API (opcional)
    """
    if backend == "mock":
        return DeterministicPlanner(**kwargs)

    if backend == "ollama":
        from planner.ollama_planner import OllamaPlanner
        return OllamaPlanner(**kwargs)

    if backend == "openai":
        from planner.openai_planner import OpenAIPlanner
        return OpenAIPlanner(**kwargs)

    if backend == "claude":
        from planner.claude_planner import ClaudePlanner
        return ClaudePlanner(**kwargs)

    raise ValueError(
        f"Backend '{backend}' desconhecido. "
        f"Opções: mock, ollama, openai, claude"
    )


def get_strategic_planner(backend: str = "mock", **kwargs) -> StrategicPlanner:
    """
    Factory de strategic planners.

    backends:
      mock    — determinístico, sem LLM, padrão para testes
      openai  — qualquer API OpenAI-compatible (OpenAI, Ollama, etc.)
    """
    if backend == "mock":
        return MockStrategicPlanner(**kwargs)

    if backend in ("openai", "ollama"):
        from planner.openai_strategic_planner import OpenAICompatibleStrategicPlanner
        return OpenAICompatibleStrategicPlanner(**kwargs)

    raise ValueError(
        f"Strategic planner backend '{backend}' desconhecido. "
        f"Opções: mock, openai"
    )


__all__ = [
    "Planner", "get_planner",
    "StrategicPlanner", "AttackHypothesis", "MockStrategicPlanner", "get_strategic_planner",
]
