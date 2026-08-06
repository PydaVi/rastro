"""Protege o mecanismo de integridade da fase de labs (anti-viés-de-confirmação).

Se o scorer um dia parar de reportar miss/FP corretamente, o suite inteiro de
labs vira teatro. Estes testes travam o comportamento que dá integridade:
- caminho em-cobertura NÃO gerado pelo engine → miss INESPERADO (não some);
- caminho fora-de-cobertura NÃO gerado → miss ESPERADO (registrado, não conta como falha);
- controle negativo com hipótese gerada → FALSO POSITIVO detectado.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lab_scorer import score_lab
from operations.discovery import _compute_capability_graph

ACCT = "123456789012"
USER = f"arn:aws:iam::{ACCT}:user/u"
ROLE = f"arn:aws:iam::{ACCT}:role/r"
GHOST = f"arn:aws:iam::{ACCT}:role/does-not-connect"


def _write_lab(tmp_path, resources, true_paths, challenge=False):
    _compute_capability_graph(resources)
    snap = {"target": "t", "resources": resources,
            "caller_identity": {"Account": ACCT, "Arn": USER}}
    d = tmp_path / "lab"
    d.mkdir()
    (d / "lab.yaml").write_text(f"name: lab\nlayer: C\nchallenge: {json.dumps(challenge)}\n")
    (d / "env.discovery.json").write_text(json.dumps(snap))
    (d / "ground_truth.json").write_text(json.dumps({"lab": "lab", "true_paths": true_paths}))
    return d


def _assumable_role_env():
    return [
        {"resource_type": "identity.user", "identifier": USER, "metadata": {"policy_permissions": [
            {"source": "i", "statements": [{"Effect": "Allow", "Action": ["sts:AssumeRole"], "Resource": [ROLE]}]}]}},
        {"resource_type": "identity.role", "identifier": ROLE,
         "metadata": {"trust_principals": [USER], "policy_permissions": []}},
    ]


def test_in_coverage_path_found_is_recall_one(tmp_path):
    d = _write_lab(tmp_path, _assumable_role_env(),
                   [{"id": "p", "entry": USER, "target": ROLE, "in_coverage": True}])
    res = score_lab(d)
    assert res.recall == 1.0
    assert not res.covered_missed
    assert not res.false_positives


def test_in_coverage_path_not_generated_is_unexpected_miss(tmp_path):
    # ground truth afirma um caminho que o engine NÃO gera (role sem aresta) →
    # tem que aparecer como miss inesperado, não sumir.
    env = _assumable_role_env()
    env.append({"resource_type": "identity.role", "identifier": GHOST,
                "metadata": {"trust_principals": [], "policy_permissions": []}})
    d = _write_lab(tmp_path, env,
                   [{"id": "real", "entry": USER, "target": ROLE, "in_coverage": True},
                    {"id": "phantom", "entry": USER, "target": GHOST, "in_coverage": True}])
    res = score_lab(d)
    assert res.recall == 0.5
    assert [p["id"] for p in res.covered_missed] == ["phantom"]


def test_out_of_coverage_miss_is_expected_not_failure(tmp_path):
    env = _assumable_role_env()
    env.append({"resource_type": "identity.role", "identifier": GHOST,
                "metadata": {"trust_principals": [], "policy_permissions": []}})
    d = _write_lab(tmp_path, env,
                   [{"id": "real", "entry": USER, "target": ROLE, "in_coverage": True},
                    {"id": "hard", "entry": USER, "target": GHOST, "in_coverage": False}],
                   challenge=True)
    res = score_lab(d)
    assert res.recall == 1.0  # o em-cobertura foi achado
    assert not res.covered_missed  # o fora-de-cobertura NÃO conta como miss inesperado
    assert [p["id"] for p in res.ooc_missed] == ["hard"]


def test_negative_control_flags_false_positive(tmp_path):
    # ground truth VAZIO mas o ambiente tem um caminho real → o engine gera
    # hipótese → tem que virar FALSO POSITIVO.
    d = _write_lab(tmp_path, _assumable_role_env(), [])
    res = score_lab(d)
    assert res.false_positives
    assert any(fp["target"] == ROLE for fp in res.false_positives)
