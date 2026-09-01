"""High-signal state-machine checks executed by the real GenVM SDK."""

import json

import pytest

from conftest import set_block_time


MIN_BOND = 10**15


def open_round(contract, vm, sender, round_id="r1", value=0):
    vm.sender = sender
    vm.value = value
    return contract.create_round(round_id, "Review round", 2020, 2026)


def test_fresh_contract_has_empty_round_index(contract):
    assert contract.list_rounds() == []


def test_create_round_persists_operator_window_and_open_state(contract, direct_vm, direct_alice):
    set_block_time(direct_vm)
    receipt = open_round(contract, direct_vm, direct_alice, value=0)
    assert "r1 opened" in receipt
    rows = contract.list_rounds()
    assert len(rows) == 1
    assert rows[0]["id"] == "r1"
    assert rows[0]["status"] == "OPEN"


@pytest.mark.parametrize("round_id,name,start,end", [
    ("", "x", 2020, 2026),
    ("r", "", 2020, 2026),
    ("r", "x", 2019, 2018),
    ("r", "x", 1800, 2026),
    ("r", "x", 2020, 2200),
])
def test_invalid_round_creation_is_rejected_without_state(contract, direct_vm, direct_alice,
                                                           round_id, name, start, end):
    set_block_time(direct_vm)
    direct_vm.sender = direct_alice
    direct_vm.value = 0
    result = contract.create_round(round_id, name, start, end)
    assert result.startswith("[REJECTED]")
    assert contract.list_rounds() == []


def test_duplicate_round_is_rejected(contract, direct_vm, direct_alice):
    set_block_time(direct_vm)
    open_round(contract, direct_vm, direct_alice)
    result = open_round(contract, direct_vm, direct_alice)
    assert result.startswith("[REJECTED]")


def test_operator_can_declare_normalized_scope_once(contract, direct_vm, direct_alice):
    set_block_time(direct_vm)
    open_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    receipt = contract.declare_github_scope("r1", json.dumps(["Org/Repo", "org/Repo"]),
                                            json.dumps(["ExampleOrg"]))
    assert "2 repositories" in receipt


def test_non_operator_cannot_declare_scope(contract, direct_vm, direct_alice, direct_bob):
    set_block_time(direct_vm)
    open_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception):
        contract.declare_github_scope("r1", "[]", "[]")


def test_scope_rejects_malformed_json(contract, direct_vm, direct_alice):
    set_block_time(direct_vm)
    open_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.declare_github_scope("r1", "{}", "[]")


def test_participants_are_round_scoped_and_duplicate_safe(contract, direct_vm, direct_alice):
    set_block_time(direct_vm)
    open_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.register_participant("r1", "REVIEWER", "Reviewer", "", "", "reviewer")
    with pytest.raises(Exception):
        contract.register_participant("r1", "REVIEWER", "Again", "", "", "reviewer2")


def test_unknown_round_and_invalid_role_are_rejected(contract, direct_vm, direct_alice):
    set_block_time(direct_vm)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.register_participant("missing", "REVIEWER", "x", "", "", "")
    open_round(contract, direct_vm, direct_alice)
    with pytest.raises(Exception):
        contract.register_participant("r1", "ARBITER", "x", "", "", "")


def test_funded_invalid_screening_returns_refusal_and_refunds(contract, direct_vm, direct_alice,
                                                               value_ledger):
    set_block_time(direct_vm)
    open_round(contract, direct_vm, direct_alice)
    value_ledger.fund(MIN_BOND)
    result = contract.request_screening("r1", "0x0000000000000000000000000000000000000001",
                                        "0x0000000000000000000000000000000000000002")
    assert result.startswith("[REJECTED]")
    assert value_ledger.retained == 0


def test_missing_round_screening_is_rejected_and_no_value_is_retained(contract, direct_vm,
                                                                        direct_alice,
                                                                        value_ledger):
    set_block_time(direct_vm)
    direct_vm.sender = direct_alice
    value_ledger.fund(MIN_BOND)
    result = contract.request_screening("missing", "0x0000000000000000000000000000000000000001",
                                        "0x0000000000000000000000000000000000000002")
    assert result.startswith("[REJECTED]")
    assert value_ledger.retained == 0


def test_unknown_views_return_empty_collections(contract):
    assert contract.list_screenings("missing") == []
    assert contract.list_appeals("missing") == []


def test_missing_weight_is_rejected(contract):
    with pytest.raises(Exception):
        contract.get_weight("missing")
