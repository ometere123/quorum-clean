"""Executed lifecycle and boundary matrix; these calls run inside the GenVM SDK."""

import json

import pytest

from conftest import set_block_time


def setup_round(contract, vm, operator, rid="round"):
    set_block_time(vm)
    vm.sender = operator
    vm.value = 0
    contract.create_round(rid, "Grant review", 2020, 2026)


def addr(account):
    return account.as_hex


@pytest.mark.parametrize("bad_scope", ["{}", "null", '"repo"', "[1]", '["bad"]'])
def test_scope_input_boundaries_execute_and_reject(contract, direct_vm, direct_alice, bad_scope):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.declare_github_scope("round", bad_scope, "[]")


@pytest.mark.parametrize("role", ["", "REVIEW", "ADMIN"])
def test_role_boundary_inputs_are_not_accepted_as_reviewer(contract, direct_vm, direct_alice, role):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.register_participant("round", role, "x", "", "", "")


@pytest.mark.parametrize("handle", ["not-an-orcid", "https://orcid.org/", "0000-0000-0000-0000"])
def test_invalid_orcid_handles_are_rejected(contract, direct_vm, direct_alice, handle):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.register_participant("round", "REVIEWER", "x", handle, "", "")


@pytest.mark.parametrize("handle", ["bad", "https://openalex.org/W1"])
def test_invalid_openalex_handles_are_rejected(contract, direct_vm, direct_alice, handle):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.register_participant("round", "REVIEWER", "x", "", handle, "")


@pytest.mark.parametrize("handle", ["bad/name", "https://github.com/a", "two words"])
def test_invalid_github_handles_are_rejected(contract, direct_vm, direct_alice, handle):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.register_participant("round", "REVIEWER", "x", "", "", handle)


def test_reviewer_and_applicant_registration_is_persisted(contract, direct_vm, direct_alice,
                                                          direct_bob):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.register_participant("round", "reviewer", "Alice", "", "", "alice")
    direct_vm.sender = direct_bob
    contract.register_participant("round", "applicant", "Bob", "", "", "bob")
    summary = contract.round_summary("round")
    assert summary["reviewers_count"] == "1"
    assert summary["applicants_count"] == "1"


def test_participant_cannot_register_twice_or_mutate_after_registration(contract, direct_vm,
                                                                         direct_alice):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.register_participant("round", "reviewer", "Alice", "", "", "alice")
    with pytest.raises(Exception, match="already registered"):
        contract.register_participant("round", "reviewer", "Changed", "", "", "other")


def test_valid_screening_request_creates_pending_record_and_freezes_scope(contract, direct_vm,
                                                                            direct_alice,
                                                                            direct_bob):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.declare_github_scope("round", json.dumps(["org/repo"]), "[]")
    contract.register_participant("round", "reviewer", "Alice", "", "", "alice")
    direct_vm.sender = direct_bob
    contract.register_participant("round", "applicant", "Bob", "", "", "bob")
    direct_vm.value = 10**15
    receipt = contract.request_screening("round", addr(direct_alice), addr(direct_bob))
    assert "screening" in receipt and "queued" in receipt.lower()
    rows = contract.list_screenings("round")
    assert len(rows) == 1 and rows[0]["status"] == "PENDING"
    assert contract.round_summary("round")["window_frozen"] is False


@pytest.mark.parametrize("reviewer,applicant", [
    ("0x0000000000000000000000000000000000000001", "0x0000000000000000000000000000000000000001"),
    ("0x0000000000000000000000000000000000000001", "0x0000000000000000000000000000000000000002"),
])
def test_screening_pair_boundaries_are_refused(contract, direct_vm, direct_alice, reviewer, applicant):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.value = 10**15
    result = contract.request_screening("round", reviewer, applicant)
    assert result.startswith("[REJECTED]")


def test_duplicate_screening_is_refused_without_a_second_record(contract, direct_vm, direct_alice,
                                                                  direct_bob):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.register_participant("round", "reviewer", "Alice", "", "", "alice")
    direct_vm.sender = direct_bob
    contract.register_participant("round", "applicant", "Bob", "", "", "bob")
    direct_vm.value = 10**15
    contract.request_screening("round", addr(direct_alice), addr(direct_bob))
    direct_vm.value = 10**15
    result = contract.request_screening("round", addr(direct_alice), addr(direct_bob))
    assert "already requested" in result
    assert len(contract.list_screenings("round")) == 1


def test_lock_round_is_operator_only_and_blocks_future_mutations(contract, direct_vm, direct_alice,
                                                                   direct_bob):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception, match="operator"):
        contract.lock_round("round")
    direct_vm.sender = direct_alice
    assert "locked" in contract.lock_round("round").lower()
    with pytest.raises(Exception, match="locked"):
        contract.declare_github_scope("round", "[]", "[]")
    direct_vm.sender = direct_bob
    with pytest.raises(Exception, match="locked"):
        contract.register_participant("round", "APPLICANT", "x", "", "", "")


def test_round_summary_and_stats_are_structured_after_lock(contract, direct_vm, direct_alice):
    setup_round(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.lock_round("round")
    summary = contract.round_summary("round")
    ledger = contract.ledger()
    assert summary["id"] == "round" and summary["status"] == "LOCKED"
    assert int(ledger["rounds_created"]) == 1


def test_weight_view_is_unavailable_before_a_screening(contract):
    with pytest.raises(Exception, match="no screening"):
        contract.get_weight("missing")
