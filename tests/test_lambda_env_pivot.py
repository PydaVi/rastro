"""Bloco 16.3 — cobertura de Lambda env-var pivot (offline).

Modela a função Lambda como fonte de credencial (as env vars), reusando a mesma
máquina de read-pivot que Secrets/SSM/S3: um principal com
`lambda:GetFunctionConfiguration` lê a config, extrai credencial embutida nas env
vars e assume roles com ela. Execução contra AWS real (condição 4) fica pra fase
de labs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from core.blind_real_runtime import BlindRealRuntime
from core.capability_graph import CapabilityGraph
from core.domain import Action, ActionType, Scope
from execution.aws_executor import AwsRealExecutor
from operations.discovery import _compute_capability_graph
from operations.service import _attack_class_to_profile

USER = "arn:aws:iam::123:user/dev"
ROLE = "arn:aws:iam::123:role/priv-role"
FN = "arn:aws:lambda:us-east-1:123:function:billing-worker"


def _resources(action="lambda:GetFunctionConfiguration", effect="Allow"):
    return [
        {"resource_type": "identity.user", "identifier": USER, "metadata": {"policy_permissions": [
            {"source": "inline", "statements": [
                {"Effect": effect, "Action": [action], "Resource": [FN]}]}]}},
        {"resource_type": "identity.role", "identifier": ROLE, "metadata": {}},
        {"resource_type": "compute.lambda_function", "identifier": FN,
         "metadata": {"name": "billing-worker", "execution_role": ROLE}},
    ]


# --- discovery annotation (readable_by via lambda read actions) ---

def test_discovery_marks_lambda_readable_by():
    resources = _resources()
    _compute_capability_graph(resources)
    fn_meta = next(r["metadata"] for r in resources if r["resource_type"] == "compute.lambda_function")
    assert fn_meta["readable_by"] == [USER]


def test_discovery_lambda_read_respects_deny():
    resources = _resources()
    resources[0]["metadata"]["policy_permissions"][0]["statements"].append(
        {"Effect": "Deny", "Action": ["lambda:GetFunctionConfiguration"], "Resource": [FN]})
    _compute_capability_graph(resources)
    fn_meta = next(r["metadata"] for r in resources if r["resource_type"] == "compute.lambda_function")
    assert "readable_by" not in fn_meta


def test_discovery_no_read_without_lambda_permission():
    resources = _resources(action="lambda:ListTags")
    _compute_capability_graph(resources)
    fn_meta = next(r["metadata"] for r in resources if r["resource_type"] == "compute.lambda_function")
    assert "readable_by" not in fn_meta


# --- capability graph → lambda_pivot hypothesis ---

def test_capability_graph_derives_lambda_pivot():
    resources = _resources()
    _compute_capability_graph(resources)
    graph = CapabilityGraph.build({"resources": resources})
    hyps = graph.derive_all_hypotheses([USER])
    lp = [h for h in hyps if h.attack_class == "lambda_pivot"]
    assert len(lp) == 1
    h = lp[0]
    assert h.target == ROLE
    assert h.intermediate_resource == FN
    tools = [s.tool for s in h.path]
    assert tools == ["lambda_read_env", "iam_passrole"]


def test_lambda_pivot_routes_to_credential_pivot_profile():
    assert _attack_class_to_profile("lambda_pivot", ROLE, []) == "aws-credential-pivot"


# --- path-driven runtime action ---

def test_blind_runtime_step_to_action_builds_lambda_action():
    scope = Scope.model_validate({
        "target": "aws", "allowed_services": ["lambda", "iam"],
        "allowed_actions": ["enumerate", "assume_role", "access_resource"],
        "allowed_resources": [FN], "aws_account_ids": ["123"],
        "allowed_regions": ["us-east-1"], "authorized_by": "test",
        "authorized_at": "2026-01-01", "authorization_document": "docs/auth.pdf", "dry_run": False,
    })
    path = [{"step_type": "read", "actor": USER, "target": FN, "tool": "lambda_read_env"}]
    runtime = BlindRealRuntime.build(
        plan={"profile": "aws-credential-pivot", "resource_arn": ROLE, "signals": {"path": path}},
        discovery_snapshot={"resources": []}, scope=scope, entry_identities=[USER])
    actions = runtime.enumerate_actions(None)
    assert len(actions) == 1
    action = actions[0]
    assert action.tool == "lambda_read_env"
    assert action.parameters["service"] == "lambda"
    assert action.parameters["function_name"] == "billing-worker"


# --- executor extracts credentials from env vars (Bloco 8 produces) ---

class _FakeLambdaClient:
    def __init__(self, env):
        self._env = env

    def get_function_configuration(self, region, function_name, credentials=None):
        return {"FunctionArn": FN, "FunctionName": function_name, "Role": ROLE, "Environment": self._env}


def _run_executor(env):
    # Testa o método do executor + _apply_produces (Bloco 8) direto, sem o caminho
    # de scope/credenciais do execute() completo (não relevante pra este pivot).
    executor = AwsRealExecutor(fixture=None, scope=None, client=_FakeLambdaClient(env))
    executor._base_actor_arn = USER
    action = Action(action_type=ActionType.ACCESS_RESOURCE, actor=USER, target=FN,
                    parameters={"service": "lambda", "region": "us-east-1", "function_name": "billing-worker"},
                    tool="lambda_read_env")
    details = executor._execute_lambda_read_env(_FakeLambdaClient(env), action)
    executor._apply_produces(action, details)
    return executor, details


def test_executor_extracts_aws_credentials_from_env_vars():
    env = {
        "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE1234567890",
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "LOG_LEVEL": "info",
    }
    executor, details = _run_executor(env)
    assert details["response_summary"]["credential_extracted"] is True
    # produces (Bloco 8) registra a identidade extraída
    assert details.get("synthetic_actor") == f"extracted://{FN}"
    assert f"extracted://{FN}" in executor._credentials_by_actor


def test_executor_no_credentials_when_env_is_clean():
    executor, details = _run_executor({"LOG_LEVEL": "info", "STAGE": "prod"})
    assert details["response_summary"].get("credential_extracted") in (False, None)
    assert "synthetic_actor" not in details


# --- Camada C generator + baseline ---

def test_generated_lambda_environment_yields_lambda_pivot():
    from gen_synthetic_environment import generate_lambda_environment
    snap = generate_lambda_environment(10, seed=909)
    graph = CapabilityGraph.build(snap)
    entries = sorted(r["identifier"] for r in snap["resources"] if r["resource_type"] == "identity.user")
    hyps = graph.derive_all_hypotheses(entries)
    lp = [h for h in hyps if h.attack_class == "lambda_pivot"]
    assert lp
    for h in lp:
        assert h.path and h.path[0].tool == "lambda_read_env"
