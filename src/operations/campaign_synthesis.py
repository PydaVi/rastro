from __future__ import annotations

import json
import re
from pathlib import Path

from core.domain import Objective
from operations.catalog import get_profile
from operations.models import AuthorizationConfig, TargetConfig
from operations.service import (
    build_campaign_scope,
    build_campaign_scope_from_path,
    validate_profile_access,
    validate_target,
)


def synthesize_foundation_campaigns(
    *,
    candidates_payload: dict,
    target: TargetConfig,
    authorization: AuthorizationConfig,
    output_dir: Path,
    max_plans_per_profile: int = 1,
    dedupe_resource_targets: bool = False,
    profile_resolver=None,
) -> tuple[Path, Path, dict]:
    profile_resolver = profile_resolver or get_profile
    issues = validate_target(target)
    if issues:
        raise ValueError("; ".join(issues))

    grouped: dict[str, list[dict]] = {}
    for candidate in candidates_payload.get("candidates", []):
        grouped.setdefault(candidate["profile_family"], []).append(candidate)

    grouped_plans: list[dict] = []
    generated_dir = output_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    for profile_name, candidates in grouped.items():
        validate_profile_access(profile_name, authorization)
        ordered = sorted(candidates, key=lambda item: (-item["score"], item["resource_arn"]))

        for candidate in ordered[:max_plans_per_profile]:
            fixture_path = candidate.get("fixture_path")
            scope_template_path = candidate.get("scope_template_path")
            if scope_template_path:
                base_scope = build_campaign_scope_from_path(Path(scope_template_path), target, authorization)
            else:
                profile = _resolve_profile(profile_resolver, profile_name, candidate)
                base_scope = build_campaign_scope(profile, target, authorization)
                fixture_path = fixture_path or str(profile.fixture_path)
            candidate_slug = _slugify(candidate["resource_arn"])
            candidate_dir = generated_dir / profile_name / candidate_slug
            candidate_dir.mkdir(parents=True, exist_ok=True)

            objective = Objective(
                description=_build_generated_objective_description(profile_name, candidate),
                target=candidate["resource_arn"],
                success_criteria=_build_generated_success_criteria(candidate),
            )

            scope_data = base_scope.model_dump()
            allowed_resources = list(scope_data["allowed_resources"])
            if candidate["resource_arn"] not in allowed_resources:
                allowed_resources.append(candidate["resource_arn"])
            scope_data["allowed_resources"] = sorted(set(allowed_resources))
            scope_data["aws_account_ids"] = _merge_account_ids(
                scope_data.get("aws_account_ids", []),
                scope_data["allowed_resources"],
                candidate["resource_arn"],
            )
            scope_data["allowed_regions"] = _merge_regions(
                scope_data.get("allowed_regions", []),
                scope_data["allowed_resources"],
                candidate["resource_arn"],
            )
            scope = base_scope.model_validate(scope_data)

            objective_path = candidate_dir / "objective.generated.json"
            scope_path = candidate_dir / "scope.generated.json"
            objective_path.write_text(json.dumps(objective.model_dump(), indent=2))
            scope_path.write_text(json.dumps(scope.model_dump(), indent=2))

            grouped_plans.append(
                {
                    "id": f"{profile_name}:{candidate_slug}",
                    "profile": profile_name,
                    "target_candidate_id": candidate["id"],
                    "resource_arn": candidate["resource_arn"],
                    "priority": _priority_for_score(candidate["score"]),
                    "planned_services": scope.allowed_services,
                    "fixture_path": fixture_path,
                    "generated_objective": str(objective_path),
                    "generated_scope": str(scope_path),
                    "confidence": candidate["confidence"],
                    "score": candidate["score"],
                    "score_components": candidate.get("score_components", {}),
                    "execution_fixture_set": candidate.get("execution_fixture_set"),
                    "external_entry_reachability": candidate.get("external_entry_reachability"),
                }
            )

    plans = _dedupe_plans_by_resource(grouped_plans) if dedupe_resource_targets else grouped_plans

    payload = {
        "target": target.name,
        "bundle": candidates_payload.get("bundle"),
        "derived_from": "target_candidates.json",
        "summary": {
            "plans_total": len(plans),
            "by_profile": _count_by_profile(plans),
        },
        "plans": plans,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "campaign_plan.json"
    md_path = output_dir / "campaign_plan.md"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_render_campaign_plan_markdown(payload))
    return json_path, md_path, payload


def _priority_for_score(score: int) -> str:
    if score >= 90:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _build_generated_objective_description(profile_name: str, candidate: dict) -> str:
    return f"Auto-generated campaign for {profile_name} against {candidate['resource_arn']}"


