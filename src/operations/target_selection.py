from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from operations.synthetic_catalog import get_synthetic_profile


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
    structural_index = _build_structural_index(
        resources,
        discovery_snapshot.get("caller_identity", {}).get("Account"),
        discovery_snapshot.get("relationships", []),
        discovery_snapshot.get("target"),
    )
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
    execution_fixture_set = _infer_execution_fixture_set(resource, profile_name, structural_index)
    synthetic_profile = _resolve_synthetic_profile_definition(execution_fixture_set, profile_name)
    reachable_roles = _resolved_reachable_roles(resource, structural_index)
    pivot_chain = _resolved_pivot_chain(resource, structural_index, reachable_roles)
    chain_depth = _resolved_chain_depth(resource, reachable_roles, pivot_chain, structural_index)

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
        trust_principals = structural_index["role_trust_principals"].get(identifier, [])
        escalation_signals = structural_index["role_policy_escalation_signals"].get(identifier, [])
        if "*" in trust_principals:
            score += 20
            structural_score += 20
            reasons.append("broad_trust_signal")
            signals["trust_principals"] = trust_principals
        if escalation_signals:
            bonus = min(40, 10 + 5 * len(escalation_signals))
            score += bonus
            structural_score += bonus
            reasons.append("policy_escalation_signal")
            signals["policy_escalation_signals"] = escalation_signals
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
        external_entry_reachability = _infer_external_entry_reachability(public_path_roles, structural_index)
        signals["external_entry_reachability"] = external_entry_reachability
        if external_entry_reachability["network_reachable_from_internet"]["status"] == "proved":
            score += 10
            structural_score += 10
            reasons.append("network_reachability_proved")
        if external_entry_reachability["backend_reachable"]["status"] == "proved":
            score += 10
            structural_score += 10
            reasons.append("backend_reachability_proved")
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
                depth_penalty = 10 + ((len(pivot_chain) - 2) * 10)
                score -= depth_penalty
                structural_score -= depth_penalty
                reasons.append("deep_chain_not_primary_cross_account")
        if resource["resource_type"] == "data_store.s3_object":
            score += 25
            structural_score += 25
            reasons.append("cross_account_object_signal")
    if profile_name == "aws-multi-step-data":
        if len(pivot_chain) < 3:
            return None
        score += 25
        structural_score += 25
        reasons.append("multi_step_chain")
        signals["pivot_chain"] = pivot_chain
        if reachable_roles:
            signals["reachable_roles"] = reachable_roles
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
        "execution_fixture_set": execution_fixture_set,
        "fixture_path": str(synthetic_profile.fixture_path) if synthetic_profile else None,
        "scope_template_path": str(synthetic_profile.scope_path) if synthetic_profile else None,
        "supporting_evidence": {
            "service": resource["service"],
            "region": resource.get("region"),
            "metadata": resource.get("metadata", {}),
        },
        "external_entry_reachability": signals.get("external_entry_reachability"),
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


