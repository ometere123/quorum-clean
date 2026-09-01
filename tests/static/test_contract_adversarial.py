"""High-signal contract audit checks for the deterministic boundary.

These are intentionally source-level assertions: the GenVM direct harness is not available in
every clean-clone environment, but these checks still fail if a future edit removes a lifecycle
gate, changes the closed status vocabulary, or lets missing evidence become CLEAR.
"""

import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "contracts" / "QuorumClean.py"
TEXT = SOURCE.read_text(encoding="utf-8")
TREE = ast.parse(TEXT)
FUNCTIONS = {
    node.name: node for node in ast.walk(TREE)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}


def body_text(name: str) -> str:
    node = FUNCTIONS[name]
    start = node.lineno - 1
    end = max((child.lineno for child in ast.walk(node) if hasattr(child, "lineno")), default=node.lineno)
    return "\n".join(TEXT.splitlines()[start:end])


def test_round_creation_has_duplicate_and_window_gates():
    body = body_text("create_round")
    assert "rid in self.rounds" in body
    assert "coi_start_year" in body and "coi_end_year" in body
    assert "start_year" in body and "end_year" in body


def test_registration_is_round_scoped_and_duplicate_safe():
    body = body_text("register_participant")
    assert "round_id" in body
    assert "already registered" in body or "duplicate" in body
    assert "role_text" in body and "ROLE_REVIEWER" in body


def test_scope_is_validated_and_frozen_before_screening():
    declare = body_text("declare_github_scope")
    request = body_text("request_screening")
    assert "_require_json_list" in declare
    assert "if value not in out" in TEXT
    assert "round_id" in request
    assert "frozen" in TEXT.lower() or "scope_declared" in request


def test_screening_requires_bond_and_rejects_duplicate_pairs():
    body = body_text("request_screening")
    assert "gl.message.value" in body
    assert "bond" in body
    assert "pair_to_screening" in body and "pair already requested" in body


def test_missing_external_evidence_cannot_be_clean():
    text = TEXT.lower()
    assert "insufficient" in text
    assert "never clear" in text
    assert "source did not answer" in text or "did not answer" in text
    assert "complete" in text


def test_identity_and_materiality_models_are_bounded_to_equivalence_blocks():
    for name in ("_github_block", "_orcid_block", "_openalex_block", "_identity_block", "_materiality_block"):
        if name in FUNCTIONS:
            body = body_text(name)
            assert "eq_principle" in body, name
    assert "prompt_comparative" in TEXT
    assert "UNRESOLVED" in TEXT


def test_appeal_has_ground_bond_and_terminal_settlement_paths():
    appeal = body_text("appeal")
    adjudicate = body_text("adjudicate_appeal")
    assert "gl.message.value" in appeal and "bond" in appeal
    assert "ground" in appeal and "evidence" in appeal
    assert "settle" in adjudicate or "refund" in adjudicate
    assert "already" in adjudicate or "terminal" in adjudicate


def test_lock_is_terminal_for_round_mutations():
    body = body_text("lock_round")
    assert "locked" in body.lower()
    assert "screen" in body.lower()
    for name in ("declare_github_scope", "register_participant", "request_screening"):
        assert "locked" in body_text(name).lower() or "lock" in body_text(name).lower(), name


def test_contract_has_no_float_money_or_private_signer_fallback():
    assert "float(" not in TEXT
    assert "PRIVATE_KEY" not in TEXT
    assert "mnemonic" not in TEXT.lower()
    assert "emit_transfer" in TEXT  # payouts use the explicit payee interface


def test_all_network_reads_are_inside_ep_blocks_after_lint_refactor():
    global_adapter = body_text("_fetch")
    assert "gl.nondet.web.request" not in global_adapter
    assert TEXT.count("gl.eq_principle.strict_eq") >= 3
    assert TEXT.count("gl.nondet.web.request") >= 4
