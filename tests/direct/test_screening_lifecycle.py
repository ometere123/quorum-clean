"""Real Direct Mode execution of the public consensus lifecycle: screen(), appeal(),
adjudicate_appeal(). These call the actual @gl.public methods against the deployed contract
object through the real GenVM SDK, with gl.nondet.web.request / gl.nondet.exec_prompt served by
direct_vm.mock_web / direct_vm.mock_llm rather than by AST inspection or a stub of the pure
helper functions underneath them.

A prior audit found these three methods were never actually executed by any test in this repo —
only counted by string-presence in tests/static/test_contract_adversarial.py. This file closes
that gap.
"""

import json

from conftest import set_block_time

MIN_BOND = 10**15

REVIEWER_ORCID = "0000-0002-1825-0097"
APPLICANT_ORCID = "0000-0001-5109-3700"
REVIEWER_OPENALEX = "A5069172917"
APPLICANT_OPENALEX = "A5023888391"


def _openalex_works_url_pattern(author_id):
    return r"api\.openalex\.org/works\?filter=author\.id:%s" % author_id


def _orcid_record_url_pattern(orcid):
    return r"pub\.orcid\.org/v3\.0/%s/record" % orcid


def _orcid_payload(org_name, start_year):
    return json.dumps({
        "orcid-identifier": {"path": REVIEWER_ORCID},
        "activities-summary": {
            "employments": {
                "affiliation-group": [
                    {
                        "summaries": [
                            {
                                "employment-summary": {
                                    "organization": {"name": org_name},
                                    "put-code": 1,
                                    "start-date": {"year": {"value": str(start_year)}, "month": None, "day": None},
                                    "end-date": None,
                                }
                            }
                        ]
                    }
                ]
            }
        },
    })


def _openalex_solo_payload(work_id, author_id, year=2023):
    return json.dumps({
        "results": [
            {
                "id": "https://openalex.org/%s" % work_id,
                "title": "A solo paper",
                "publication_year": year,
                "authorships": [{"author": {"id": "https://openalex.org/%s" % author_id}}],
            }
        ]
    })


def _work_url(bare_work_id):
    """`extract_coauthorship` stores `item["id"]` verbatim as `tie_basis` — the full OpenAlex
    URL, not the bare id the pattern helpers below key mocks off of."""
    return "https://openalex.org/%s" % bare_work_id


def _openalex_shared_payload(work_id, year=2023):
    return json.dumps({
        "results": [
            {
                "id": "https://openalex.org/%s" % work_id,
                "title": "A co-authored paper",
                "publication_year": year,
                "authorships": [
                    {"author": {"id": "https://openalex.org/%s" % REVIEWER_OPENALEX}},
                    {"author": {"id": "https://openalex.org/%s" % APPLICANT_OPENALEX}},
                ],
            }
        ]
    })


def _register_pair(contract, vm, operator, reviewer, applicant, round_id="round"):
    set_block_time(vm)
    vm.sender = operator
    vm.value = 0
    contract.create_round(round_id, "Grant review", 2020, 2026)
    vm.sender = reviewer
    contract.register_participant(round_id, "REVIEWER", "Reviewer", REVIEWER_ORCID,
                                  REVIEWER_OPENALEX, "")
    vm.sender = applicant
    contract.register_participant(round_id, "APPLICANT", "Applicant", APPLICANT_ORCID,
                                  APPLICANT_OPENALEX, "")
    return round_id


def _request_screening(contract, vm, value_ledger, round_id, reviewer, applicant, sender):
    vm.sender = sender
    value_ledger.fund(MIN_BOND)
    receipt = contract.request_screening(round_id, reviewer.as_hex, applicant.as_hex)
    assert "queued" in receipt.lower(), receipt
    rows = contract.list_screenings(round_id)
    assert len(rows) == 1
    return rows[0]["id"]


def _mock_no_tie_sources(direct_vm):
    direct_vm.mock_web(_openalex_works_url_pattern(REVIEWER_OPENALEX),
                       {"status": 200, "body": _openalex_solo_payload("W1000000001", REVIEWER_OPENALEX)})
    direct_vm.mock_web(_openalex_works_url_pattern(APPLICANT_OPENALEX),
                       {"status": 200, "body": _openalex_solo_payload("W2000000001", APPLICANT_OPENALEX)})
    direct_vm.mock_web(_orcid_record_url_pattern(REVIEWER_ORCID),
                       {"status": 200, "body": _orcid_payload("Reviewer University", 2015)})
    direct_vm.mock_web(_orcid_record_url_pattern(APPLICANT_ORCID),
                       {"status": 200, "body": _orcid_payload("Applicant University", 2018)})