def _build_structural_index(
    resources: list[dict],
    caller_account: str | None,
    relationships: list[dict] | None = None,
    target_name: str | None = None,
) -> dict:
    relationships = relationships or []
    role_to_instance_profiles: dict[str, list[str]] = {}
    profile_to_instances: dict[str, list[str]] = {}
    instance_to_public_surfaces: dict[str, list[str]] = {}
    instance_metadata: dict[str, dict] = {}
    public_surface_metadata: dict[str, dict] = {}
    listener_metadata: dict[str, dict] = {}
    target_group_metadata: dict[str, dict] = {}
    api_integration_metadata: dict[str, dict] = {}
    subnet_to_route_tables: dict[str, list[str]] = {}
    route_table_to_internet_gateways: dict[str, list[str]] = {}
    instance_to_security_groups: dict[str, list[str]] = {}
    security_group_public_ingress: dict[str, list[int]] = {}
    load_balancer_to_listeners: dict[str, list[str]] = {}
    listener_to_target_groups: dict[str, list[str]] = {}
    api_gateway_to_integrations: dict[str, list[str]] = {}
    integration_to_instances: dict[str, list[str]] = {}
    integration_to_load_balancers: dict[str, list[str]] = {}
    role_to_lambda_functions: dict[str, list[str]] = {}
    role_trust_principals: dict[str, list[str]] = {}
    role_attached_policy_names: dict[str, list[str]] = {}
    role_inline_policy_names: dict[str, list[str]] = {}
    role_policy_escalation_signals: dict[str, list[str]] = {}
    bucket_to_objects: dict[str, list[str]] = {}
    role_metadata: dict[str, dict] = {}

    for resource in resources:
        metadata = resource.get("metadata", {})
        identifier = resource["identifier"]
        if resource["resource_type"] == "identity.role":
            role_metadata[identifier] = metadata
            role_trust_principals[identifier] = metadata.get("trust_principals", [])
            role_attached_policy_names[identifier] = metadata.get("attached_policy_names", [])
            role_inline_policy_names[identifier] = metadata.get("inline_policy_names", [])
            role_policy_escalation_signals[identifier] = _policy_escalation_signals(metadata)
        if resource["resource_type"] == "compute.instance_profile":
            role_arn = metadata.get("role")
            if role_arn:
                role_to_instance_profiles.setdefault(role_arn, []).append(identifier)
        if resource["resource_type"] == "compute.ec2_instance":
            instance_metadata[identifier] = metadata
            profile_arn = metadata.get("instance_profile")
            if profile_arn:
                profile_to_instances.setdefault(profile_arn, []).append(identifier)
        if resource["resource_type"] in {"network.load_balancer", "network.api_gateway"}:
            public_surface_metadata[identifier] = metadata
            if metadata.get("exposure", "public") == "public":
                target_instance = metadata.get("target_instance")
                if target_instance:
                    instance_to_public_surfaces.setdefault(target_instance, []).append(identifier)
        if resource["resource_type"] == "network.lb_listener":
            listener_metadata[identifier] = metadata
        if resource["resource_type"] == "network.target_group":
            target_group_metadata[identifier] = metadata
        if resource["resource_type"] == "network.api_integration":
            api_integration_metadata[identifier] = metadata
        if resource["resource_type"] == "network.route_table":
            for subnet_id in metadata.get("subnet_ids", []):
                subnet_to_route_tables.setdefault(subnet_id, []).append(identifier)
            for internet_gateway_id in metadata.get("internet_gateway_ids", []):
                route_table_to_internet_gateways.setdefault(identifier, []).append(internet_gateway_id)
        if resource["resource_type"] == "network.security_group":
            security_group_public_ingress[identifier] = metadata.get("public_ingress_ports", [])
        if resource["resource_type"] == "compute.lambda_function":
            role_arn = metadata.get("role")
            if role_arn:
                role_to_lambda_functions.setdefault(role_arn, []).append(identifier)
        if resource["resource_type"] == "data_store.s3_object":
            bucket = metadata.get("bucket")
            if bucket:
                bucket_to_objects.setdefault(f"arn:aws:s3:::{bucket}", []).append(identifier)

    role_to_accessible_resources: dict[str, list[str]] = {}
    role_to_assumable_roles: dict[str, list[str]] = {}
    resource_to_roles: dict[str, list[str]] = {}
    for relationship in relationships:
        source = relationship.get("source")
        target = relationship.get("target")
        rel_type = relationship.get("type") or relationship.get("relationship_type") or relationship.get("kind")
        if not source or not target or not rel_type:
            continue
        if rel_type in {"can_access", "can_read", "reads", "accesses"} and ":role/" in source:
            role_to_accessible_resources.setdefault(source, []).append(target)
            resource_to_roles.setdefault(target, []).append(source)
        if rel_type in {"can_assume", "assume_role", "assumes"} and ":role/" in source and ":role/" in target:
            role_to_assumable_roles.setdefault(source, []).append(target)
        if rel_type == "associated_with_route_table" and ":subnet/" in source and ":route-table/" in target:
            subnet_to_route_tables.setdefault(source.rsplit("/", 1)[-1], []).append(target)
        if rel_type == "routes_to_internet_gateway" and ":route-table/" in source:
            route_table_to_internet_gateways.setdefault(source, []).append(target)
        if rel_type == "protected_by_security_group" and ":instance/" in source and ":security-group/" in target:
            instance_to_security_groups.setdefault(source, []).append(target)
        if rel_type == "exposes_listener" and ":loadbalancer/" in source:
            load_balancer_to_listeners.setdefault(source, []).append(target)
        if rel_type == "forwards_to_target_group" and ":listener/" in source:
            listener_to_target_groups.setdefault(source, []).append(target)
        if rel_type == "uses_integration" and ":apigateway:" in source:
            api_gateway_to_integrations.setdefault(source, []).append(target)
        if rel_type == "integrates_with_instance" and "/integration/" in source:
            integration_to_instances.setdefault(source, []).append(target)
        if rel_type == "integrates_with_load_balancer" and "/integration/" in source:
            integration_to_load_balancers.setdefault(source, []).append(target)

    role_to_instances: dict[str, list[str]] = {}
    role_to_public_surfaces: dict[str, list[str]] = {}
    instance_network_maturity: dict[str, dict[str, object]] = {}
    for instance_arn, metadata in instance_metadata.items():
        subnet_id = metadata.get("subnet_id")
        route_tables = subnet_to_route_tables.get(subnet_id, [])
        security_groups = instance_to_security_groups.get(instance_arn, [])
        if not security_groups:
            security_groups = [
                _as_ec2_resource_arn(caller_account, group_id, "security-group")
                for group_id in metadata.get("security_group_ids", [])
            ]
        has_internet_route = any(route_table_to_internet_gateways.get(route_table) for route_table in route_tables)
        has_public_ingress = any(security_group_public_ingress.get(group_arn) for group_arn in security_groups)
        explicit_public_exposure = bool(metadata.get("public_ip")) or str(metadata.get("exposure", "")).startswith("public")
        network_status = "not_observed"
        backend_status = "not_observed"
        if explicit_public_exposure:
            network_status = "structural"
            backend_status = "structural"
        if metadata.get("public_ip") and has_internet_route and has_public_ingress:
            network_status = "proved"
            backend_status = "proved"
            instance_to_public_surfaces.setdefault(instance_arn, []).append(instance_arn)
        elif str(metadata.get("exposure", "")).startswith("public"):
            instance_to_public_surfaces.setdefault(instance_arn, []).append(instance_arn)
        if instance_to_public_surfaces.get(instance_arn):
            if network_status == "not_observed":
                network_status = "structural"
            if backend_status == "not_observed":
                backend_status = "structural"
        instance_network_maturity[instance_arn] = {
            "network_reachable_from_internet": network_status,
            "backend_reachable": backend_status,
            "public_surfaces": sorted(set(instance_to_public_surfaces.get(instance_arn, []))),
            "security_groups": sorted(set(security_groups)),
            "route_tables": sorted(set(route_tables)),
        }

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
        "role_trust_principals": role_trust_principals,
        "role_attached_policy_names": role_attached_policy_names,
        "role_inline_policy_names": role_inline_policy_names,
        "role_policy_escalation_signals": role_policy_escalation_signals,
        "bucket_to_objects": {key: sorted(set(value)) for key, value in bucket_to_objects.items()},
        "role_to_accessible_resources": {key: sorted(set(value)) for key, value in role_to_accessible_resources.items()},
        "resource_to_roles": {key: sorted(set(value)) for key, value in resource_to_roles.items()},
        "role_to_assumable_roles": {key: sorted(set(value)) for key, value in role_to_assumable_roles.items()},
        "public_root_roles": sorted(role_to_public_surfaces.keys()),
        "public_surface_metadata": public_surface_metadata,
        "listener_metadata": listener_metadata,
        "target_group_metadata": target_group_metadata,
        "api_integration_metadata": api_integration_metadata,
        "load_balancer_to_listeners": {key: sorted(set(value)) for key, value in load_balancer_to_listeners.items()},
        "listener_to_target_groups": {key: sorted(set(value)) for key, value in listener_to_target_groups.items()},
        "api_gateway_to_integrations": {key: sorted(set(value)) for key, value in api_gateway_to_integrations.items()},
        "integration_to_instances": {key: sorted(set(value)) for key, value in integration_to_instances.items()},
        "integration_to_load_balancers": {key: sorted(set(value)) for key, value in integration_to_load_balancers.items()},
        "role_metadata": role_metadata,
        "instance_network_maturity": instance_network_maturity,
        "caller_account": caller_account,
        "target_name": target_name,
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

    reachable_roles = _resolved_reachable_roles(resource, structural_index)
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

    pivot_chain = _resolved_pivot_chain(resource, structural_index, reachable_roles)
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
    if structural_index.get("role_policy_escalation_signals", {}).get(role_arn):
        score += 15
    if "*" in structural_index.get("role_trust_principals", {}).get(role_arn, []):
        score += 10
    return score


