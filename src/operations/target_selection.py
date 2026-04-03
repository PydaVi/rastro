from __future__ import annotations

import json
from pathlib import Path


KEYWORD_WEIGHTS = {
    "payroll": 40,
    "finance": 25,
    "prod": 20,
    "secret": 20,
    "token": 15,
    "api_key": 25,
    "password": 15,
    "backup": 10,
}

KEYWORD_PENALTIES = {
    "admin": 10,
    "public": 10,
    "bridge": 10,
    "audit": 10,
}


PROFILE_RULES = {
    "aws-iam-s3": {"resource_types": {"data_store.s3_bucket", "data_store.s3_object"}},
    "aws-iam-secrets": {"resource_types": {"secret.secrets_manager"}},
    "aws-iam-ssm": {"resource_types": {"secret.ssm_parameter"}},
    "aws-iam-role-chaining": {"resource_types": {"identity.role"}},
    "aws-iam-compute-iam": {"resource_types": {"identity.role"}},
    "aws-external-entry-data": {"resource_types": {"data_store.s3_object", "secret.secrets_manager", "secret.ssm_parameter"}},
    "aws-cross-account-data": {"resource_types": {"data_store.s3_object", "secret.secrets_manager", "secret.ssm_parameter"}},
    "aws-multi-step-data": {"resource_types": {"data_store.s3_object", "secret.secrets_manager", "secret.ssm_parameter"}},
    "aws-iam-lambda-data": {"resource_types": {"compute.lambda_function"}},
    "aws-iam-kms-data": {"resource_types": {"crypto.kms_key"}},
}

BUNDLE_RULES = {
    "aws-foundation": [
        "aws-iam-s3",
        "aws-iam-secrets",
        "aws-iam-ssm",
        "aws-iam-role-chaining",
    ],
    "aws-advanced": [
        "aws-iam-s3",
        "aws-iam-secrets",
        "aws-iam-ssm",
        "aws-iam-role-chaining",
        "aws-iam-compute-iam",
        "aws-external-entry-data",
        "aws-iam-lambda-data",
        "aws-iam-kms-data",
    ],
    "aws-enterprise": [
        "aws-iam-s3",
        "aws-iam-secrets",
        "aws-iam-ssm",
        "aws-iam-role-chaining",
        "aws-iam-compute-iam",
        "aws-external-entry-data",
        "aws-cross-account-data",
        "aws-multi-step-data",
        "aws-iam-lambda-data",
        "aws-iam-kms-data",
    ],
}