def test_screen_public_entrypoint_clears_on_a_real_successful_evidence_path(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, value_ledger):
    """A. The successful evidence path: every declared source is fetched for real, no tie is
    found, and the screening resolves CLEAR at full weight with the bond returned."""
    round_id = _register_pair(contract, direct_vm, direct_alice, direct_bob, direct_charlie)
    sid = _request_screening(contract, direct_vm, value_ledger, round_id, direct_bob, direct_charlie,
                             direct_alice)

    _mock_no_tie_sources(direct_vm)
    value_ledger.no_value()
    direct_vm.sender = direct_alice
    receipt = contract.screen(sid)
    assert "CLEAR" in receipt, receipt

    row = contract.get_screening(sid)
    assert row["status"] == "CLEAR"
    assert row["weight_bp"] == "10000"
    assert row["resolved"] is True
    assert row["flagged"] is False
    assert "openalex" in row["sources_checked"] and "orcid" in row["sources_checked"]
    assert row["sources_failed"] == ""
    assert row["appeal"] is None

    # The nondet fetch path actually ran: ledger reflects a real screening attempt, not a
    # no-op, and the bond was returned to the requester rather than held.
    ledger = contract.ledger()
    assert int(ledger["screening_attempts"]) == 1
    assert int(ledger["screenings_resolved"]) == 1
    assert value_ledger.paid_out == MIN_BOND


def test_screen_public_entrypoint_cannot_reach_clear_when_a_required_source_fails(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, value_ledger):
    """B. The source-failure path: ORCID answers HTTP 200 with an unparseable (XML-shaped) body
    — the exact real-world trap this contract's own comments describe — so that source is
    recorded as failed. Gate 2 then forbids CLEAR: the pair must resolve INSUFFICIENT and
    retryable, never a favourable result, and the bond must stay held rather than be returned."""
    round_id = _register_pair(contract, direct_vm, direct_alice, direct_bob, direct_charlie)
    sid = _request_screening(contract, direct_vm, value_ledger, round_id, direct_bob, direct_charlie,
                             direct_alice)

    direct_vm.mock_web(_openalex_works_url_pattern(REVIEWER_OPENALEX),
                       {"status": 200, "body": _openalex_solo_payload("W1000000001", REVIEWER_OPENALEX)})
    direct_vm.mock_web(_openalex_works_url_pattern(APPLICANT_OPENALEX),
                       {"status": 200, "body": _openalex_solo_payload("W2000000001", APPLICANT_OPENALEX)})
    direct_vm.mock_web(_orcid_record_url_pattern(REVIEWER_ORCID),
                       {"status": 200, "body": "<html>not json</html>"})
    direct_vm.mock_web(_orcid_record_url_pattern(APPLICANT_ORCID),
                       {"status": 200, "body": _orcid_payload("Applicant University", 2018)})

    value_ledger.no_value()
    direct_vm.sender = direct_alice
    receipt = contract.screen(sid)
    assert "INSUFFICIENT" in receipt, receipt

    row = contract.get_screening(sid)
    assert row["status"] == "INSUFFICIENT"
    assert row["resolved"] is False
    assert row["retryable"] is True
    assert "orcid" in row["sources_failed"]

    # Refusing to clear is not the same as refusing to pay: the bond was funded, so the honest
    # accounting is that it stays held (the pair is retryable, not settled), not stranded, not
    # returned as if the pair had cleared.
    assert value_ledger.paid_out == 0
    assert value_ledger.retained == MIN_BOND


