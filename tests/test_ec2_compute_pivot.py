"""Bloco 16.3 — cobertura de EC2 instance-profile pivot (offline).

Modela o compute pivot como entrada IAM-grounded no CapabilityGraph: um principal
com `ssm:SendCommand`/`ssm:StartSession` numa instância rouba as credenciais do
role do instance profile via IMDS. Reachability de rede é uma superfície SEPARADA
(external_entry), não este caminho.

Cobre discovery → grafo → hipótese → path executável → modo de sucesso, e o
baseline seguro (Camada B) que mede falso positivo. Execução contra AWS real
(condição 4 da 16.3, Camadas A/B/C ao vivo) fica pendente — o classificador exige
o `terraform apply` rodado à mão.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from core.blind_real_runtime import BlindRealRuntime
from core.capability_graph import CapabilityGraph
from core.domain import Action, ActionType, Objective, Observation, Scope
from core.aws_dry_run_lab import AwsDryRunLab
from core.fixture import Fixture
from core.state import StateManager
from core.tool_registry import ToolRegistry
from operations.campaign_synthesis import _build_generated_success_criteria
from operations.discovery import _compute_capability_graph

ROOT = Path(__file__).resolve().parents[1]
USER = "arn:aws:iam::123:user/ops"
ROLE = "arn:aws:iam::123:role/app-role"
PROFILE = "arn:aws:iam::123:instance-profile/app-profile"
INSTANCE = "arn:aws:ec2:us-east-1:123:instance/i-0abc"


def _ec2_resources(command_actions=("ssm:SendCommand",), effect="Allow"):
    return [
        {"resource_type": "identity.user", "identifier": USER, "metadata": {"policy_permissions": [
            {"source": "inline", "statements": [
                {"Effect": effect, "Action": list(command_actions), "Resource": [INSTANCE]}]}]}},
        {"resource_type": "identity.role", "identifier": ROLE, "metadata": {}},
        {"resource_type": "compute.instance_profile", "identifier": PROFILE, "metadata": {"role": ROLE}},
        {"resource_type": "compute.ec2_instance", "identifier": INSTANCE, "metadata": {"instance_profile": PROFILE}},
    ]


# --- discovery annotation ---

def test_discovery_annotates_compute_pivot_by_from_ssm_command():
    resources = _ec2_resources()
    _compute_capability_graph(resources)
    role_meta = next(r["metadata"] for r in resources if r["resource_type"] == "identity.role")
    assert role_meta["compute_pivot_by"] == [USER]
    assert role_meta["compute_pivot_profile"] == PROFILE


def test_discovery_compute_pivot_respects_explicit_deny():
    resources = _ec2_resources()
    # adiciona um Deny cobrindo a mesma action+resource → não é commander
    resources[0]["metadata"]["policy_permissions"][0]["statements"].append(
        {"Effect": "Deny", "Action": ["ssm:SendCommand"], "Resource": [INSTANCE]})
    _compute_capability_graph(resources)
    role_meta = next(r["metadata"] for r in resources if r["resource_type"] == "identity.role")
    assert "compute_pivot_by" not in role_meta


def test_discovery_no_pivot_without_command_permission():
    resources = _ec2_resources(command_actions=("ec2:DescribeInstances",))
    _compute_capability_graph(resources)
    role_meta = next(r["metadata"] for r in resources if r["resource_type"] == "identity.role")
    assert "compute_pivot_by" not in role_meta


def test_discovery_startsession_also_grants_pivot():
    resources = _ec2_resources(command_actions=("ssm:StartSession",))
    _compute_capability_graph(resources)
    role_meta = next(r["metadata"] for r in resources if r["resource_type"] == "identity.role")
    assert role_meta["compute_pivot_by"] == [USER]


# --- capability graph → hypothesis → path ---

def test_capability_graph_derives_compute_pivot_hypothesis():
    resources = _ec2_resources()
    _compute_capability_graph(resources)
    graph = CapabilityGraph.build({"resources": resources})
    assert (ROLE, PROFILE) in graph.can_pivot_compute[USER]

    hyps = graph.derive_all_hypotheses([USER])
    cp = [h for h in hyps if h.attack_class == "compute_pivot"]
    assert len(cp) == 1
    h = cp[0]
    assert h.entry_identity == USER
    assert h.target == ROLE  # o alvo lógico é a role
    assert h.evaluation_tier == "structural"  # pivot IMDS não avalia estático


def test_compute_pivot_structured_path_targets_instance_profile():
    resources = _ec2_resources()
    _compute_capability_graph(resources)
    graph = CapabilityGraph.build({"resources": resources})
    h = next(x for x in graph.derive_all_hypotheses([USER]) if x.attack_class == "compute_pivot")
    assert len(h.path) == 1
    step = h.path[0]
    assert step.step_type == "compute_pivot"
    assert step.tool == "ec2_instance_profile_pivot"
    assert step.actor == USER
    assert step.target == PROFILE  # o executor age sobre o instance profile, não a role


# --- success mode: compute_pivot_proved ---

def _state_for_compute_pivot():
    fixture = Fixture.load(ROOT / "fixtures" / "mixed_generalization_iam_s3_lab.json")
    scope = Scope.model_validate_json(
        (ROOT / "examples" / "scope_internal_data_platform_iam_s3.json").read_text())
    objective = Objective(description="Reach role via EC2 instance profile",
                          target=ROLE, success_criteria={"mode": "compute_pivot_proved"})
    return StateManager(objective=objective, scope=scope,
                        fixture=AwsDryRunLab.from_fixture(fixture, scope),
                        tool_registry=ToolRegistry.load(ROOT / "tools"))


def _ec2_action():
    return Action(action_type=ActionType.ACCESS_RESOURCE, actor=USER, target=PROFILE,
                  parameters={"service": "ec2"}, tool="ec2_instance_profile_pivot")


def test_compute_pivot_proved_met_when_reached_role_matches():
    state = _state_for_compute_pivot()
    state.apply_observation(_ec2_action(),
                            Observation(success=True, details={"reached_role": ROLE}),
                            "pivoted via instance profile")
    assert state.is_objective_met() is True


def test_compute_pivot_proved_not_met_for_different_role():
    state = _state_for_compute_pivot()
    state.apply_observation(_ec2_action(),
                            Observation(success=True, details={"reached_role": "arn:aws:iam::123:role/other"}),
                            "reached the wrong role")
    assert state.is_objective_met() is False


def test_compute_pivot_proved_not_met_without_ec2_tool():
    state = _state_for_compute_pivot()
    wrong = Action(action_type=ActionType.ACCESS_RESOURCE, actor=USER, target=PROFILE,
                   parameters={"service": "ec2"}, tool="iam_list_roles")
    state.apply_observation(wrong, Observation(success=True, details={"reached_role": ROLE}),
                            "not the ec2 tool")
    assert state.is_objective_met() is False


def test_campaign_synthesis_routes_compute_iam_to_compute_pivot_proved():
    criteria = _build_generated_success_criteria({"profile_family": "aws-iam-compute-iam", "id": "c1"})
    assert criteria["mode"] == "compute_pivot_proved"


# --- path-driven runtime action ---

def test_blind_runtime_step_to_action_builds_ec2_action():
    scope = Scope.model_validate({
        "target": "aws", "allowed_services": ["ec2", "iam"],
        "allowed_actions": ["enumerate", "assume_role", "access_resource"],
        "allowed_resources": [PROFILE], "aws_account_ids": ["123"],
        "allowed_regions": ["us-east-1"], "authorized_by": "test",
        "authorized_at": "2026-01-01", "authorization_document": "docs/auth.pdf", "dry_run": False,
    })
    path = [{"step_type": "compute_pivot", "actor": USER, "target": PROFILE,
             "tool": "ec2_instance_profile_pivot"}]
    runtime = BlindRealRuntime.build(
        plan={"profile": "aws-iam-compute-iam", "resource_arn": ROLE, "signals": {"path": path}},
        discovery_snapshot={"resources": []}, scope=scope, entry_identities=[USER])
    actions = runtime.enumerate_actions(None)
    assert len(actions) == 1
    action = actions[0]
    assert action.tool == "ec2_instance_profile_pivot"
    assert action.target == PROFILE
    assert action.parameters["instance_profile_arn"] == PROFILE
    assert action.parameters["service"] == "ec2"


# --- Camada C generator + Camada B baseline (16.2 practice) ---

def test_generated_ec2_environment_yields_compute_pivot_hypotheses():
    from gen_synthetic_environment import generate_ec2_environment
    snap = generate_ec2_environment(10, seed=4242)
    graph = CapabilityGraph.build(snap)
    entries = sorted(r["identifier"] for r in snap["resources"] if r["resource_type"] == "identity.user")
    hyps = graph.derive_all_hypotheses(entries)
    cp = [h for h in hyps if h.attack_class == "compute_pivot"]
    assert cp, "esperava compute_pivot hypotheses no ambiente EC2 sintético"
    for h in cp:
        assert h.path and h.path[0].tool == "ec2_instance_profile_pivot"


def test_secure_baseline_yields_zero_attack_hypotheses():
    # Camada B: recursos existem, nenhum caminho de ataque → falso positivo = 0.
    from gen_synthetic_environment import generate_secure_baseline
    snap = generate_secure_baseline(20, seed=7)
    graph = CapabilityGraph.build(snap)
    entries = sorted(r["identifier"] for r in snap["resources"] if r["resource_type"] == "identity.user")
    hyps = graph.derive_all_hypotheses(entries)
    assert hyps == [], f"baseline seguro gerou {len(hyps)} hipóteses — falso positivo"
