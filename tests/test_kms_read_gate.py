"""Bloco 16.3 — KMS read-gate (offline).

KMS não é superfície de pivot-pra-identidade (decrypt dá texto-plano, não role).
O modelo escolhido é o READ-GATE: um recurso cifrado com CMK customer-managed só
é realmente legível por quem tem TAMBÉM kms:Decrypt na chave — refina o readable_by
existente pra reduzir falso positivo. Ter GetSecretValue não basta se você não
decifra.

Coleta real de CMK + captura do kms_key_id por recurso é peça de discovery da fase
de labs; aqui o mecanismo do gate é provado offline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from core.capability_graph import CapabilityGraph
from operations.discovery import _compute_capability_graph

KEY = "arn:aws:kms:us-east-1:123:key/cmk-1"
SECRET = "arn:aws:secretsmanager:us-east-1:123:secret:prod/db"
A = "arn:aws:iam::123:user/can-decrypt"
B = "arn:aws:iam::123:user/no-decrypt"


def _stmt(actions, res):
    return {"Effect": "Allow", "Action": actions, "Resource": res}


def _resources(*, b_can_decrypt=False, encrypted=True, key_in_snapshot=True):
    a_stmts = [_stmt(["secretsmanager:GetSecretValue"], [SECRET]), _stmt(["kms:Decrypt"], [KEY])]
    b_stmts = [_stmt(["secretsmanager:GetSecretValue"], [SECRET])]
    if b_can_decrypt:
        b_stmts.append(_stmt(["kms:Decrypt"], [KEY]))
    secret_meta = {"name": "prod/db"}
    if encrypted:
        secret_meta["kms_key_id"] = KEY
    resources = [
        {"resource_type": "identity.user", "identifier": A,
         "metadata": {"policy_permissions": [{"source": "i", "statements": a_stmts}]}},
        {"resource_type": "identity.user", "identifier": B,
         "metadata": {"policy_permissions": [{"source": "i", "statements": b_stmts}]}},
        {"resource_type": "secret.secrets_manager", "identifier": SECRET, "metadata": secret_meta},
    ]
    if key_in_snapshot:
        resources.append({"resource_type": "crypto.kms_key", "identifier": KEY, "metadata": {}})
    return resources


def _readable(resources):
    meta = next(r["metadata"] for r in resources if r["resource_type"] == "secret.secrets_manager")
    return set(meta.get("readable_by", []))


# --- gate behaviour ---

def test_gate_removes_reader_without_decrypt():
    resources = _resources(b_can_decrypt=False)
    _compute_capability_graph(resources)
    assert _readable(resources) == {A}  # B gateado por não decifrar


def test_gate_keeps_reader_with_decrypt():
    resources = _resources(b_can_decrypt=True)
    _compute_capability_graph(resources)
    assert _readable(resources) == {A, B}


def test_key_annotated_with_decryptable_by():
    resources = _resources(b_can_decrypt=True)
    _compute_capability_graph(resources)
    key_meta = next(r["metadata"] for r in resources if r["resource_type"] == "crypto.kms_key")
    assert set(key_meta["decryptable_by"]) == {A, B}


# --- honest non-restriction when data is missing ---

def test_no_gate_when_resource_not_encrypted():
    # Sem kms_key_id, readable_by preserva ambos (comportamento anterior).
    resources = _resources(encrypted=False)
    _compute_capability_graph(resources)
    assert _readable(resources) == {A, B}


def test_no_gate_when_key_absent_from_snapshot():
    # CMK referenciada mas não descoberta → não inventa falso negativo, preserva.
    resources = _resources(key_in_snapshot=False)
    _compute_capability_graph(resources)
    assert _readable(resources) == {A, B}


# --- end-to-end effect on hypotheses (false positive reduction) ---

def test_gate_suppresses_hypothesis_from_non_decryptor():
    # B só teria hipótese de credential_access se pudesse ler o secret; o gate
    # remove B do readable_by → nenhuma hipótese partindo de B sobre esse secret.
    resources = _resources(b_can_decrypt=False)
    _compute_capability_graph(resources)
    graph = CapabilityGraph.build({"resources": resources})
    b_hyps = [h for h in graph.derive_all_hypotheses([B]) if h.target == SECRET or h.intermediate_resource == SECRET]
    assert b_hyps == []
    a_hyps = [h for h in graph.derive_all_hypotheses([A]) if h.target == SECRET]
    assert any(h.attack_class == "credential_access_direct" for h in a_hyps)


# --- Camada C generator ---

def test_generated_kms_environment_gates_non_decryptors():
    from gen_synthetic_environment import generate_kms_gated_environment
    snap = generate_kms_gated_environment(10, seed=55)
    by_id = {r["identifier"]: r for r in snap["resources"]}
    # cada secret cifrado só deve listar leitores que também decifram
    for r in snap["resources"]:
        if r["resource_type"] != "secret.secrets_manager":
            continue
        key_id = r["metadata"].get("kms_key_id")
        readers = set(r["metadata"].get("readable_by", []))
        decryptors = set(by_id[key_id]["metadata"].get("decryptable_by", []))
        assert readers <= decryptors, f"{r['identifier']}: leitor sem decrypt vazou o gate"