def select_foundation_targets(
    *,
    discovery_snapshot: dict,
    output_dir: Path,
    max_candidates_per_profile: int = 5,
    bundle_name: str | None = None,
) -> tuple[Path, Path, dict]:
    active_bundle = bundle_name or discovery_snapshot.get("bundle") or "aws-foundation"
    profile_names = BUNDLE_RULES.get(active_bundle, BUNDLE_RULES["aws-foundation"])
    candidates: list[dict] = []
    resources = discovery_snapshot.get("resources", [])
    structural_index = _build_structural_index(resources, discovery_snapshot.get("caller_identity", {}).get("Account"))
    for profile_name in profile_names:
        rule = PROFILE_RULES[profile_name]
        profile_candidates = []
        for resource in resources:
            if resource["resource_type"] not in rule["resource_types"]:
                continue
            candidate = _build_candidate(profile_name, resource, structural_index)
            if candidate is None:
                continue
            profile_candidates.append(candidate)
        profile_candidates.sort(key=lambda item: (-item["score"], item["resource_arn"]))
        candidates.extend(profile_candidates[:max_candidates_per_profile])

    summary = _build_candidate_summary(candidates)
    payload = {
        "target": discovery_snapshot.get("target"),
        "bundle": active_bundle,
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


def _build_candidate(profile_name: str, resource: dict, structural_index: dict) -> dict | None:
    identifier = resource["identifier"]
    searchable_text = _searchable_text(resource)
    lowered = searchable_text.lower()
    normalized = lowered.replace("-", "_").replace("/", "_")
    metadata = resource.get("metadata", {})
    candidate_profiles = metadata.get("candidate_profiles", [])
    inferred_profiles = _infer_candidate_profiles(resource, structural_index)
    active_profiles = candidate_profiles or inferred_profiles

    if active_profiles and profile_name not in active_profiles:
        return None

    if profile_name == "aws-iam-role-chaining" and lowered.endswith(("/rolea", "/roleb", "/rolem", "/roleq")):
        # low-confidence named lab roles are still useful chain candidates
        pass

    score = 10
    lexical_score = 0
    structural_score = 0
    reasons: list[str] = []
    signals: dict = {"keyword_hits": [], "service": resource["service"]}

    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in lowered or keyword in normalized:
            score += weight
            lexical_score += weight
            signals["keyword_hits"].append(keyword)
            reasons.append(f"keyword:{keyword}")

    for keyword, penalty in KEYWORD_PENALTIES.items():
        if keyword in lowered or keyword in normalized:
            score -= penalty
            lexical_score -= penalty
            reasons.append(f"penalty:{keyword}")

    if resource["resource_type"] == "data_store.s3_object":
        score += 15
        structural_score += 15
        reasons.append("object_level_target")
        if profile_name == "aws-iam-s3":
            score += 15
            structural_score += 15
            reasons.append("object_specific_signal")
    elif resource["resource_type"] == "secret.secrets_manager":
        score += 20
        structural_score += 20
        reasons.append("secret_surface")
    elif resource["resource_type"] == "secret.ssm_parameter":
        score += 20
        structural_score += 20
        reasons.append("parameter_surface")
    elif resource["resource_type"] == "identity.role":
        score += 5
        structural_score += 5
        reasons.append("role_chain_candidate")
        if profile_name == "aws-iam-compute-iam":
            role_profiles = structural_index["role_to_instance_profiles"].get(identifier, [])
            role_instances = structural_index["role_to_instances"].get(identifier, [])
            public_surfaces = structural_index["role_to_public_surfaces"].get(identifier, [])
            if not role_profiles and not role_instances:
                return None
            score += 30
            structural_score += 30
            reasons.append("compute_linked_role")
            signals["instance_profiles"] = role_profiles
            signals["instances"] = role_instances
            if role_profiles:
                score += 15
                structural_score += 15
                reasons.append("instance_profile_signal")
            if role_instances:
                score += 15
                structural_score += 15
                reasons.append("instance_signal")
            if public_surfaces:
                score += 10
                structural_score += 10
                reasons.append("public_compute_reachability")
                signals["public_surfaces"] = public_surfaces

    classification = metadata.get("classification")
    resource_account = _extract_account_id(identifier)
    if classification in {"restricted", "confidential"}:
        score += 20
        structural_score += 20
        reasons.append(f"classification:{classification}")

    if resource_account and structural_index["caller_account"] and resource_account != structural_index["caller_account"]:
        if profile_name in {"aws-iam-s3", "aws-iam-secrets", "aws-iam-ssm", "aws-iam-role-chaining", "aws-iam-compute-iam"}:
            score -= 25
            structural_score -= 25
            reasons.append("non_primary_account_penalty")

    if metadata.get("path_prefix") == "/prod":
        score += 10
        lexical_score += 10
        reasons.append("prod_path_prefix")
    if profile_name == "aws-iam-s3" and resource["resource_type"] == "data_store.s3_bucket":
        bucket_objects = structural_index["bucket_to_objects"].get(identifier, [])
        if bucket_objects:
            score -= 10
            structural_score -= 10
            reasons.append("bucket_contains_more_precise_object_targets")

    if profile_name == "aws-iam-role-chaining" and ("broker" in lowered or "broker" in normalized):
        score += 15
        structural_score += 15
        reasons.append("chain_broker_signal")
    if profile_name == "aws-iam-role-chaining" and ("dataaccess" in lowered or "dataaccess" in normalized):
        score += 25
        structural_score += 25
        reasons.append("data_access_signal")
    if profile_name == "aws-iam-role-chaining" and ("handler" in lowered or "handler" in normalized):
        score += 20
        structural_score += 20
        reasons.append("handler_runtime_signal")
    if profile_name == "aws-iam-role-chaining" and ("runtime" in lowered or "runtime" in normalized):
        score += 10
        structural_score += 10
        reasons.append("runtime_signal")
    if profile_name == "aws-iam-role-chaining" and ("audit" in lowered or "audit" in normalized):
        score -= 10
        structural_score -= 10
        reasons.append("audit_role_penalty")
    if profile_name == "aws-iam-role-chaining" and ("decrypt" in lowered or "decrypt" in normalized):
        score -= 15
        structural_score -= 15
        reasons.append("decrypt_role_penalty")
    if profile_name == "aws-iam-role-chaining" and ("public" in lowered or "public" in normalized):
        score -= 10
        structural_score -= 10
        reasons.append("public_role_penalty")
    if profile_name == "aws-iam-role-chaining":
        lambda_functions = structural_index["role_to_lambda_functions"].get(identifier, [])
        if lambda_functions:
            score += 10
            structural_score += 10
            reasons.append("lambda_runtime_link")
            signals["lambda_functions"] = lambda_functions
    if profile_name == "aws-iam-compute-iam" and metadata.get("tier") == "prod":
        score += 10
        structural_score += 10
        reasons.append("prod_compute_role")
    if profile_name == "aws-external-entry-data":
        reachable_roles = metadata.get("reachable_roles", [])
        if resource_account and structural_index["caller_account"] and resource_account != structural_index["caller_account"]:
            return None
        public_path_roles = []
        for role_arn in reachable_roles:
            if structural_index["role_to_public_surfaces"].get(role_arn):
                public_path_roles.append(role_arn)
        if not public_path_roles:
            return None
        score += 25
        structural_score += 25
        reasons.append("external_reachability_signal")
        signals["reachable_roles"] = reachable_roles
        signals["public_path_roles"] = public_path_roles
        public_role_score = sum(_role_quality_score(role_arn, structural_index) for role_arn in public_path_roles)
        if public_role_score:
            score += public_role_score
            structural_score += public_role_score
            reasons.append("public_role_quality_signal")
            signals["public_role_score"] = public_role_score
        if resource["resource_type"] == "data_store.s3_object":
            score += 15
            structural_score += 15
            reasons.append("external_data_object_signal")
        if metadata.get("classification") in {"restricted", "confidential"}:
            score += 10
            structural_score += 10
            reasons.append("external_sensitive_data")
    if profile_name == "aws-cross-account-data":
        reachable_roles = metadata.get("reachable_roles", [])
        if not resource_account or resource_account == structural_index["caller_account"]:
            return None
        cross_account_roles = [role for role in reachable_roles if _extract_account_id(role) == resource_account]
        if not cross_account_roles:
            return None
        score += 30
        structural_score += 30
        reasons.append("cross_account_target")
        reasons.append("cross_account_reachability")
        signals["reachable_roles"] = reachable_roles
        signals["cross_account_roles"] = cross_account_roles
        pivot_chain = metadata.get("pivot_chain", [])
        if pivot_chain:
            score += 10
            structural_score += 10
            reasons.append("pivot_chain_signal")
            signals["pivot_chain"] = pivot_chain
            if len(pivot_chain) <= 2:
                score += 15
                structural_score += 15
                reasons.append("direct_cross_account_chain")
            else:
                score -= 10
                structural_score -= 10
                reasons.append("deep_chain_not_primary_cross_account")
        if resource["resource_type"] == "data_store.s3_object":
            score += 25
            structural_score += 25
            reasons.append("cross_account_object_signal")
    if profile_name == "aws-multi-step-data":
        pivot_chain = metadata.get("pivot_chain", [])
        if len(pivot_chain) < 3:
            return None
        score += 25
        structural_score += 25
        reasons.append("multi_step_chain")
        signals["pivot_chain"] = pivot_chain
        if metadata.get("reachable_roles"):
            signals["reachable_roles"] = metadata["reachable_roles"]
        if resource["resource_type"] == "data_store.s3_object":
            score += 10
            structural_score += 10
            reasons.append("multi_step_object_signal")
        if _extract_account_id(identifier) and _extract_account_id(identifier) != structural_index["caller_account"]:
            score += 10
            structural_score += 10
            reasons.append("cross_account_depth_bonus")
    if profile_name == "aws-iam-secrets" and ("api_key" in lowered or "api_key" in normalized):
        score += 10
        lexical_score += 10
        reasons.append("api_key_signal")
    if profile_name == "aws-iam-secrets" and ("password" in lowered or "password" in normalized):
        score += 10
        lexical_score += 10
        reasons.append("password_signal")
    if profile_name == "aws-iam-secrets" and ("token" in lowered or "token" in normalized):
        score -= 5
        lexical_score -= 5
        reasons.append("token_penalty")
    if profile_name == "aws-iam-ssm" and ("api_key" in lowered or "api_key" in normalized):
        score += 10
        lexical_score += 10
        reasons.append("api_key_signal")
    if profile_name == "aws-iam-ssm" and ("token" in lowered or "token" in normalized):
        score -= 5
        lexical_score -= 5
        reasons.append("token_penalty")
    if profile_name == "aws-iam-lambda-data" and ("lambda" in lowered or "lambda" in normalized):
        score += 10
        structural_score += 10
        reasons.append("lambda_surface")
    if profile_name == "aws-iam-lambda-data" and ("handler" in lowered or "handler" in normalized):
        score += 15
        structural_score += 15
        reasons.append("handler_signal")
    if profile_name == "aws-iam-lambda-data" and ("payroll" in lowered or "payroll" in normalized):
        score += 15
        lexical_score += 15
        reasons.append("payroll_signal")
    if profile_name == "aws-iam-lambda-data" and ("admin" in lowered or "admin" in normalized):
        score -= 10
        lexical_score -= 10
        reasons.append("admin_penalty")
    if profile_name == "aws-iam-kms-data" and ("kms" in lowered or "kms" in normalized):
        score += 10
        structural_score += 10
        reasons.append("kms_surface")
    if profile_name == "aws-iam-kms-data" and ("payroll" in lowered or "payroll" in normalized):
        score += 15
        lexical_score += 15
        reasons.append("payroll_signal")
    if profile_name == "aws-iam-kms-data" and ("runtime" in lowered or "runtime" in normalized):
        score += 10
        structural_score += 10
        reasons.append("runtime_signal")
    semantic_tags = metadata.get("semantic_tags", [])
    if semantic_tags:
        matched_tags = [tag for tag in semantic_tags if tag in lowered]
        if matched_tags:
            score += 5 * len(matched_tags)
            structural_score += 5 * len(matched_tags)
            signals["semantic_tags"] = matched_tags
            reasons.append("semantic_tag_signal")
    chain_depth = metadata.get("chain_depth")
    if isinstance(chain_depth, int) and profile_name in {"aws-external-entry-data", "aws-cross-account-data", "aws-multi-step-data"}:
        score += min(chain_depth * 5, 20)
        structural_score += min(chain_depth * 5, 20)
        reasons.append("chain_depth_signal")
        signals["chain_depth"] = chain_depth
    if candidate_profiles:
        score += 5
        structural_score += 5
        reasons.append("explicit_profile_mapping")
        signals["candidate_profiles"] = candidate_profiles
    elif inferred_profiles:
        score += 3
        structural_score += 3
        reasons.append("inferred_profile_mapping")
        signals["inferred_profiles"] = inferred_profiles

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
        "score_components": {
            "lexical": lexical_score,
            "structural": structural_score,
        },
        "supporting_evidence": {
            "service": resource["service"],
            "region": resource["region"],
            "metadata": resource.get("metadata", {}),
        },
    }