def _policy_escalation_signals(metadata: dict) -> list[str]:
    haystack = " ".join(
        [
            *metadata.get("attached_policy_names", []),
            *metadata.get("attached_policy_arns", []),
            *metadata.get("inline_policy_names", []),
        ]
    ).lower()
    markers = [
        "administratoraccess",
        "createpolicyversion",
        "setdefaultpolicyversion",
        "attachrolepolicy",
        "attachuserpolicy",
        "putrolepolicy",
        "putuserpolicy",
        "updateassumerolepolicy",
        "passrole",
        "addusertogroup",
        "createaccesskey",
        "cloudformation",
        "codebuild",
        "sagemaker",
        "iamfullaccess",
    ]
    return sorted({marker for marker in markers if marker in haystack})


def _infer_execution_fixture_set(resource: dict, profile_name: str, structural_index: dict) -> str:
    target_name = (structural_index.get("target_name") or "").lower()
    if target_name.startswith("serverless-business-app"):
        return "serverless-business-app"
    if target_name.startswith("compute-pivot-app"):
        return "compute-pivot-app"
    if target_name.startswith("internal-data-platform"):
        return "internal-data-platform"

    metadata = resource.get("metadata", {})
    resource_type = resource["resource_type"]
    identifier = resource["identifier"]
    resource_account = _extract_account_id(identifier)
    caller_account = structural_index["caller_account"]
    reachable_roles = _resolved_reachable_roles(resource, structural_index)
    has_public_compute = any(structural_index["role_to_public_surfaces"].get(role_arn) for role_arn in reachable_roles)
    has_compute_role = any(
        structural_index["role_to_instance_profiles"].get(role_arn) or structural_index["role_to_instances"].get(role_arn)
        for role_arn in reachable_roles
    )
    has_lambda_role = any(structural_index["role_to_lambda_functions"].get(role_arn) for role_arn in reachable_roles)
    pivot_chain = _resolved_pivot_chain(resource, structural_index, reachable_roles)
    chain_depth = _resolved_chain_depth(resource, reachable_roles, pivot_chain, structural_index) or 0

    if resource_type == "compute.lambda_function" or profile_name == "aws-iam-lambda-data":
        return "serverless-business-app"
    if resource_type == "crypto.kms_key" or profile_name == "aws-iam-kms-data":
        return "serverless-business-app"
    if resource_account and caller_account and resource_account != caller_account:
        return "mixed-generalization"
    if chain_depth >= 3 and profile_name in {"aws-multi-step-data", "aws-cross-account-data"}:
        return "mixed-generalization"
    if profile_name == "aws-external-entry-data" and has_public_compute:
        return "compute-pivot-app"
    if profile_name == "aws-iam-compute-iam" and resource_type == "identity.role":
        role_profiles = structural_index["role_to_instance_profiles"].get(identifier, [])
        role_instances = structural_index["role_to_instances"].get(identifier, [])
        if role_profiles or role_instances:
            return "compute-pivot-app"

    if profile_name == "aws-iam-role-chaining":
        if structural_index["role_to_lambda_functions"].get(identifier):
            return "serverless-business-app"
        if structural_index["role_to_instance_profiles"].get(identifier) or structural_index["role_to_instances"].get(identifier):
            return "compute-pivot-app"
        return "mixed-generalization"

    if profile_name in {"aws-iam-s3", "aws-iam-secrets", "aws-iam-ssm"}:
        if profile_name == "aws-iam-s3":
            return "mixed-generalization"
        if has_public_compute or has_compute_role:
            return "compute-pivot-app"
        if has_lambda_role:
            return "serverless-business-app"
        return "mixed-generalization"

    return "mixed-generalization"