def test_screen_conflict_then_appeal_then_adjudicate_overturned_through_real_public_methods(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, value_ledger):
    """C + appeal + adjudicate_appeal, all through the real public entrypoints.

    C. Tie/materiality path: a real deterministic co-authorship tie is found in code (not
    claimed by the model), the model is only asked to band its materiality, and the returned
    tie_basis is re-verified in deterministic code (verify_tie_basis) before it can zero a vote
    — the model cannot invent a record.

    Then: a funded appeal on a ground with real standing, adjudicated for real (a second
    real gl.nondet.web.request for the appellant's evidence, a second real gl.nondet.exec_prompt
    for the disposition), settling the appeal bond and restoring the screening.
    """
    round_id = _register_pair(contract, direct_vm, direct_alice, direct_bob, direct_charlie)
    sid = _request_screening(contract, direct_vm, value_ledger, round_id, direct_bob, direct_charlie,
                             direct_alice)

    shared_work = "W9000000001"
    direct_vm.mock_web(_openalex_works_url_pattern(REVIEWER_OPENALEX),
                       {"status": 200, "body": _openalex_shared_payload(shared_work)})
    direct_vm.mock_web(_openalex_works_url_pattern(APPLICANT_OPENALEX),
                       {"status": 200, "body": _openalex_shared_payload(shared_work)})
    direct_vm.mock_web(_orcid_record_url_pattern(REVIEWER_ORCID),
                       {"status": 200, "body": _orcid_payload("Reviewer University", 2015)})
    direct_vm.mock_web(_orcid_record_url_pattern(APPLICANT_ORCID),
                       {"status": 200, "body": _orcid_payload("Applicant University", 2018)})
    direct_vm.mock_llm(
        r"YOUR QUESTION, AND ONLY THIS QUESTION: does this link bear on",
        json.dumps({"label": "MATERIAL", "tie_basis": _work_url(shared_work),
                    "rationale": "A recent co-authored paper with two authors."}),
    )

    value_ledger.no_value()
    direct_vm.sender = direct_alice
    receipt = contract.screen(sid)
    assert "CONFLICT" in receipt, receipt

    row = contract.get_screening(sid)
    assert row["status"] == "CONFLICT"
    assert row["weight_bp"] == "0"
    assert row["tie_kind"] == "COAUTHOR"
    assert row["tie_basis"] == _work_url(shared_work)
    # The model was asked, and its answer was checked, not merely trusted.
    ledger = contract.ledger()
    assert int(ledger["prompts_run"]) == 1

    # The bond returns on any settling verdict, CONFLICT included — it pays for the screening
    # attempt, not for a favourable outcome. Only INSUFFICIENT (test B) holds it.
    assert value_ledger.paid_out == MIN_BOND

    # -- appeal(): the reviewer contests materiality, funded with a real bond. --
    evidence_url = "https://example.org/rebuttal"
    direct_vm.mock_web(r"example\.org/rebuttal",
                       {"status": 200, "body": "This co-authorship was incidental to a workshop panel."})
    direct_vm.sender = direct_bob  # the reviewer; GROUND_STANDING[NOT_MATERIAL] is REVIEWER
    value_ledger.fund(MIN_BOND)
    appeal_receipt = contract.appeal(sid, "NOT_MATERIAL", evidence_url)
    assert "filed" in appeal_receipt.lower(), appeal_receipt

    screening_after_appeal = contract.get_screening(sid)
    aid = screening_after_appeal["appeal_id"]
    assert aid == "%s-appeal" % sid
    assert screening_after_appeal["appeal"]["id"] == aid
    assert screening_after_appeal["appeal"]["status"] == "OPEN"

    # -- adjudicate_appeal(): permissionless, real evidence fetch, real disposition prompt. --
    direct_vm.mock_llm(
        r"appellant established that ground",
        json.dumps({"disposition": "OVERTURNED",
                    "rationale": "The rebuttal shows the tie was incidental."}),
    )
    value_ledger.no_value()
    direct_vm.sender = direct_charlie  # permissionless: the applicant may call it too
    adjudicate_receipt = contract.adjudicate_appeal(aid)
    assert "OVERTURNED" in adjudicate_receipt, adjudicate_receipt

    final = contract.get_screening(sid)
    # NOT_MATERIAL overturned, with every source having answered, restores full weight and
    # clears the pair — fixed in code per ground, never chosen by the model.
    assert final["status"] == "CLEAR"
    assert final["weight_bp"] == "10000"
    assert final["appeal"]["status"] == "OVERTURNED"

    final_ledger = contract.ledger()
    assert int(final_ledger["appeals_filed"]) == 1
    assert int(final_ledger["appeals_overturned"]) == 1
    # The appellant's bond came back (the round's bounty pool was never funded, so no bounty
    # rides along with it) — settled through the real payable/value path, not asserted blind.
    # Cumulative across the whole flow: the screening bond (returned on CONFLICT, above) plus
    # this appeal bond, both real transfers captured by value_ledger.
    assert value_ledger.paid_out == 2 * MIN_BOND


def test_appeal_public_entrypoint_refuses_and_refunds_without_standing(
        contract, direct_vm, direct_alice, direct_bob, direct_charlie, value_ledger):
    """A funded appeal from a party with no standing for the ground raised is refused through
    the real public entrypoint (not merely rejected by a pure helper), and the bond is not
    stranded — StudioNet does not refund value on a revert, so this must return, not raise."""
    round_id = _register_pair(contract, direct_vm, direct_alice, direct_bob, direct_charlie)
    sid = _request_screening(contract, direct_vm, value_ledger, round_id, direct_bob, direct_charlie,
                             direct_alice)

    shared_work = "W9000000002"
    direct_vm.mock_web(_openalex_works_url_pattern(REVIEWER_OPENALEX),
                       {"status": 200, "body": _openalex_shared_payload(shared_work)})
    direct_vm.mock_web(_openalex_works_url_pattern(APPLICANT_OPENALEX),
                       {"status": 200, "body": _openalex_shared_payload(shared_work)})
    direct_vm.mock_web(_orcid_record_url_pattern(REVIEWER_ORCID),
                       {"status": 200, "body": _orcid_payload("Reviewer University", 2015)})
    direct_vm.mock_web(_orcid_record_url_pattern(APPLICANT_ORCID),
                       {"status": 200, "body": _orcid_payload("Applicant University", 2018)})
    direct_vm.mock_llm(
        r"YOUR QUESTION, AND ONLY THIS QUESTION: does this link bear on",
        json.dumps({"label": "MATERIAL", "tie_basis": _work_url(shared_work), "rationale": "Two authors."}),
    )
    value_ledger.no_value()
    direct_vm.sender = direct_alice
    contract.screen(sid)
    assert contract.get_screening(sid)["status"] == "CONFLICT"

    # NOT_MATERIAL has standing for the REVIEWER only; the applicant has none for it.
    direct_vm.sender = direct_charlie
    value_ledger.fund(MIN_BOND)
    result = contract.appeal(sid, "NOT_MATERIAL", "https://example.org/no-standing")
    assert result.startswith("[REJECTED]")
    assert "standing" in result
    assert value_ledger.retained == 0
    assert contract.get_screening(sid)["appeal_id"] == ""
