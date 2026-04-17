from __future__ import annotations

import json
import logging
import os

from planner.strategic_planner import AttackHypothesis, StrategicPlanner
from planner.strategic_prompting import STRATEGIC_SYSTEM_PROMPT, build_strategic_prompt

logger = logging.getLogger(__name__)


class OpenAICompatibleStrategicPlanner(StrategicPlanner):
    def __init__(
        self,
        model: str = "gpt-4o",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 60,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai não está instalado. Execute: pip install openai"
            ) from exc

        self._model = model
        self._timeout = timeout

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY") or "not-needed"
        self._client = OpenAI(
            api_key=resolved_key,
            base_url=base_url,
        )

    def plan_attacks(
        self,
        discovery_snapshot: dict,
        entry_identities: list[str],
        scope,
    ) -> list[AttackHypothesis]:
        try:
            user_message = build_strategic_prompt(
                discovery_snapshot, entry_identities, scope
            )
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": STRATEGIC_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                timeout=self._timeout,
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)
            raw_hypotheses = data.get("hypotheses", [])
            return [AttackHypothesis.model_validate(h) for h in raw_hypotheses]
        except Exception as exc:
            logger.error("OpenAICompatibleStrategicPlanner.plan_attacks failed: %s", exc)
            return []