def _resolve_synthetic_profile_definition(profile_set: str, profile_name: str):
    try:
        return get_synthetic_profile(profile_set, profile_name)
    except KeyError:
        return None


def _resolved_reachable_roles(resource: dict, structural_index: dict) -> list[str]:
    metadata = resource.get("metadata", {})
    reachable_roles = metadata.get("reachable_roles")
    if reachable_roles:
        return sorted(set(reachable_roles))
    return structural_index["resource_to_roles"].get(resource["identifier"], [])


def _resolved_pivot_chain(resource: dict, structural_index: dict, reachable_roles: list[str]) -> list[str]:
    metadata = resource.get("metadata", {})
    if metadata.get("pivot_chain"):
        return metadata["pivot_chain"]
    if not reachable_roles:
        return []
    public_roots = structural_index.get("public_root_roles", [])
    if not public_roots:
        return []
    best_path: list[str] = []
    for target_role in reachable_roles:
        path = _find_shortest_role_path(public_roots, target_role, structural_index.get("role_to_assumable_roles", {}))
        if path and (not best_path or len(path) < len(best_path)):
            best_path = path
    return best_path


def _resolved_chain_depth(resource: dict, reachable_roles: list[str], pivot_chain: list[str], structural_index: dict) -> int | None:
    metadata = resource.get("metadata", {})
    chain_depth = metadata.get("chain_depth")
    if isinstance(chain_depth, int):
        return chain_depth
    if pivot_chain:
        return len(pivot_chain)
    if reachable_roles:
        public_path_roles = [role for role in reachable_roles if structural_index["role_to_public_surfaces"].get(role)]
        if public_path_roles:
            return 2
    return None


