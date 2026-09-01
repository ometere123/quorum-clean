# quorum-coauthor

Deterministic core of Quorum Clean (PRD `genlayer-prds/04-reviewer-integrity-gate.md`), standalone because a GenLayer
contract cannot import a sibling file, so this is the only place it can be unit tested. `coauthor.py` has **zero
imports**, no clock and no filesystem, and reaches HTTP only through an injected `fetch(url,headers)` callable.

    python test_coauthor.py     # 176 tests
    python mutation_check.py    # 8 safety mutations, all must report CAUGHT

Absence is never success: empty results, 403, 429, 404 and a 200 with an unparseable body all raise `[EXTERNAL]` and
resolve to `INSUFFICIENT`, never `CLEAR`. Tags: `[EXPECTED]` `[EXTERNAL]` `[TRANSIENT]` `[LLM_ERROR]`. Model output is
classification only; weight is decided in code. Normalization and window rules: one sentence each in `coauthor.py`.

## Public signatures
**Normalization:** `normalize_institution(raw)` `institutions_match(a,b)` `normalize_person_name(raw)` (display
only, never identity) `normalize_repo_id(raw)` `normalize_github_login(raw)` `normalize_orcid(raw)`
`normalize_orcid_maybe(raw)` `check_handle_consistency(declared,found)`
**Dates, COI window both ends inclusive:** `make_date(y,m,d,end=False)` `days_in_month(y,m)` `fmt_date(d)`
`interval_overlap(a_start,a_end,b_start,b_end)` `coi_window_from_years(sy,ey)` `months_of_overlap(start,end)`
`overlap_in_window(start,end,window)` `year_in_window(year,window)`
**OpenAlex:** `assert_openalex_select(url)` `build_openalex_works_url(author_id,per_page)` `fetch_openalex_works(fetch,author_id)`
`build_openalex_author_search_url(name)` `validate_openalex_author_id(raw)` `parse_openalex_authors(payload)`
`extract_coauthorship(payload,focus_id)` `coauthorship_overlap(graph,other_id,window)` `shared_third_party_coauthors(a,b)`
**ORCID:** `assert_orcid_json_headers(headers)` `build_orcid_record_url(orcid)` `guard_orcid_json_body(resp)`
`fetch_orcid_record(fetch,orcid)` `extract_employments(record)` `employment_overlap(emps_a,emps_b,window)`
**GitHub:** `build_github_contributors_url(repo)` `build_github_org_members_url(org)` `rank_contributors(c)`
`plan_github_batch(repo_ids,budget,spent)` `fetch_github_contributors_batch(fetch,repo_ids)`
`extract_contributors(payload,repo)` `contribution_overlap(repo,c,a,b,top_n)` `org_membership_overlap(org,m,a,b)`
**Verdict:** `new_ledger()` `record_checked(l,src)` `record_failed(l,src,err)` `ledger_summary(l)`
`classify_status(status,headers)` `classify_identity_link(out,recs)` `classify_materiality(out,recs)`
`verify_tie_basis(basis,recs)` `screen_verdict(...)` `render_verdict_line(result)`

## Splice contract
1. Copy `coauthor.py` verbatim, from `# --- QUORUM-COAUTHOR SPLICE BEGIN ---` to
   `# --- QUORUM-COAUTHOR SPLICE END ---`, into `quorum-clean/contracts/QuorumClean.py` at module
   level between the same two markers. Change nothing inside; zero imports is what makes that safe.
2. The markers live in this source, not only in the contract, so `test_coauthor.py`
   (`TestSpliceRegion`) and `quorum-clean/scripts/splice_coauthor.py` bracket the identical text and
   report one digest rather than two that nearly agree. Normalization is line endings only:
   `"\n".join(region.replace("\r\n","\n").split("\n")).strip() + "\n"`. A mismatch fails the build.
3. The contract supplies `fetch(url,headers) -> {"status","headers","json","text"}` by wrapping
   `gl.nondet.web.request` (the field is `.status`) plus `json.loads`, and surfaces every tag unchanged.
