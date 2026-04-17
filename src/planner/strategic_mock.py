from __future__ import annotations

from core.domain import Scope
from planner.strategic_planner import AttackHypothesis, StrategicPlanner

_ROLE_ESCALATION_SIGNALS = {
    "createpolicyversion", "setdefaultpolicyversion",
    "attachrolepolicy", "attachuserpolicy", "putrolepolicy", "putuserpolicy",
    "passrole", "cloudformation", "codebuild", "sagemaker",
    "iamfullaccess", "administratoraccess",
}

_RESOURCE_TYPE_TO_ATTACK_CLASS: dict[str, str] = {
    "identity.role": "role_chain",
    "secret.secrets_manager": "credential_access",
    "secret.ssm_parameter": "credential_access",
    "data_store.s3_object": "data_exfil",
    "data_store.s3_bucket": "data_exfil",
    "compute.lambda_function": "compute_pivot",
    "compute.ec2_instance": "compute_pivot",
    "crypto.kms_key": "credential_access",
}


class MockStrategicPlanner(StrategicPlanner):
    """
    Planner estratégico determinístico para testes offline.

    Para cada par (entry_identity, resource relevante) no discovery snapshot,
    gera uma AttackHypothesis com campos calculados deterministicamente —
    sem randomness, sem LLM externo.
    """

    def plan_attacks(
        self,
        discovery_snapshot: dict,
        entry_identities: list[str],
        scope: Scope,
    ) -> list[AttackHypothesis]:
        if not entry_identities:
            return []

        resources = discovery_snapshot.get("resources", [])
        hypotheses: list[AttackHypothesis] = []
        seen: set[tuple[str, str]] = set()

        for resource in resources:
            resource_type = resource.get("resource_type", "")
            identifier = resource.get("identifier", "")
            if not identifier or resource_type not in _RESOURCE_TYPE_TO_ATTACK_CLASS:
                continue

            attack_class = _RESOURCE_TYPE_TO_ATTACK_CLASS[resource_type]
            metadata = resource.get("metadata", {})

            # Roles com sinais de escalação → iam_privesc em vez de role_chain
            if resource_type == "identity.role":
                escalation = set(metadata.get("policy_escalation_signals", []))
                if escalation & _ROLE_ESCALATION_SIGNALS:
                    attack_class = "iam_privesc"

            entry_identity = entry_identities[0]
            key = (entry_identity, identifier)
            if key in seen:
                continue
            seen.add(key)

            steps, reasoning = _build_steps_and_reasoning(resource_type, attack_class, identifier, metadata)
            confidence = _derive_confidence(resource_type, attack_class, metadata)

            hypotheses.append(
                AttackHypothesis(
                    entry_identity=entry_identity,
                    target=identifier,
                    attack_class=attack_class,
                    attack_steps=steps,
                    confidence=confidence,
                    reasoning=reasoning,
                )
            )

        return hypotheses


def _build_steps_and_reasoning(
    resource_type: str,
    attack_class: str,
    identifier: str,
    metadata: dict,
) -> tuple[list[str], str]:
    short = identifier.rsplit("/", 1)[-1].rsplit(":", 1)[-1]

    if attack_class == "iam_privesc":
        signals = metadata.get("policy_escalation_signals", [])
        signal_str = ", ".join(signals[:3]) or "escalation policy"
        steps = [
            f"Identify escalation opportunity on {short} via {signal_str}",
            "Exploit IAM policy mutation to gain privileged identity",
            "Access sensitive resources as elevated principal",
        ]
        reasoning = f"{short} has escalation signals ({signal_str}) exploitable from entry identity."
    elif attack_class == "role_chain":
        steps = [
            f"Enumerate trust policy of {short}",
            f"Assume {short} via sts:AssumeRole",
            "Access target resources as assumed role",
        ]
        reasoning = f"{short} may be assumable from entry identity based on trust policy."
    elif attack_class == "credential_access":
        steps = [
            "Assume role with access to secret store",
            f"Read secret {short}",
        ]
        reasoning = f"{short} stores sensitive credentials reachable via IAM role assumption."
    elif attack_class == "data_exfil":
        steps = [
            "Assume role with s3:GetObject permission",
            f"Exfiltrate object {short}",
        ]
        reasoning = f"{short} contains sensitive data accessible via IAM role assumption."
    else:  # compute_pivot
        steps = [
            f"Identify execution role of {short}",
            "Pivot to privileged role via compute instance profile",
        ]
        reasoning = f"{short} may execute with a privileged role enabling lateral movement."

    return steps, reasoning


def _derive_confidence(resource_type: str, attack_class: str, metadata: dict) -> str:
    if attack_class == "iam_privesc":
        signals = metadata.get("policy_escalation_signals", [])
        if any(s in signals for s in ("administratoraccess", "iamfullaccess")):
            return "high"
        return "medium"
    if attack_class in ("credential_access", "data_exfil"):
        name = metadata.get("name", "") or ""
        if any(kw in name.lower() for kw in ("prod", "payroll", "finance", "secret")):
            return "high"
        return "medium"
    return "low"