def _find_shortest_role_path(start_roles: list[str], target_role: str, adjacency: dict[str, list[str]]) -> list[str]:
    queue: deque[tuple[str, list[str]]] = deque()
    visited: set[str] = set()
    for role in start_roles:
        queue.append((role, [role]))
    while queue:
        current, path = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        if current == target_role:
            return path
        for next_role in adjacency.get(current, []):
            if next_role not in visited:
                queue.append((next_role, [*path, next_role]))
    return []


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


def _as_ec2_resource_arn(account_id: str | None, resource_id: str, resource_type: str) -> str:
    if resource_id.startswith("arn:aws:"):
        return resource_id
    if not account_id:
        return resource_id
    return f"arn:aws:ec2:us-east-1:{account_id}:{resource_type}/{resource_id}"


def _infer_external_entry_reachability(public_path_roles: list[str], structural_index: dict) -> dict:
    network_status = "not_observed"
    backend_status = "not_observed"
    instances: list[str] = []
    public_surfaces: list[str] = []
    for role_arn in public_path_roles:
        role_surfaces = structural_index["role_to_public_surfaces"].get(role_arn, [])
        for surface_arn in role_surfaces:
            surface_status = _public_surface_reachability(surface_arn, structural_index)
            if surface_status["network_reachable_from_internet"] == "proved":
                network_status = "proved"
            elif network_status == "not_observed" and surface_status["network_reachable_from_internet"] == "structural":
                network_status = "structural"
            if surface_status["backend_reachable"] == "proved":
                backend_status = "proved"
            elif backend_status == "not_observed" and surface_status["backend_reachable"] == "structural":
                backend_status = "structural"
            public_surfaces.append(surface_arn)
        for instance_arn in structural_index["role_to_instances"].get(role_arn, []):
            maturity = structural_index.get("instance_network_maturity", {}).get(instance_arn, {})
            instance_network = maturity.get("network_reachable_from_internet")
            instance_backend = maturity.get("backend_reachable")
            if instance_network == "proved":
                network_status = "proved"
            elif network_status == "not_observed" and instance_network == "structural":
                network_status = "structural"
            if instance_backend == "proved":
                backend_status = "proved"
            elif backend_status == "not_observed" and instance_backend == "structural":
                backend_status = "structural"
            instances.append(instance_arn)
            public_surfaces.extend(maturity.get("public_surfaces", []))
        if structural_index["role_to_public_surfaces"].get(role_arn) and network_status == "not_observed":
            network_status = "structural"
            backend_status = "structural"
            public_surfaces.extend(structural_index["role_to_public_surfaces"].get(role_arn, []))
    return {
        "network_reachable_from_internet": {
            "status": network_status,
            "evidence": sorted(set(public_surfaces)),
        },
        "backend_reachable": {
            "status": backend_status,
            "evidence": sorted(set(instances)),
        },
        "credential_acquisition_possible": {
            "status": "structural" if public_path_roles else "not_observed",
            "evidence": sorted(set(public_path_roles)),
        },
        "data_path_exploitable": {
            "status": "not_observed",
            "evidence": None,
        },
    }


