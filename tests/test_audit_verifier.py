"""Bloco 15 — testes do auditor offline independente. Arquivo próprio, mesma
disciplina de test_policy_evaluator.py / test_graph_diff.py / test_remediation.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from operations.audit_verifier import audit_assessment, audit_campaign


def _base_report(**overrides) -> dict:
    report = {
        "objective": {
            "target": "arn:aws:iam::123:role/AdminRole",
            "success_criteria": {"mode": "assume_role_proved"},
        },
        "execution_policy": {"allowed_services": ["iam", "sts", "s3"]},
        "steps": [],
        "objective_met": False,
    }
    report.update(overrides)
    return report


def _step(tool, actor, target, action_type, service, success=True) -> dict:
    return {
        "action": {
            "action_type": action_type,
            "actor": actor,
            "target": target,
            "tool": tool,
            "parameters": {"service": service},
        },
        "observation": {"success": success, "details": {}},
    }


# ---------------------------------------------------------------------------
# scope_respected
# ---------------------------------------------------------------------------

def test_scope_respected_when_all_steps_in_allowed_services():
    report = _base_report(steps=[
        _step("s3_read_sensitive", "arn:x", "arn:y", "access_resource", "s3"),
    ])
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.scope_respected
    assert result.out_of_scope_steps == []


def test_scope_violation_detected_even_if_step_failed():
    """O passo pode ter falhado (bloqueado a jusante) — a violação de escopo
    em si já é o que o auditor precisa flagrar, não só sucesso indevido."""
    report = _base_report(steps=[
        _step("secretsmanager_read_secret", "arn:x", "arn:y", "access_resource", "secretsmanager", success=False),
    ])
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert not result.scope_respected
    assert len(result.out_of_scope_steps) == 1
    assert not result.passed


# ---------------------------------------------------------------------------
# objective_claim_grounded
# ---------------------------------------------------------------------------

def test_objective_claim_none_when_objective_not_met():
    report = _base_report(objective_met=False, steps=[])
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.objective_claim_grounded is None
    assert result.passed  # None não reprova


def test_objective_claim_grounded_true_for_assume_role_proved():
    report = _base_report(objective_met=True, steps=[
        _step("iam_passrole", "arn:x", "arn:aws:iam::123:role/AdminRole", "assume_role", "iam"),
    ])
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.objective_claim_grounded is True


def test_objective_claim_grounded_false_when_no_step_supports_it():
    """objective_met=True mas nenhum step realmente prova — a alegação não é fundamentada."""
    report = _base_report(objective_met=True, steps=[
        _step("iam_list_roles", "arn:x", None, "enumerate", "iam"),
    ])
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.objective_claim_grounded is False
    assert not result.passed


def test_objective_claim_grounded_for_policy_mutation_proved():
    report = _base_report(
        objective_met=True,
        objective={
            "target": "arn:aws:iam::123:role/AdminRole",
            "success_criteria": {"mode": "policy_mutation_proved", "required_tool": "iam_attach_role_policy_mutate"},
        },
        steps=[_step("iam_attach_role_policy_mutate", "arn:x", "arn:aws:iam::123:role/AdminRole", "access_resource", "iam")],
    )
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.objective_claim_grounded is True


def test_objective_claim_grounded_for_access_proved():
    report = _base_report(
        objective_met=True,
        objective={"target": "arn:aws:s3:::bucket/key", "success_criteria": {"mode": "access_proved"}},
        steps=[_step("s3_read_sensitive", "arn:x", "arn:aws:s3:::bucket/key", "access_resource", "s3")],
    )
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.objective_claim_grounded is True


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

def test_rollback_ok_when_no_mutation_happened():
    report = _base_report(steps=[_step("s3_read_sensitive", "arn:x", "arn:y", "access_resource", "s3")])
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.rollback_attempted_when_needed
    assert result.missing_rollback_tools == []


def test_rollback_ok_when_mutation_succeeded_and_rollback_event_present():
    report = _base_report(steps=[
        _step("iam_attach_role_policy_mutate", "arn:x", "arn:aws:iam::123:role/AdminRole", "access_resource", "iam"),
    ])
    events = [{"event": "run_start"}, {"event": "action_executed"}, {"event": "rollback_executed", "payload": {}}]
    result = audit_campaign(profile="p", report=report, audit_events=events, findings=None, discovery_snapshot=None, output_dir="d")
    assert result.rollback_attempted_when_needed


def test_rollback_missing_when_mutation_succeeded_without_rollback_event():
    report = _base_report(steps=[
        _step("iam_create_access_key", "arn:x", "arn:aws:iam::123:user/bot", "access_resource", "iam"),
    ])
    result = audit_campaign(profile="p", report=report, audit_events=[{"event": "run_complete"}], findings=None, discovery_snapshot=None, output_dir="d")
    assert not result.rollback_attempted_when_needed
    assert result.missing_rollback_tools == ["iam_create_access_key"]
    assert not result.passed


def test_rollback_ignores_failed_mutation_attempt():
    """Mutacao que FALHOU nao exige rollback — nada foi mutado de verdade."""
    report = _base_report(steps=[
        _step("iam_attach_role_policy_mutate", "arn:x", "arn:y", "access_resource", "iam", success=False),
    ])
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=None, discovery_snapshot=None, output_dir="d")
    assert result.rollback_attempted_when_needed


# ---------------------------------------------------------------------------
# evaluation_tier_consistent
# ---------------------------------------------------------------------------

def _discovery_with_policy(actor: str, target: str, action: str) -> dict:
    return {
        "resources": [
            {
                "resource_type": "identity.user", "identifier": actor,
                "metadata": {"policy_permissions": [{"source": "p", "statements": [
                    {"Effect": "Allow", "Action": action, "Resource": target},
                ]}]},
            },
        ],
    }


def test_evaluation_tier_none_without_discovery_snapshot():
    report = _base_report(steps=[_step("iam_passrole", "arn:x", "arn:aws:iam::123:role/AdminRole", "assume_role", "iam")])
    findings = [{"profile": "p", "target_resource": "arn:aws:iam::123:role/AdminRole", "evaluation_tier": "evaluated"}]
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=findings, discovery_snapshot=None, output_dir="d")
    assert result.evaluation_tier_claimed == "evaluated"
    assert result.evaluation_tier_reproduced is None
    assert result.evaluation_tier_consistent is None
    assert result.passed  # None nao reprova


def test_evaluation_tier_consistent_when_claim_matches_reproduction():
    actor = "arn:aws:iam::123:user/u"
    target = "arn:aws:iam::123:role/AdminRole"
    report = _base_report(steps=[_step("iam_passrole", actor, target, "assume_role", "iam")])
    findings = [{"profile": "p", "target_resource": target, "evaluation_tier": "evaluated"}]
    discovery = _discovery_with_policy(actor, target, "sts:AssumeRole")
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=findings, discovery_snapshot=discovery, output_dir="d")
    assert result.evaluation_tier_reproduced == "evaluated"
    assert result.evaluation_tier_consistent is True


def test_evaluation_tier_inconsistent_when_claim_overstates_reproduction():
    """Finding alega "evaluated" mas o discovery.json nao sustenta isso -> flagra inconsistencia."""
    actor = "arn:aws:iam::123:user/u"
    target = "arn:aws:iam::123:role/AdminRole"
    report = _base_report(steps=[_step("iam_passrole", actor, target, "assume_role", "iam")])
    findings = [{"profile": "p", "target_resource": target, "evaluation_tier": "evaluated"}]
    discovery = {"resources": [{"resource_type": "identity.user", "identifier": actor, "metadata": {}}]}
    result = audit_campaign(profile="p", report=report, audit_events=[], findings=findings, discovery_snapshot=discovery, output_dir="d")
    assert result.evaluation_tier_reproduced == "structural"
    assert result.evaluation_tier_consistent is False
    assert not result.passed


# ---------------------------------------------------------------------------
# audit_assessment — ponta a ponta lendo arquivos de disco
# ---------------------------------------------------------------------------

def test_audit_assessment_reads_real_directory_layout(tmp_path: Path) -> None:
    actor = "arn:aws:iam::123:user/u"
    target = "arn:aws:iam::123:role/AdminRole"

    campaign_dir = tmp_path / "campaigns" / "aws-iam-role-chaining" / "run1"
    campaign_dir.mkdir(parents=True)
    report = _base_report(objective_met=True, steps=[
        _step("iam_passrole", actor, target, "assume_role", "iam"),
    ])
    (campaign_dir / "report.json").write_text(json.dumps(report))
    (campaign_dir / "audit.jsonl").write_text("\n".join([
        json.dumps({"event": "run_start"}),
        json.dumps({"event": "run_complete"}),
    ]))

    (tmp_path / "discovery").mkdir()
    (tmp_path / "discovery" / "discovery.json").write_text(
        json.dumps(_discovery_with_policy(actor, target, "sts:AssumeRole"))
    )

    (tmp_path / "assessment_findings.json").write_text(json.dumps({
        "findings": [{"profile": "aws-iam-role-chaining", "target_resource": target, "evaluation_tier": "evaluated"}],
    }))

    (tmp_path / "assessment.json").write_text(json.dumps({
        "campaigns": [{
            "profile": "aws-iam-role-chaining",
            "report_json": str(campaign_dir / "report.json"),
        }],
    }))

    result = audit_assessment(tmp_path)
    assert len(result.campaigns) == 1
    c = result.campaigns[0]
    assert c.scope_respected
    assert c.objective_claim_grounded is True
    assert c.evaluation_tier_consistent is True
    assert c.passed
    assert result.all_passed


def test_audit_assessment_skips_campaigns_without_report(tmp_path: Path) -> None:
    (tmp_path / "assessment.json").write_text(json.dumps({
        "campaigns": [{"profile": "p", "report_json": None}],
    }))
    result = audit_assessment(tmp_path)
    assert result.campaigns == []
    assert result.all_passed  # vazio nao e falha