def _build_generated_success_criteria(candidate: dict) -> dict:
    profile_family = candidate.get("profile_family")
    if profile_family in {"aws-iam-s3", "aws-iam-secrets", "aws-iam-ssm"}:
        mode = "access_proved"
    elif profile_family == "aws-iam-role-chaining":
        mode = "assume_role_proved"
    elif profile_family in {
        "aws-iam-create-policy-version-privesc",
        "aws-iam-attach-role-policy-privesc",
        "aws-iam-pass-role-privesc",
    }:
        mode = "policy_probe_proved"
    else:
        mode = "target_observed"
    criteria = {
        "target_candidate_id": candidate["id"],
        "mode": mode,
    }
    required_tool_by_profile = {
        "aws-iam-create-policy-version-privesc": "iam_create_policy_version",
        "aws-iam-attach-role-policy-privesc": "iam_attach_role_policy",
        "aws-iam-pass-role-privesc": "iam_pass_role_service_create",
    }
    required_tool = required_tool_by_profile.get(profile_family)
    if required_tool:
        criteria["required_tool"] = required_tool
    return criteria


def _resolve_profile(profile_resolver, profile_name: str, candidate: dict):
    try:
        return profile_resolver(profile_name, candidate)
    except TypeError:
        return profile_resolver(profile_name)


def _dedupe_plans_by_resource(plans: list[dict]) -> list[dict]:
    by_resource: dict[str, list[dict]] = {}
    for plan in plans:
        by_resource.setdefault(plan["resource_arn"], []).append(plan)

    selected: list[dict] = []
    for resource_arn, resource_plans in by_resource.items():
        ordered = sorted(
            resource_plans,
            key=lambda item: (
                -item["score"],
                -item.get("score_components", {}).get("structural", 0),
                _profile_specificity_rank(item["profile"]),
                item["profile"],
                resource_arn,
            ),
        )
        selected.append(ordered[0])
    selected.sort(key=lambda item: (-item["score"], item["profile"], item["resource_arn"]))
    return selected


def _profile_specificity_rank(profile_name: str) -> int:
    ranks = {
        "aws-multi-step-data": 0,
        "aws-cross-account-data": 1,
        "aws-external-entry-data": 2,
        "aws-iam-compute-iam": 3,
        "aws-iam-lambda-data": 4,
        "aws-iam-kms-data": 5,
        "aws-iam-role-chaining": 6,
        "aws-iam-secrets": 7,
        "aws-iam-ssm": 8,
        "aws-iam-s3": 9,
    }
    return ranks.get(profile_name, 50)


def _count_by_profile(plans: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for plan in plans:
        counts[plan["profile"]] = counts.get(plan["profile"], 0) + 1
    return counts


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80]


def _render_campaign_plan_markdown(payload: dict) -> str:
    lines = [
        "# Campaign Plan",
        "",
        f"- Target: {payload['target']}",
        f"- Bundle: {payload['bundle']}",
        f"- Plans total: {payload['summary']['plans_total']}",
        "",
        "## Plans",
        "",
    ]
    for plan in payload["plans"]:
        lines.append(
            f"- {plan['profile']}: priority={plan['priority']} confidence={plan['confidence']} target={plan['resource_arn']}"
        )
        lines.append(f"  objective={plan['generated_objective']}")
        lines.append(f"  scope={plan['generated_scope']}")
        if plan.get("external_entry_reachability"):
            reachability = plan["external_entry_reachability"]
            lines.append(
                "  external_entry_reachability="
                f"network={reachability['network_reachable_from_internet']['status']}, "
                f"backend={reachability['backend_reachable']['status']}, "
                f"credentials={reachability['credential_acquisition_possible']['status']}"
            )
    lines.append("")
    return "\n".join(lines)


def _merge_account_ids(
    configured_accounts: list[str],
    allowed_resources: list[str],
    candidate_resource: str,
) -> list[str]:
    accounts = set(configured_accounts)
    for resource in [*allowed_resources, candidate_resource]:
        account_id = _extract_account_id(resource)
        if account_id:
            accounts.add(account_id)
    return sorted(accounts)


def _merge_regions(
    configured_regions: list[str],
    allowed_resources: list[str],
    candidate_resource: str,
) -> list[str]:
    regions = set(configured_regions)
    for resource in [*allowed_resources, candidate_resource]:
        region = _extract_region(resource)
        if region:
            regions.add(region)
    return sorted(regions)


def _extract_account_id(resource_arn: str) -> str | None:
    if not resource_arn.startswith("arn:aws:"):
        return None
    parts = resource_arn.split(":")
    if len(parts) < 5:
        return None
    return parts[4] or None


def _extract_region(resource_arn: str) -> str | None:
    if not resource_arn.startswith("arn:aws:"):
        return None
    parts = resource_arn.split(":")
    if len(parts) < 4:
        return None
    return parts[3] or None