def _searchable_text(resource: dict) -> str:
    metadata = resource.get("metadata", {})
    lexical_fields = [
        "name",
        "alias",
        "path_prefix",
        "classification",
        "service",
        "workload",
        "tier",
        "exposure",
        "object_key",
        "bucket",
    ]
    tokens = [resource["identifier"]]
    for field in lexical_fields:
        value = metadata.get(field)
        if isinstance(value, str):
            tokens.append(value)
    return " ".join(tokens)


def _build_structural_index(resources: list[dict], caller_account: str | None) -> dict:
    role_to_instance_profiles: dict[str, list[str]] = {}
    profile_to_instances: dict[str, list[str]] = {}
    instance_to_public_surfaces: dict[str, list[str]] = {}
    role_to_lambda_functions: dict[str, list[str]] = {}
    bucket_to_objects: dict[str, list[str]] = {}

    for resource in resources:
        metadata = resource.get("metadata", {})
        identifier = resource["identifier"]
        if resource["resource_type"] == "compute.instance_profile":
            role_arn = metadata.get("role")
            if role_arn:
                role_to_instance_profiles.setdefault(role_arn, []).append(identifier)
        if resource["resource_type"] == "compute.ec2_instance":
            profile_arn = metadata.get("instance_profile")
            if profile_arn:
                profile_to_instances.setdefault(profile_arn, []).append(identifier)
        if resource["resource_type"] in {"network.load_balancer", "network.api_gateway"}:
            if metadata.get("exposure") == "public":
                target_instance = metadata.get("target_instance")
                if target_instance:
                    instance_to_public_surfaces.setdefault(target_instance, []).append(identifier)
        if resource["resource_type"] == "compute.lambda_function":
            role_arn = metadata.get("role")
            if role_arn:
                role_to_lambda_functions.setdefault(role_arn, []).append(identifier)
        if resource["resource_type"] == "data_store.s3_object":
            bucket = metadata.get("bucket")
            if bucket:
                bucket_to_objects.setdefault(f"arn:aws:s3:::{bucket}", []).append(identifier)

    role_to_instances: dict[str, list[str]] = {}
    role_to_public_surfaces: dict[str, list[str]] = {}
    for role_arn, profiles in role_to_instance_profiles.items():
        for profile_arn in profiles:
            instances = profile_to_instances.get(profile_arn, [])
            if instances:
                role_to_instances.setdefault(role_arn, []).extend(instances)
            for instance_arn in instances:
                public_surfaces = instance_to_public_surfaces.get(instance_arn, [])
                if public_surfaces:
                    role_to_public_surfaces.setdefault(role_arn, []).extend(public_surfaces)

    return {
        "role_to_instance_profiles": {key: sorted(set(value)) for key, value in role_to_instance_profiles.items()},
        "role_to_instances": {key: sorted(set(value)) for key, value in role_to_instances.items()},
        "role_to_public_surfaces": {key: sorted(set(value)) for key, value in role_to_public_surfaces.items()},
        "role_to_lambda_functions": {key: sorted(set(value)) for key, value in role_to_lambda_functions.items()},
        "bucket_to_objects": {key: sorted(set(value)) for key, value in bucket_to_objects.items()},
        "caller_account": caller_account,
    }