def _public_surface_reachability(surface_arn: str, structural_index: dict) -> dict[str, str]:
    metadata = structural_index.get("public_surface_metadata", {}).get(surface_arn, {})
    network_status = "not_observed"
    backend_status = "not_observed"

    if metadata.get("exposure") == "public":
        network_status = "structural"
        backend_status = "structural"

    if metadata.get("network_reachable_from_internet") is True:
        network_status = "proved"
    elif metadata.get("exposure") == "public" and any(
        metadata.get(field)
        for field in ("dns_public", "public_stage", "internet_facing", "listener_public")
    ):
        network_status = "proved"

    if metadata.get("backend_reachable") is True:
        backend_status = "proved"
    elif metadata.get("target_health") == "healthy":
        backend_status = "proved"
    elif metadata.get("integration_status") in {"active", "reachable"}:
        backend_status = "proved"
    elif metadata.get("listener_forwarding") is True and metadata.get("target_instance"):
        backend_status = "proved"

    if ":loadbalancer/" in surface_arn:
        listeners = structural_index.get("load_balancer_to_listeners", {}).get(surface_arn, [])
        if listeners:
            network_status = "proved" if network_status != "not_observed" else "structural"
        for listener_arn in listeners:
            listener = structural_index.get("listener_metadata", {}).get(listener_arn, {})
            if listener.get("listener_public"):
                network_status = "proved"
            if listener.get("listener_forwarding"):
                backend_status = "proved" if structural_index.get("listener_to_target_groups", {}).get(listener_arn) else backend_status
    if ":apigateway:" in surface_arn:
        integrations = structural_index.get("api_gateway_to_integrations", {}).get(surface_arn, [])
        if integrations and metadata.get("public_stage"):
            network_status = "proved"
        for integration_arn in integrations:
            integration = structural_index.get("api_integration_metadata", {}).get(integration_arn, {})
            if integration.get("integration_status") == "active":
                backend_status = "proved"
            if structural_index.get("integration_to_instances", {}).get(integration_arn) or structural_index.get("integration_to_load_balancers", {}).get(integration_arn):
                backend_status = "proved"

    return {
        "network_reachable_from_internet": network_status,
        "backend_reachable": backend_status,
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
        if candidate.get("external_entry_reachability"):
            reachability = candidate["external_entry_reachability"]
            lines.append(
                "  external_entry_reachability="
                f"network={reachability['network_reachable_from_internet']['status']}, "
                f"backend={reachability['backend_reachable']['status']}, "
                f"credentials={reachability['credential_acquisition_possible']['status']}"
            )
    lines.append("")
    return "\n".join(lines)
