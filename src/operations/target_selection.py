from __future__ import annotations

import json
from pathlib import Path


KEYWORD_WEIGHTS = {
    "payroll": 40,
    "finance": 25,
    "prod": 20,
    "secret": 20,
    "token": 15,
    "api_key": 15,
    "backup": 10,
}


PROFILE_RULES = {
    "aws-iam-s3": {"resource_types": {"data_store.s3_bucket", "data_store.s3_object"}},
    "aws-iam-secrets": {"resource_types": {"secret.secrets_manager"}},
    "aws-iam-ssm": {"resource_types": {"secret.ssm_parameter"}},
    "aws-iam-role-chaining": {"resource_types": {"identity.role"}},
}


def select_foundation_targets(
    *,
    discovery_snapshot: dict,
    output_dir: Path,
    max_candidates_per_profile: int = 5,
) -> tuple[Path, Path, dict]:
    candidates: list[dict] = []
    for profile_name, rule in PROFILE_RULES.items():
        profile_candidates = []
        for resource in discovery_snapshot.get("resources", []):
            if resource["resource_type"] not in rule["resource_types"]:
                continue
            candidate = _build_candidate(profile_name, resource)
            if candidate is None:
                continue
            profile_candidates.append(candidate)
        profile_candidates.sort(key=lambda item: (-item["score"], item["resource_arn"]))
        candidates.extend(profile_candidates[:max_candidates_per_profile])

    summary = _build_candidate_summary(candidates)
    payload = {
        "target": discovery_snapshot.get("target"),
        "bundle": discovery_snapshot.get("bundle"),
        "derived_from": "discovery.json",
        "summary": summary,
        "candidates": candidates,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "target_candidates.json"
    md_path = output_dir / "target_candidates.md"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_render_target_candidates_markdown(payload))
    return json_path, md_path, payload


def _build_candidate(profile_name: str, resource: dict) -> dict | None:
    identifier = resource["identifier"]
    lowered = identifier.lower()

    if profile_name == "aws-iam-role-chaining" and lowered.endswith(("/rolea", "/roleb", "/rolem", "/roleq")):
        # low-confidence named lab roles are still useful chain candidates
        pass

    score = 10
    reasons: list[str] = []
    signals: dict = {"keyword_hits": [], "service": resource["service"]}

    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in lowered:
            score += weight
            signals["keyword_hits"].append(keyword)
            reasons.append(f"keyword:{keyword}")

    if resource["resource_type"] == "data_store.s3_object":
        score += 15
        reasons.append("object_level_target")
    elif resource["resource_type"] == "secret.secrets_manager":
        score += 20
        reasons.append("secret_surface")
    elif resource["resource_type"] == "secret.ssm_parameter":
        score += 20
        reasons.append("parameter_surface")
    elif resource["resource_type"] == "identity.role":
        score += 5
        reasons.append("role_chain_candidate")

    if profile_name == "aws-iam-role-chaining" and "broker" in lowered:
        score += 15
        reasons.append("chain_broker_signal")
    if profile_name == "aws-iam-role-chaining" and "dataaccess" in lowered:
        score += 25
        reasons.append("data_access_signal")
    if profile_name == "aws-iam-role-chaining" and "audit" in lowered:
        score -= 10
        reasons.append("audit_role_penalty")

    if not reasons:
        reasons.append("baseline_profile_match")

    confidence = "high" if score >= 60 else "medium" if score >= 35 else "low"
    return {
        "id": f"{profile_name}:{identifier}",
        "resource_arn": identifier,
        "resource_type": resource["resource_type"],
        "profile_family": profile_name,
        "score": score,
        "confidence": confidence,
        "selection_reason": reasons,
        "signals": signals,
        "supporting_evidence": {
            "service": resource["service"],
            "region": resource["region"],
            "metadata": resource.get("metadata", {}),
        },
    }


def _build_candidate_summary(candidates: list[dict]) -> dict:
    by_profile: dict[str, int] = {}
    for candidate in candidates:
        by_profile[candidate["profile_family"]] = by_profile.get(candidate["profile_family"], 0) + 1
    return {
        "candidates_total": len(candidates),
        "by_profile": by_profile,
        "high_confidence": sum(1 for candidate in candidates if candidate["confidence"] == "high"),
    }


def _render_target_candidates_markdown(payload: dict) -> str:
    lines = [
        "# Target Candidates",
        "",
        f"- Target: {payload['target']}",
        f"- Bundle: {payload['bundle']}",
        f"- Candidates total: {payload['summary']['candidates_total']}",
        f"- High confidence: {payload['summary']['high_confidence']}",
        "",
        "## Candidates",
        "",
    ]
    for candidate in payload["candidates"]:
        lines.append(
            f"- {candidate['profile_family']}: score={candidate['score']} confidence={candidate['confidence']} target={candidate['resource_arn']}"
        )
        lines.append(f"  reasons={candidate['selection_reason']}")
    lines.append("")
    return "\n".join(lines)