def _infer_candidate_profiles(resource: dict, structural_index: dict) -> list[str]:
    metadata = resource.get("metadata", {})
    identifier = resource["identifier"]
    resource_type = resource["resource_type"]
    inferred: list[str] = []
    resource_account = _extract_account_id(identifier)

    if resource_type == "data_store.s3_object":
        inferred.append("aws-iam-s3")
    elif resource_type == "secret.secrets_manager":
        inferred.append("aws-iam-secrets")
    elif resource_type == "secret.ssm_parameter":
        inferred.append("aws-iam-ssm")
    elif resource_type == "compute.lambda_function":
        inferred.append("aws-iam-lambda-data")
    elif resource_type == "crypto.kms_key":
        inferred.append("aws-iam-kms-data")
    elif resource_type == "identity.role":
        inferred.append("aws-iam-role-chaining")
        if structural_index["role_to_instance_profiles"].get(identifier) or structural_index["role_to_instances"].get(identifier):
            inferred.append("aws-iam-compute-iam")

    reachable_roles = metadata.get("reachable_roles", [])
    if reachable_roles:
        public_path_roles = [
            role_arn for role_arn in reachable_roles if structural_index["role_to_public_surfaces"].get(role_arn)
        ]
        if public_path_roles:
            inferred.append("aws-external-entry-data")

        if resource_account and structural_index["caller_account"] and resource_account != structural_index["caller_account"]:
            cross_account_roles = [role for role in reachable_roles if _extract_account_id(role) == resource_account]
            if cross_account_roles:
                inferred.append("aws-cross-account-data")

    pivot_chain = metadata.get("pivot_chain", [])
    if len(pivot_chain) >= 3:
        inferred.append("aws-multi-step-data")

    if resource_type == "identity.role" and metadata.get("service") == "lambda":
        inferred.append("aws-iam-role-chaining")

    return sorted(set(inferred))


