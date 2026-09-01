import ast
from pathlib import Path


def _contract():
    return ast.parse(Path("contracts/QuorumClean.py").read_text(encoding="utf-8"))


def test_contract_has_single_public_class_and_required_methods():
    tree = _contract()
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "QuorumClean"]
    assert len(classes) == 1
    methods = {node.name for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {"create_round", "register_participant", "request_screening", "screen", "appeal", "adjudicate_appeal", "lock_round", "get_weight"} <= methods


def test_contract_has_no_raw_external_decision_shortcut():
    source = Path("contracts/QuorumClean.py").read_text(encoding="utf-8")
    assert "verdict = \"CLEAR\"" not in source
    assert "VERDICT_INSUFFICIENT" in source
