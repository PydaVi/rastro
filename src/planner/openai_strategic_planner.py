from __future__ import annotations

import json
import logging
import os
import time

from planner.strategic_planner import AttackHypothesis, StrategicPlanner
from planner.strategic_prompting import STRATEGIC_SYSTEM_PROMPT, build_strategic_prompt

logger = logging.getLogger(__name__)

_BATCH_SIZE = 10  # entry identities per LLM call
_MAX_RETRIES = 5


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
        batches = [
            entry_identities[i : i + _BATCH_SIZE]
            for i in range(0, len(entry_identities), _BATCH_SIZE)
        ]
        logger.info(
            "StrategicPlanner: %d entry identities → %d batches of ≤%d",
            len(entry_identities),
            len(batches),
            _BATCH_SIZE,
        )

        all_hypotheses: list[AttackHypothesis] = []
        for batch_idx, batch in enumerate(batches):
            if batch_idx > 0:
                time.sleep(2)  # evita burst de TPM em chamadas consecutivas
            batch_hypotheses = self._plan_batch(discovery_snapshot, batch, scope)
            logger.info(
                "StrategicPlanner batch %d/%d: %d hypotheses for %s",
                batch_idx + 1,
                len(batches),
                len(batch_hypotheses),
                [e.split("/")[-1] for e in batch],
            )
            all_hypotheses.extend(batch_hypotheses)

        return _deduplicate(all_hypotheses)

    def _plan_batch(
        self,
        discovery_snapshot: dict,
        entry_identities: list[str],
        scope,
    ) -> list[AttackHypothesis]:
        user_message = build_strategic_prompt(discovery_snapshot, entry_identities, scope)
        response = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": STRATEGIC_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    timeout=self._timeout,
                )
                break
            except Exception as exc:
                msg = str(exc)
                if "rate_limit_exceeded" in msg and attempt < _MAX_RETRIES - 1:
                    wait = 2 ** attempt * 5  # 5, 10, 20, 40, 80s
                    logger.warning(
                        "StrategicPlanner rate limit (attempt %d/%d), waiting %ds",
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                    continue
                logger.error("OpenAICompatibleStrategicPlanner._plan_batch failed: %s", exc)
                return []

        if response is None:
            return []

        try:
            raw = response.choices[0].message.content
            data = json.loads(raw)
            raw_hypotheses = [
                h for h in data.get("hypotheses", [])
                if h.get("attack_steps")  # filtra hipóteses sem steps antes do pydantic
            ]
            return [AttackHypothesis.model_validate(h) for h in raw_hypotheses]
        except Exception as exc:
            logger.error("StrategicPlanner failed to parse batch response: %s", exc)
            return []


def _deduplicate(hypotheses: list[AttackHypothesis]) -> list[AttackHypothesis]:
    seen: set[tuple] = set()
    result: list[AttackHypothesis] = []
    for h in hypotheses:
        key = (h.entry_identity, h.target, h.attack_class)
        if key not in seen:
            seen.add(key)
            result.append(h)
    return result