def _role_quality_score(role_arn: str, structural_index: dict) -> int:
    metadata = structural_index.get("role_metadata", {}).get(role_arn, {})
    role_text = f"{role_arn} {' '.join(str(v) for v in metadata.values() if isinstance(v, str))}".lower()
    role_text = role_text.replace("-", "_").replace("/", "_")
    score = 0
    if "payroll" in role_text:
        score += 5
    if "runtime" in role_text or "handler" in role_text or "compute" in role_text:
        score += 10
    if "prod" in role_text:
        score += 5
    if "legacy" in role_text:
        score -= 15
    if "audit" in role_text:
        score -= 15
    if "bridge" in role_text:
        score -= 10
    return score


def _build_candidate_summary(candidates: list[dict]) -> dict:
    by_profile: dict[str, int] = {}
    for candidate in candidates:
        by_profile[candidate["profile_family"]] = by_profile.get(candidate["profile_family"], 0) + 1
    return {
        "candidates_total": len(candidates),
        "by_profile": by_profile,
        "high_confidence": sum(1 for candidate in candidates if candidate["confidence"] == "high"),
    }


def _extract_account_id(resource_arn: str) -> str | None:
    if not resource_arn.startswith("arn:aws:"):
        return None
    parts = resource_arn.split(":")
    if len(parts) < 5:
        return None
    return parts[4] or None


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
