"""Unit tests for coauthor.py, the deterministic core of Quorum Clean.

Run either way:
    python test_coauthor.py
    pytest test_coauthor.py

The module under test has zero imports and no I/O. This file is allowed both: it imports json and
reads the pinned fixture manifest so the measured byte counts in the module cannot drift away from
_build/fixtures/quorum-clean/manifest.json.

Fixture note: the payloads below are constructed inline to satisfy the manifest's `expect` blocks
exactly (stable id A5069172917, authorships with stable ids, publication_year present,
per-contributor contributions counts, employments present), and a separate test asserts every
measured number against the manifest itself. One test reads a captured body from disk,
orcid-record.json, because the calendar-impossible dates on that real record are the thing it
regresses; it skips itself if the capture is absent.
"""

import hashlib
import json
import os
import unittest

import coauthor as C

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(
    HERE, "..", "fixtures", "quorum-clean", "manifest.json")

# Handles used throughout. A5069172917 is the stable id the manifest pins.
AID_REVIEWER = "A5069172917"
AID_APPLICANT = "A5023888391"
AID_THIRD = "A5044811191"
AID_STRANGER = "A5100000001"
ORCID_REVIEWER = "0000-0002-1825-0097"
ORCID_APPLICANT = "0000-0001-5109-3700"


# ---------------------------------------------------------------------------
# Injected fetch doubles. Nothing here touches a network.
# ---------------------------------------------------------------------------

class FakeFetch:
    """Records every call and replays canned responses keyed by URL substring."""

    def __init__(self, routes, default=None):
        self.routes = routes
        self.default = default
        self.calls = []

    def __call__(self, url, headers=None):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        for needle, resp in self.routes:
            if needle in url:
                return dict(resp)
        if self.default is not None:
            return dict(self.default)
        raise AssertionError("no fake route matched " + url)


def ok(payload, headers=None, text=None):
    return {"status": 200, "headers": headers or {"content-type": "application/json"},
            "json": payload, "text": text if text is not None else json.dumps(payload)}


def err(status, headers=None, payload=None, text=""):
    return {"status": status, "headers": headers or {}, "json": payload, "text": text}


def exploding_fetch(url, headers=None):
    raise AssertionError("fetch must not be reached: " + url)


# ---------------------------------------------------------------------------
# Inline payloads shaped to the manifest expect blocks.
# ---------------------------------------------------------------------------

def authorship(author_id, name):
    return {"author": {"id": "https://openalex.org/" + author_id, "display_name": name},
            "institutions": []}


# Two-author paper from 2024 (recent, small: the PRD's CONFLICT row) and a 40-author paper from
# 2016 (the MATERIAL_UNCLEAR row), plus a solo work and a work sharing only a third party.
WORK_SMALL_RECENT = {
    "id": "https://openalex.org/W2741809807",
    "title": "A two author paper",
    "publication_year": 2024,
    "authorships": [authorship(AID_REVIEWER, "R Reviewer"),
                    authorship(AID_APPLICANT, "A Applicant")],
}
WORK_BIG_OLD = {
    "id": "https://openalex.org/W1990000001",
    "title": "A forty author collaboration",
    "publication_year": 2016,
    "authorships": ([authorship(AID_REVIEWER, "R Reviewer"),
                     authorship(AID_APPLICANT, "A Applicant")]
                    + [authorship("A59%08d" % i, "Author %d" % i) for i in range(38)]),
}
WORK_SOLO = {
    "id": "https://openalex.org/W3000000003",
    "title": "A solo work",
    "publication_year": 2022,
    "authorships": [authorship(AID_REVIEWER, "R Reviewer")],
}
WORK_THIRD_PARTY = {
    "id": "https://openalex.org/W3000000004",
    "title": "Shares only a third party",
    "publication_year": 2021,
    "authorships": [authorship(AID_REVIEWER, "R Reviewer"), authorship(AID_THIRD, "T Third")],
}
WORK_NO_YEAR = {
    "id": "https://openalex.org/W3000000005",
    "title": "A work with no publication_year",
    "publication_year": None,
    "authorships": [authorship(AID_REVIEWER, "R Reviewer"), authorship(AID_APPLICANT, "A")],
}

OPENALEX_WORKS_REVIEWER = {
    "meta": {"count": 4, "per_page": 50},
    "results": [WORK_SMALL_RECENT, WORK_BIG_OLD, WORK_SOLO, WORK_THIRD_PARTY],
}
OPENALEX_WORKS_APPLICANT = {
    "meta": {"count": 2, "per_page": 50},
    "results": [
        dict(WORK_SMALL_RECENT),
        {"id": "https://openalex.org/W3000000009", "title": "Applicant solo",
         "publication_year": 2023,
         "authorships": [authorship(AID_APPLICANT, "A Applicant"),
                         authorship(AID_THIRD, "T Third")]},
    ],
}
OPENALEX_WORKS_STRANGER = {
    "meta": {"count": 1},
    "results": [{"id": "https://openalex.org/W4000000001", "title": "Unrelated",
                 "publication_year": 2020,
                 "authorships": [authorship(AID_STRANGER, "Same Name"),
                                 authorship("A5199999999", "Someone Else")]}],
}
OPENALEX_EMPTY = {"meta": {"count": 0}, "results": []}

OPENALEX_AUTHORS_HIT = {
    "meta": {"count": 1},
    "results": [{"id": "https://openalex.org/" + AID_REVIEWER, "display_name": "R Reviewer",
                 "orcid": "https://orcid.org/" + ORCID_REVIEWER, "works_count": 41}],
}
# Two distinct people sharing one name: the manifest's AMBIGUOUS route.
OPENALEX_AUTHORS_AMBIGUOUS = {
    "meta": {"count": 2},
    "results": [{"id": "https://openalex.org/" + AID_REVIEWER, "display_name": "Same Name",
                 "orcid": None, "works_count": 40},
                {"id": "https://openalex.org/" + AID_STRANGER, "display_name": "Same Name",
                 "orcid": None, "works_count": 38}],
}


def employment(org, put_code, start, end=None, role="Researcher"):
    def date_node(triple):
        if triple is None:
            return None
        y, m, d = triple
        node = {"year": {"value": str(y)}}
        node["month"] = {"value": "%02d" % m} if m else None
        node["day"] = {"value": "%02d" % d} if d else None
        return node
    return {"employment-summary": {
        "put-code": put_code,
        "organization": {"name": org},
        "role-title": role,
        "start-date": date_node(start),
        "end-date": date_node(end),
    }}


def orcid_record(orcid, employments):
    return {
        "orcid-identifier": {"path": orcid, "uri": "https://orcid.org/" + orcid},
        "activities-summary": {
            "employments": {"affiliation-group": [{"summaries": [e]} for e in employments]}},
    }


GITHUB_CONTRIBUTORS = [
    {"login": "topmaintainer", "contributions": 1841, "type": "User"},
    {"login": "dohernandez", "contributions": 412, "type": "User"},
    {"login": "vbuterin", "contributions": 301, "type": "User"},
    {"login": "fourth", "contributions": 210, "type": "User"},
    {"login": "fifth", "contributions": 120, "type": "User"},
    {"login": "sixth", "contributions": 44, "type": "User"},
    {"login": "seventh", "contributions": 20, "type": "User"},
    {"login": "eighth", "contributions": 7, "type": "User"},
    {"login": "typofixer", "contributions": 1, "type": "User"},
]
GITHUB_ORG_MEMBERS = [{"login": "dohernandez"}, {"login": "topmaintainer"}, {"login": "fifth"}]


class TestManifestPins(unittest.TestCase):
    """Every measured number in the module must match the pinned manifest."""

    @classmethod
    def setUpClass(cls):
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            cls.manifest = json.load(fh)
        cls.routes = {r["name"]: r for r in cls.manifest["routes"]}

    def test_manifest_has_ten_routes(self):
        self.assertEqual(len(self.manifest["routes"]), 10)

    def test_openalex_authors_bytes(self):
        self.assertEqual(C.MEASURED_OPENALEX_AUTHORS_BYTES,
                         self.routes["openalex-author-resolve"]["capture"]["measured_bytes"])

    def test_openalex_works_select_bytes(self):
        cap = self.routes["openalex-coauthors"]["capture"]
        self.assertEqual(C.MEASURED_OPENALEX_WORKS_SELECT_BYTES, cap["measured_bytes"])
        self.assertEqual(C.MEASURED_OPENALEX_WORKS_NO_SELECT_BYTES,
                         cap["measured_bytes_without_select"])
        self.assertEqual(cap["measured_bytes"], 6918)
        self.assertEqual(cap["measured_bytes_without_select"], 34362)

    def test_select_reduction_is_five_x(self):
        ratio = (C.MEASURED_OPENALEX_WORKS_NO_SELECT_BYTES
                 / float(C.MEASURED_OPENALEX_WORKS_SELECT_BYTES))
        self.assertEqual(round(ratio), 5)

    def test_orcid_bytes(self):
        cap = self.routes["orcid-record"]["capture"]
        self.assertEqual(C.MEASURED_ORCID_JSON_BYTES, cap["measured_bytes_json"])
        self.assertEqual(C.MEASURED_ORCID_XML_BYTES, cap["measured_bytes_xml"])

    def test_github_contributors_bytes(self):
        self.assertEqual(C.MEASURED_GITHUB_CONTRIBUTORS_BYTES,
                         self.routes["github-contributors"]["capture"]["measured_bytes"])
        self.assertEqual(C.MEASURED_GITHUB_CONTRIBUTORS_BYTES, 14054)

    def test_github_rate_limit_is_sixty(self):
        hdrs = self.routes["github-rate-limited"]["headers"]
        self.assertEqual(int(hdrs["x-ratelimit-limit"]), C.GITHUB_UNAUTH_HOURLY_LIMIT)
        self.assertEqual(C.GITHUB_UNAUTH_HOURLY_LIMIT, 60)
        self.assertEqual(self.routes["github-rate-limited"]["status"], 403)

    def test_stable_author_id_pinned(self):
        self.assertEqual(self.routes["openalex-author-resolve"]["expect"]["stable_id"],
                         AID_REVIEWER)

    def test_select_fields_match_capture_example(self):
        example = self.routes["openalex-coauthors"]["capture"]["example"]
        self.assertIn("select=" + C.OPENALEX_WORKS_SELECT, example)
        self.assertIn("per-page=" + str(C.OPENALEX_WORKS_PER_PAGE), example)

    def test_orcid_route_requires_accept_json(self):
        self.assertEqual(self.routes["orcid-record"]["requires_header"]["Accept"],
                         C.ORCID_HEADERS["Accept"])

    def test_module_has_zero_imports(self):
        import ast
        with open(os.path.join(HERE, "coauthor.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        found = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual(found, [], "coauthor.py must stay import-free for splicing")


SPLICE_BEGIN = "# --- QUORUM-COAUTHOR SPLICE BEGIN ---"
SPLICE_END = "# --- QUORUM-COAUTHOR SPLICE END ---"


def splice_region(text):
    """The text between the markers, normalized for line endings only.

    Kept as a module-level function with no test-only behaviour because
    quorum-clean/scripts/splice_coauthor.py copies these four lines verbatim. The suite's digest
    and the guard's digest have to be one number, not two that measure nearly the same text, so
    the normalization is written once and read twice rather than reimplemented on each side.
    """
    assert text.count(SPLICE_BEGIN) == 1, "expected exactly one BEGIN marker"
    assert text.count(SPLICE_END) == 1, "expected exactly one END marker"
    start = text.index(SPLICE_BEGIN) + len(SPLICE_BEGIN)
    stop = text.index(SPLICE_END)
    region = text[start:stop]
    return "\n".join(region.replace("\r\n", "\n").split("\n")).strip() + "\n"


class TestSpliceRegion(unittest.TestCase):
    """The drift guard's other half. The contract asserts against this exact digest."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "coauthor.py"), encoding="utf-8", newline="") as fh:
            cls.source = fh.read()
        cls.region = splice_region(cls.source)

    def test_markers_bracket_the_whole_module_body(self):
        """Everything except the docstring and the end-of-file sentinel is inside the region.

        A marker that drifted inward would silently leave a constant or a function behind in
        the source and out of the contract, and the digest would still be reproducible, so the
        boundary is asserted rather than assumed.
        """
        self.assertTrue(self.region.startswith("# ------"))
        self.assertIn("TAG_EXPECTED = \"[EXPECTED]\"", self.region)
        self.assertTrue(self.region.rstrip().endswith('return " | ".join(parts)'))
        after_end = self.source[self.source.index(SPLICE_END) + len(SPLICE_END):]
        self.assertEqual(after_end.strip(), "# --- END OF MODULE ---")

    def test_every_public_callable_is_inside_the_region(self):
        import ast
        tree = ast.parse(self.source)
        top_level = [n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        self.assertGreater(len(top_level), 50)
        missing = [name for name in top_level
                   if ("def %s(" % name) not in self.region
                   and ("class %s(" % name) not in self.region]
        self.assertEqual(missing, [], "these are defined outside the splice region")

    def test_splice_region_digest_is_reproducible(self):
        digest = hashlib.sha256(self.region.encode("utf-8")).hexdigest()
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, hashlib.sha256(
            splice_region(self.source).encode("utf-8")).hexdigest())
        print("\nsplice region: %d lines, %d bytes normalized, sha256 %s"
              % (self.region.count("\n"), len(self.region.encode("utf-8")), digest))


class TestErrorTaxonomy(unittest.TestCase):

    def test_exactly_four_tags(self):
        self.assertEqual(C.ALL_TAGS,
                         ("[EXPECTED]", "[EXTERNAL]", "[TRANSIENT]", "[LLM_ERROR]"))

    def test_each_class_carries_its_tag(self):
        self.assertEqual(C.ExpectedError("x").tag, C.TAG_EXPECTED)
        self.assertEqual(C.ExternalError("x").tag, C.TAG_EXTERNAL)
        self.assertEqual(C.TransientError("x").tag, C.TAG_TRANSIENT)
        self.assertEqual(C.LlmError("x").tag, C.TAG_LLM_ERROR)

    def test_tag_is_prefixed_on_the_message(self):
        self.assertTrue(str(C.ExternalError("boom")).startswith("[EXTERNAL] "))


class TestStatusClassification(unittest.TestCase):

    def test_200_is_usable(self):
        self.assertIsNone(C.classify_status(200))

    def test_403_rate_limited_is_external(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.classify_status(403, {"x-ratelimit-remaining": "0", "x-ratelimit-limit": "60"},
                              source="github")
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)
        self.assertIn("rate limited", ctx.exception.detail)
        self.assertIn("60", ctx.exception.detail)

    def test_403_without_ratelimit_headers_is_still_external(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.classify_status(403, {}, source="github")
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_429_is_external(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.classify_status(429, {"x-ratelimit-remaining": "0"}, source="github")
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_403_and_429_classify_identically(self):
        tags = []
        for status in (403, 429):
            try:
                C.classify_status(status, {"x-ratelimit-remaining": "0"}, source="github")
            except C.QuorumError as exc:
                tags.append(exc.tag)
        self.assertEqual(tags, [C.TAG_EXTERNAL, C.TAG_EXTERNAL])

    def test_404_is_external(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.classify_status(404, source="orcid")
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_500_is_transient(self):
        with self.assertRaises(C.TransientError) as ctx:
            C.classify_status(503, source="github")
        self.assertEqual(ctx.exception.tag, C.TAG_TRANSIENT)

    def test_status_zero_is_transient(self):
        with self.assertRaises(C.TransientError):
            C.classify_status(0, source="github")

    def test_400_is_our_own_bug(self):
        with self.assertRaises(C.ExpectedError) as ctx:
            C.classify_status(422, source="github")
        self.assertEqual(ctx.exception.tag, C.TAG_EXPECTED)

    def test_adapter_exception_becomes_transient(self):
        def boom(url, headers=None):
            raise OSError("connection reset")
        with self.assertRaises(C.TransientError) as ctx:
            C._call(boom, "https://api.github.com/x", source="github")
        self.assertIn("OSError", ctx.exception.detail)

    def test_non_callable_fetch_is_expected(self):
        with self.assertRaises(C.ExpectedError):
            C._call(None, "https://api.github.com/x")


class TestInstitutionNormalizationMerges(unittest.TestCase):
    """Two sources naming the same institution differently must resolve to one entity."""

    def test_case_and_whitespace(self):
        self.assertTrue(C.institutions_match("Ethereum Foundation", "ethereum   foundation"))

    def test_leading_the_is_structural(self):
        self.assertTrue(C.institutions_match("Ethereum Foundation", "The Ethereum Foundation"))

    def test_abbreviated_foundation(self):
        self.assertTrue(C.institutions_match("Ethereum Foundation", "Ethereum Fdn."))

    def test_openalex_vs_orcid_spelling(self):
        # OpenAlex returned "Ethereum Foundation" live; ORCID records often carry the legal form.
        self.assertEqual(C.normalize_institution("Ethereum Foundation"), "ethereum foundation")
        self.assertEqual(C.normalize_institution("ETHEREUM FOUNDATION, "), "ethereum foundation")

    def test_accented_form_folds_to_ascii(self):
        self.assertTrue(C.institutions_match("Universite de Geneve", "Université de Genève"))

    def test_university_abbreviation(self):
        self.assertTrue(C.institutions_match("Stanford University", "Stanford Univ."))

    def test_institute_abbreviation_and_of(self):
        self.assertTrue(C.institutions_match("Massachusetts Institute of Technology",
                                             "Massachusetts Inst. of Technology"))

    def test_ampersand_and_punctuation(self):
        self.assertTrue(C.institutions_match("Ernst & Young LLP", "Ernst and Young LLP"))

    def test_german_university_forms(self):
        self.assertTrue(C.institutions_match("Universität Zürich", "Universitat Zurich"))

    def test_laboratory_plural(self):
        self.assertTrue(C.institutions_match("Bell Labs", "Bell Laboratory"))


class TestInstitutionNormalizationRefusals(unittest.TestCase):
    """A normalization aggressive enough to merge two different institutions is worse than one
    that misses a match, so these must all stay distinct."""

    def test_berkeley_is_not_ucla(self):
        self.assertFalse(C.institutions_match("University of California, Berkeley",
                                              "University of California, Los Angeles"))

    def test_ethereum_is_not_ethereum_classic(self):
        self.assertFalse(C.institutions_match("Ethereum Foundation",
                                              "Ethereum Classic Foundation"))

    def test_two_max_planck_institutes(self):
        self.assertFalse(C.institutions_match("Max Planck Institute for Physics",
                                              "Max Planck Institute for Chemistry"))

    def test_no_acronym_synthesis(self):
        # A deliberate miss: expanding MIT would require inventing an acronym rule, and an
        # invented rule that merges MIT with Manchester Institute of Technology would downweight
        # an innocent reviewer. Missing this match is the safe direction.
        self.assertFalse(C.institutions_match("MIT", "Massachusetts Institute of Technology"))

    def test_tech_is_not_expanded(self):
        self.assertFalse(C.institutions_match("Caltech", "California Institute of Technology"))
        self.assertFalse(C.institutions_match("Georgia Tech", "Caltech"))

    def test_different_universities_same_country_word(self):
        self.assertFalse(C.institutions_match("University of Washington",
                                              "Washington University"))

    def test_empty_key_never_matches(self):
        self.assertEqual(C.normalize_institution("   ,,, "), "")
        self.assertFalse(C.institutions_match("", ""))
        self.assertFalse(C.institutions_match("The", "of"))

    def test_non_string_input_is_expected_error(self):
        with self.assertRaises(C.ExpectedError):
            C.normalize_institution(None)


class TestNameAndRepoNormalization(unittest.TestCase):

    def test_person_name_reorders_comma_form(self):
        self.assertEqual(C.normalize_person_name("Buterin, Vitalik"), "vitalik buterin")
        self.assertEqual(C.normalize_person_name("Vitalik Buterin"), "vitalik buterin")

    def test_person_name_folds_accents(self):
        self.assertEqual(C.normalize_person_name("José García"), "jose garcia")

    def test_repo_forms_all_normalize_to_one(self):
        want = "owner/repo"
        for raw in ("Owner/Repo", "owner/repo/", "https://github.com/Owner/Repo",
                    "https://github.com/Owner/Repo.git", "git@github.com:Owner/Repo.git",
                    "http://www.github.com/OWNER/REPO", "api.github.com/repos/Owner/Repo"):
            self.assertEqual(C.normalize_repo_id(raw), want, raw)

    def test_repo_owner_and_name_stay_distinct(self):
        self.assertNotEqual(C.normalize_repo_id("alice/tools"), C.normalize_repo_id("bob/tools"))

    def test_repo_rejects_ambiguous_input(self):
        for bad in ("", "just-a-name", "a/b/c", "owner/re po"):
            with self.assertRaises(C.ExpectedError, msg=bad):
                C.normalize_repo_id(bad)

    def test_github_login_case_insensitive(self):
        self.assertEqual(C.normalize_github_login("@DoHernandez"), "dohernandez")

    def test_github_login_rejects_junk(self):
        with self.assertRaises(C.ExpectedError):
            C.normalize_github_login("bad login!")


class TestOrcidNormalization(unittest.TestCase):

    def test_accepts_bare_and_url_forms(self):
        for raw in (ORCID_REVIEWER, "https://orcid.org/" + ORCID_REVIEWER,
                    "orcid.org/" + ORCID_REVIEWER, ORCID_REVIEWER.replace("-", "")):
            self.assertEqual(C.normalize_orcid(raw), ORCID_REVIEWER, raw)

    def test_checksum_x_allowed(self):
        self.assertEqual(C.normalize_orcid("0000-0002-1694-233X"), "0000-0002-1694-233X")

    def test_rejects_wrong_length(self):
        with self.assertRaises(C.ExpectedError):
            C.normalize_orcid("0000-0002-1825")

    def test_the_check_digit_algorithm_agrees_with_five_published_ids(self):
        """The algorithm is checked against iDs nobody in this project chose.

        A checksum implemented from a spec and tested only against its own output is a tautology.
        These five are published ORCID iDs, one of them ending in X, which is what remainder 10
        renders as and the case a naive implementation gets wrong.
        """
        for known in ("0000-0002-1825-0097",          # ORCID's own canonical demo record
                      "0000-0001-5109-3700",
                      "0000-0002-1694-233X",
                      "0000-0002-9079-593X",
                      "0000-0003-1613-5981"):
            digits = known.replace("-", "")
            self.assertEqual(C.orcid_check_digit(digits[:15]), digits[15], known)
            self.assertEqual(C.normalize_orcid(known), known)

    def test_a_single_mistyped_digit_is_refused_at_the_door(self):
        """The reason this check is worth having, stated as a test.

        `0000-0002-1825-0097` is real and `0000-0002-1825-0099` is one keystroke away from it. With
        shape checks alone the typo is accepted, stored as a declared handle, and then answers 404
        at every screening for the life of the round: [EXTERNAL], INSUFFICIENT, retryable, and no
        retry that can ever work. Refusing it costs one line and no network call.
        """
        with self.assertRaises(C.ExpectedError) as ctx:
            C.normalize_orcid("0000-0002-1825-0099")
        self.assertEqual(ctx.exception.tag, C.TAG_EXPECTED)
        self.assertIn("check digit", ctx.exception.detail)
        self.assertIn("require 7", ctx.exception.detail)

    def test_the_fixture_404_id_is_refused_so_the_route_needs_a_valid_one(self):
        """0000-0002-1825-0000 is the iD the fixture manifest keyed its 404 route on.

        It fails the check digit, which requires 3. That makes the route unreachable through
        `register_participant`, so the manifest carries a second, checksum-valid iD for the route
        to be selected by. Pinned here because the two files have to move together.
        """
        with self.assertRaises(C.ExpectedError):
            C.normalize_orcid("0000-0002-1825-0000")
        self.assertEqual(C.normalize_orcid("0000-0002-1825-0003"), "0000-0002-1825-0003")

    def test_normalize_orcid_maybe_swallows_a_bad_check_digit_too(self):
        """The OpenAlex `orcid` field is third-party text, so a bad one there is an absence.

        `normalize_orcid_maybe` exists for exactly this: a field somebody else published, which is
        allowed to be missing or wrong without reverting our screening. It must not start raising
        because the underlying validator got stricter, and it must not report a wrong iD as a
        usable one either.
        """
        self.assertEqual(C.normalize_orcid_maybe("0000-0002-1825-0099"), "")
        self.assertTrue(C.check_handle_consistency(ORCID_REVIEWER, "0000-0002-1825-0099"))

    def test_maybe_returns_empty_for_absent(self):
        self.assertEqual(C.normalize_orcid_maybe(None), "")
        self.assertEqual(C.normalize_orcid_maybe(""), "")
        self.assertEqual(C.normalize_orcid_maybe("not an orcid"), "")

    def test_handle_consistency_agrees(self):
        self.assertTrue(C.check_handle_consistency(
            ORCID_REVIEWER, "https://orcid.org/" + ORCID_REVIEWER))

    def test_handle_consistency_contradiction_is_expected(self):
        with self.assertRaises(C.ExpectedError) as ctx:
            C.check_handle_consistency(ORCID_REVIEWER, "https://orcid.org/" + ORCID_APPLICANT)
        self.assertEqual(ctx.exception.tag, C.TAG_EXPECTED)

    def test_absent_openalex_orcid_is_not_a_contradiction(self):
        self.assertTrue(C.check_handle_consistency(ORCID_REVIEWER, None))


class TestOpenAlexSelectGuard(unittest.TestCase):
    """A call without select= is a bug even when it works: 34,362 B against 6,918 B, and payload
    size is a consensus cost paid by every validator."""

    def test_builder_always_emits_select(self):
        url = C.build_openalex_works_url(AID_REVIEWER)
        self.assertIn("select=" + C.OPENALEX_WORKS_SELECT, url)
        self.assertIn("filter=author.id:" + AID_REVIEWER, url)
        self.assertIn("per-page=50", url)
        self.assertTrue(C.assert_openalex_select(url))

    def test_url_without_select_is_rejected(self):
        bare = "https://api.openalex.org/works?filter=author.id:" + AID_REVIEWER
        with self.assertRaises(C.ExpectedError) as ctx:
            C.assert_openalex_select(bare)
        self.assertEqual(ctx.exception.tag, C.TAG_EXPECTED)
        self.assertIn("no select=", ctx.exception.detail)

    def test_rejection_message_quotes_the_measurement(self):
        bare = "https://api.openalex.org/works?filter=author.id:" + AID_REVIEWER
        with self.assertRaises(C.ExpectedError) as ctx:
            C.assert_openalex_select(bare)
        self.assertIn("34362", ctx.exception.detail)
        self.assertIn("6918", ctx.exception.detail)

    def test_empty_select_is_rejected(self):
        with self.assertRaises(C.ExpectedError):
            C.assert_openalex_select("https://api.openalex.org/works?filter=x&select=")

    def test_select_missing_publication_year_is_rejected(self):
        url = "https://api.openalex.org/works?filter=x&select=id,title,authorships"
        with self.assertRaises(C.ExpectedError) as ctx:
            C.assert_openalex_select(url)
        self.assertIn("publication_year", ctx.exception.detail)

    def test_select_missing_authorships_is_rejected(self):
        url = "https://api.openalex.org/works?filter=x&select=id,publication_year"
        with self.assertRaises(C.ExpectedError):
            C.assert_openalex_select(url)

    def test_url_encoded_select_list_is_accepted(self):
        url = ("https://api.openalex.org/works?filter=x"
               "&select=id%2Ctitle%2Cauthorships%2Cpublication_year")
        self.assertTrue(C.assert_openalex_select(url))

    def test_fetch_path_sends_select(self):
        fake = FakeFetch([("api.openalex.org/works", ok(OPENALEX_WORKS_REVIEWER))])
        C.fetch_openalex_works(fake, AID_REVIEWER)
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("select=", fake.calls[0]["url"])

    def test_bad_author_id_never_reaches_the_network(self):
        with self.assertRaises(C.ExpectedError):
            C.fetch_openalex_works(exploding_fetch, "not-an-id")

    def test_author_id_accepts_url_form(self):
        self.assertEqual(C.validate_openalex_author_id(
            "https://openalex.org/" + AID_REVIEWER), AID_REVIEWER)

    def test_author_search_url_percent_encodes(self):
        url = C.build_openalex_author_search_url("Vitalik Buterin")
        self.assertEqual(url, "https://api.openalex.org/authors?search=Vitalik%20Buterin")


class TestCoauthorshipExtraction(unittest.TestCase):

    def setUp(self):
        self.graph = C.extract_coauthorship(OPENALEX_WORKS_REVIEWER, AID_REVIEWER)

    def test_all_works_extracted(self):
        self.assertEqual(len(self.graph["works"]), 4)

    def test_works_are_sorted_for_determinism(self):
        ids = [w["work_id"] for w in self.graph["works"]]
        self.assertEqual(ids, sorted(ids))

    def test_focus_author_excluded_from_coauthors(self):
        self.assertNotIn(AID_REVIEWER, self.graph["coauthor_ids"])

    def test_stable_coauthor_ids_present(self):
        self.assertIn(AID_APPLICANT, self.graph["coauthor_ids"])
        self.assertIn(AID_THIRD, self.graph["coauthor_ids"])

    def test_author_count_recorded_per_work(self):
        by_id = {w["work_id"]: w for w in self.graph["works"]}
        self.assertEqual(by_id["https://openalex.org/W2741809807"]["author_count"], 2)
        self.assertEqual(by_id["https://openalex.org/W1990000001"]["author_count"], 40)

    def test_publication_year_recorded(self):
        by_id = {w["work_id"]: w for w in self.graph["works"]}
        self.assertEqual(by_id["https://openalex.org/W2741809807"]["year"], 2024)
        self.assertEqual(by_id["https://openalex.org/W1990000001"]["year"], 2016)

    def test_solo_work_has_no_coauthors(self):
        by_id = {w["work_id"]: w for w in self.graph["works"]}
        self.assertEqual(by_id["https://openalex.org/W3000000003"]["coauthor_ids"], ())

    def test_direct_overlap_finds_both_shared_works(self):
        ties = C.coauthorship_overlap(self.graph, AID_APPLICANT)
        self.assertEqual([t["tie_basis"] for t in ties],
                         ["https://openalex.org/W1990000001",
                          "https://openalex.org/W2741809807"])
        self.assertTrue(all(t["tie_kind"] == C.TIE_COAUTHOR for t in ties))

    def test_no_overlap_with_a_stranger(self):
        self.assertEqual(C.coauthorship_overlap(self.graph, AID_STRANGER), [])

    def test_third_party_coauthor_is_reported_separately(self):
        other = C.extract_coauthorship(OPENALEX_WORKS_APPLICANT, AID_APPLICANT)
        shared = C.shared_third_party_coauthors(self.graph, other)
        self.assertEqual(shared, (AID_THIRD,))

    def test_empty_results_is_external_not_clean(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.extract_coauthorship(OPENALEX_EMPTY, AID_REVIEWER)
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_missing_authorships_field_is_external(self):
        payload = {"results": [{"id": "https://openalex.org/W1", "publication_year": 2020}]}
        with self.assertRaises(C.ExternalError) as ctx:
            C.extract_coauthorship(payload, AID_REVIEWER)
        self.assertIn("select=", ctx.exception.detail)

    def test_undated_work_is_reported_not_dropped(self):
        payload = {"results": [WORK_SMALL_RECENT, WORK_NO_YEAR]}
        graph = C.extract_coauthorship(payload, AID_REVIEWER)
        self.assertEqual(graph["undated_work_ids"], ("https://openalex.org/W3000000005",))
        ties = C.coauthorship_overlap(graph, AID_APPLICANT,
                                      window=C.coi_window_from_years(2020, 2026))
        undated = [t for t in ties if t["undetermined"]]
        self.assertEqual(len(undated), 1)
        self.assertIsNone(undated[0]["in_window"])

    def test_year_in_window_refuses_to_guess_a_missing_year(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.year_in_window(None, C.coi_window_from_years(2020, 2024))
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_screening_an_author_against_themselves_is_expected(self):
        with self.assertRaises(C.ExpectedError):
            C.coauthorship_overlap(self.graph, AID_REVIEWER)

    def test_ambiguous_name_yields_no_false_conflict(self):
        # Two people share one display name. Identity comes from the declared handle, so screening
        # the reviewer against the stranger's id finds nothing, and the name match is irrelevant.
        authors = C.parse_openalex_authors(OPENALEX_AUTHORS_AMBIGUOUS)
        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0]["name_key"], authors[1]["name_key"])
        self.assertNotEqual(authors[0]["author_id"], authors[1]["author_id"])
        self.assertEqual(C.coauthorship_overlap(self.graph, AID_STRANGER), [])

    def test_author_search_no_match_is_external(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.parse_openalex_authors(OPENALEX_EMPTY)
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_author_search_carries_orcid_field(self):
        authors = C.parse_openalex_authors(OPENALEX_AUTHORS_HIT)
        self.assertEqual(authors[0]["orcid"], ORCID_REVIEWER)
        self.assertEqual(authors[0]["author_id"], AID_REVIEWER)


class TestOrcidHeaderDiscipline(unittest.TestCase):
    """ORCID returns HTTP 200 and 44,000 B of XML without Accept: application/json. A check that
    only asks whether the request succeeded sees success and then finds no employment overlap in
    bytes it cannot parse."""

    def test_module_header_constant(self):
        self.assertEqual(C.ORCID_HEADERS, {"Accept": "application/json"})

    def test_missing_accept_header_is_rejected_before_the_call(self):
        with self.assertRaises(C.ExpectedError) as ctx:
            C.fetch_orcid_record(exploding_fetch, ORCID_REVIEWER, headers={})
        self.assertEqual(ctx.exception.tag, C.TAG_EXPECTED)
        self.assertIn("Accept: application/json", ctx.exception.detail)

    def test_rejection_message_quotes_both_measurements(self):
        with self.assertRaises(C.ExpectedError) as ctx:
            C.assert_orcid_json_headers({"Accept": "application/xml"})
        self.assertIn("44000", ctx.exception.detail)
        self.assertIn("22492", ctx.exception.detail)

    def test_default_call_sends_the_header(self):
        record = orcid_record(ORCID_REVIEWER,
                              [employment("Ethereum Foundation", 1, (2015, 7, 1), (2019, 6, 30))])
        fake = FakeFetch([("pub.orcid.org", ok(record))])
        C.fetch_orcid_record(fake, ORCID_REVIEWER)
        self.assertEqual(fake.calls[0]["headers"].get("Accept"), "application/json")
        self.assertEqual(fake.calls[0]["url"],
                         "https://pub.orcid.org/v3.0/" + ORCID_REVIEWER + "/record")

    def test_xml_body_with_200_is_external_not_success(self):
        xml = ('<?xml version="1.0"?><record:record xmlns:record="http://www.orcid.org/ns/record">'
               "</record:record>")
        fake = FakeFetch([("pub.orcid.org", {"status": 200,
                                             "headers": {"content-type": "application/vnd.orcid+xml"},
                                             "json": None, "text": xml})])
        with self.assertRaises(C.ExternalError) as ctx:
            C.fetch_orcid_record(fake, ORCID_REVIEWER)
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)
        self.assertIn("NOT an absence of conflict", ctx.exception.detail)

    def test_unparseable_body_is_external(self):
        fake = FakeFetch([("pub.orcid.org", {"status": 200, "headers": {}, "json": None,
                                             "text": "not json at all"})])
        with self.assertRaises(C.ExternalError):
            C.fetch_orcid_record(fake, ORCID_REVIEWER)

    def test_404_orcid_is_external(self):
        fake = FakeFetch([("pub.orcid.org", err(404, text='{"error":"not found"}'))])
        with self.assertRaises(C.ExternalError) as ctx:
            C.fetch_orcid_record(fake, ORCID_REVIEWER)
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)


class TestEmploymentExtraction(unittest.TestCase):

    def test_extracts_org_and_interval(self):
        rec = orcid_record(ORCID_REVIEWER,
                           [employment("Ethereum Foundation", 101, (2015, 7, 1), (2019, 6, 30))])
        out = C.extract_employments(rec)
        self.assertEqual(out["orcid"], ORCID_REVIEWER)
        self.assertEqual(len(out["employments"]), 1)
        emp = out["employments"][0]
        self.assertEqual(emp["org_key"], "ethereum foundation")
        self.assertEqual(emp["start"], (2015, 7, 1))
        self.assertEqual(emp["end"], (2019, 6, 30))
        self.assertFalse(emp["imputed"])
        self.assertEqual(emp["put_code"], "101")

    def test_open_end_date_means_present(self):
        rec = orcid_record(ORCID_APPLICANT, [employment("Ethereum Fdn.", 102, (2018, 1, 1), None)])
        emp = C.extract_employments(rec)["employments"][0]
        self.assertEqual(emp["end"], C.OPEN_END)
        self.assertEqual(C.fmt_date(emp["end"]), "present")

    def test_partial_dates_are_widened_and_flagged(self):
        rec = orcid_record(ORCID_REVIEWER,
                           [employment("Bell Labs", 103, (2010, None, None), (2012, None, None))])
        emp = C.extract_employments(rec)["employments"][0]
        self.assertEqual(emp["start"], (2010, 1, 1))
        self.assertEqual(emp["end"], (2012, 12, 31))
        self.assertTrue(emp["imputed"])

    def test_missing_start_date_is_unusable_not_absent(self):
        rec = orcid_record(ORCID_REVIEWER, [employment("Bell Labs", 104, None, (2012, 5, 1))])
        out = C.extract_employments(rec)
        self.assertEqual(out["employments"], [])
        self.assertEqual(len(out["unusable"]), 1)
        self.assertIn("start date", out["unusable"][0]["reason"])

    def test_missing_employments_section_is_external(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.extract_employments({"orcid-identifier": {"path": ORCID_REVIEWER},
                                   "activities-summary": {}})
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_employments_sorted_for_determinism(self):
        rec = orcid_record(ORCID_REVIEWER, [
            employment("Zeta Institute", 3, (2019, 1, 1), (2020, 1, 1)),
            employment("Alpha Foundation", 1, (2015, 1, 1), (2016, 1, 1)),
            employment("Alpha Foundation", 2, (2011, 1, 1), (2012, 1, 1)),
        ])
        keys = [(e["org_key"], e["start"]) for e in C.extract_employments(rec)["employments"]]
        self.assertEqual(keys, sorted(keys))

    def test_leap_day_is_valid(self):
        rec = orcid_record(ORCID_REVIEWER, [employment("X Foundation", 1, (2020, 2, 29))])
        self.assertEqual(C.extract_employments(rec)["employments"][0]["start"], (2020, 2, 29))

    def test_non_leap_february_29_is_rejected(self):
        with self.assertRaises(C.ExpectedError):
            C.make_date(2021, 2, 29)

    def test_a_calendar_impossible_date_is_unusable_not_a_caller_error(self):
        """29 February 1930 exists on a real ORCID record and on no calendar.

        `make_date` refuses it as [EXPECTED], which is right for a caller constructing that date and
        wrong for a third party publishing one. The two arrive at the same function, so the record
        parser has to tell them apart: the row is unusable evidence, the rest of the record stands,
        and nothing raises. Letting [EXPECTED] out of here reverts the whole screening in the
        contract, permanently, because the date will not change on retry.
        """
        rec = orcid_record(ORCID_REVIEWER, [employment("Brown University", 4278, (1930, 2, 29))])
        out = C.extract_employments(rec)
        self.assertEqual(out["employments"], [])
        self.assertEqual(len(out["unusable"]), 1)
        self.assertIn("unusable date", out["unusable"][0]["reason"])
        self.assertIn("day out of range", out["unusable"][0]["reason"])
        self.assertEqual(out["unusable"][0]["put_code"], "4278")

    def test_one_impossible_date_does_not_destroy_the_other_rows(self):
        rec = orcid_record(ORCID_REVIEWER, [
            employment("Brown University", 1, (1930, 2, 29)),
            employment("Ethereum Foundation", 2, (2015, 7, 1), (2019, 6, 30)),
        ])
        out = C.extract_employments(rec)
        self.assertEqual([e["org_key"] for e in out["employments"]], ["ethereum foundation"])
        self.assertEqual(len(out["unusable"]), 1)

    def test_an_unusable_end_date_is_recorded_rather_than_read_as_present(self):
        """An end date that will not parse must not silently become the open-end sentinel.

        OPEN_END means "still there", which widens every overlap to today. Reaching it by way of a
        date nobody could read would manufacture overlaps out of a parse failure.
        """
        rec = orcid_record(ORCID_REVIEWER,
                           [employment("X Foundation", 9, (2015, 1, 1), (2018, 2, 30))])
        out = C.extract_employments(rec)
        self.assertEqual(out["employments"], [])
        self.assertIn("unusable date", out["unusable"][0]["reason"])

    def test_the_captured_orcid_record_parses_without_raising(self):
        """The real captured body, not a constructed one.

        0000-0002-1825-0097 is ORCID's canonical public record and the URL this project's manifest
        captured. Both of its employments carry 29 February in a non-leap year, so before the parser
        told a published bad date apart from a caller's bad date, this exact file made `screen`
        revert with [EXPECTED] and no retry could ever clear it.
        """
        path = os.path.join(os.path.dirname(MANIFEST_PATH), "orcid-record.json")
        if not os.path.exists(path):                      # capture not on disk in this checkout
            self.skipTest("orcid-record.json not captured")
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
        out = C.extract_employments(record)
        self.assertEqual(out["orcid"], ORCID_REVIEWER)
        self.assertEqual(out["employments"], [])
        self.assertEqual(len(out["unusable"]), 2)
        self.assertEqual(sorted(e["org_raw"] for e in out["unusable"]),
                         ["Brown University", "Wesleyan University"])
        for entry in out["unusable"]:
            self.assertIn("unusable date", entry["reason"])
        # And the pair of them yields no tie, which is why a caller may not read this as CLEAR.
        self.assertEqual(C.employment_overlap(out, out), [])


class TestEmploymentOverlap(unittest.TestCase):
    """Two people at the same institution during overlapping ranges is an overlap; the same
    institution at disjoint times is not."""

    def _emps(self, *specs):
        return C.extract_employments(orcid_record(ORCID_REVIEWER, list(specs)))

    def test_overlapping_dates_produce_a_tie(self):
        a = self._emps(employment("Ethereum Foundation", 1, (2015, 7, 1), (2019, 6, 30)))
        b = self._emps(employment("The Ethereum Fdn.", 2, (2018, 1, 1), None))
        ties = C.employment_overlap(a, b)
        self.assertEqual(len(ties), 1)
        tie = ties[0]
        self.assertEqual(tie["tie_kind"], C.TIE_SHARED_AFFILIATION)
        self.assertEqual(tie["overlap_start"], (2018, 1, 1))
        self.assertEqual(tie["overlap_end"], (2019, 6, 30))
        self.assertEqual(tie["org_key"], "ethereum foundation")
        self.assertEqual(tie["tie_basis"], "ethereum foundation 2018-01-01..2019-06-30")

    def test_overlap_months_counted_inclusively(self):
        a = self._emps(employment("X Foundation", 1, (2020, 1, 1), (2020, 3, 31)))
        b = self._emps(employment("X Foundation", 2, (2020, 1, 1), (2020, 3, 31)))
        self.assertEqual(C.employment_overlap(a, b)[0]["overlap_months"], 3)

    def test_disjoint_dates_at_the_same_institution_is_no_tie(self):
        a = self._emps(employment("Ethereum Foundation", 1, (2015, 7, 1), (2019, 6, 30)))
        b = self._emps(employment("Ethereum Foundation", 2, (2021, 1, 1), (2022, 12, 31)))
        self.assertEqual(C.employment_overlap(a, b), [])

    def test_adjacent_intervals_touch_on_one_day_and_do_overlap(self):
        # Closed intervals: 2019-06-30 is the last day of one and the first day of the other, so
        # they share exactly that day. Documented as inclusive.
        a = self._emps(employment("X Foundation", 1, (2015, 1, 1), (2019, 6, 30)))
        b = self._emps(employment("X Foundation", 2, (2019, 6, 30), (2021, 1, 1)))
        ties = C.employment_overlap(a, b)
        self.assertEqual(len(ties), 1)
        self.assertEqual(ties[0]["overlap_start"], (2019, 6, 30))
        self.assertEqual(ties[0]["overlap_end"], (2019, 6, 30))
        self.assertEqual(ties[0]["overlap_months"], 1)

    def test_one_day_apart_does_not_overlap(self):
        a = self._emps(employment("X Foundation", 1, (2015, 1, 1), (2019, 6, 29)))
        b = self._emps(employment("X Foundation", 2, (2019, 6, 30), (2021, 1, 1)))
        self.assertEqual(C.employment_overlap(a, b), [])

    def test_different_institutions_never_overlap_however_close_the_dates(self):
        a = self._emps(employment("University of California, Berkeley", 1, (2015, 1, 1), None))
        b = self._emps(employment("University of California, Los Angeles", 2, (2015, 1, 1), None))
        self.assertEqual(C.employment_overlap(a, b), [])

    def test_two_spellings_of_one_institution_do_overlap(self):
        a = self._emps(employment("Université de Genève", 1, (2015, 1, 1), None))
        b = self._emps(employment("Universite de Geneve", 2, (2016, 1, 1), None))
        self.assertEqual(len(C.employment_overlap(a, b)), 1)

    def test_imputed_flag_propagates_to_the_tie(self):
        a = self._emps(employment("X Foundation", 1, (2010, None, None), (2012, None, None)))
        b = self._emps(employment("X Foundation", 2, (2012, 12, 31), None))
        ties = C.employment_overlap(a, b)
        self.assertEqual(len(ties), 1)
        self.assertTrue(ties[0]["imputed"])


class TestCoiWindowBoundaries(unittest.TestCase):
    """BOTH ENDS OF THE COI WINDOW ARE INCLUSIVE. These two cases pin that decision."""

    WINDOW = C.coi_window_from_years(2020, 2024)

    def test_window_construction(self):
        self.assertEqual(self.WINDOW, ((2020, 1, 1), (2024, 12, 31)))

    def test_overlap_ending_exactly_on_the_first_day_is_inside(self):
        self.assertTrue(C.overlap_in_window((2018, 5, 1), (2020, 1, 1), self.WINDOW))

    def test_overlap_ending_one_day_before_the_first_day_is_outside(self):
        self.assertFalse(C.overlap_in_window((2018, 5, 1), (2019, 12, 31), self.WINDOW))

    def test_overlap_starting_exactly_on_the_last_day_is_inside(self):
        self.assertTrue(C.overlap_in_window((2024, 12, 31), (2026, 5, 1), self.WINDOW))

    def test_overlap_starting_one_day_after_the_last_day_is_outside(self):
        self.assertFalse(C.overlap_in_window((2025, 1, 1), (2026, 5, 1), self.WINDOW))

    def test_single_day_overlap_at_each_boundary(self):
        self.assertTrue(C.overlap_in_window((2020, 1, 1), (2020, 1, 1), self.WINDOW))
        self.assertTrue(C.overlap_in_window((2024, 12, 31), (2024, 12, 31), self.WINDOW))

    def test_employment_tie_on_the_first_day_boundary_is_in_window(self):
        a = C.extract_employments(orcid_record(
            ORCID_REVIEWER, [employment("X Foundation", 1, (2016, 1, 1), (2020, 1, 1))]))
        b = C.extract_employments(orcid_record(
            ORCID_APPLICANT, [employment("X Foundation", 2, (2020, 1, 1), (2021, 1, 1))]))
        ties = C.employment_overlap(a, b, window=self.WINDOW)
        self.assertEqual(len(ties), 1)
        self.assertEqual(ties[0]["overlap_start"], (2020, 1, 1))
        self.assertTrue(ties[0]["in_window"])

    def test_employment_tie_on_the_last_day_boundary_is_in_window(self):
        a = C.extract_employments(orcid_record(
            ORCID_REVIEWER, [employment("X Foundation", 1, (2024, 12, 31), (2026, 1, 1))]))
        b = C.extract_employments(orcid_record(
            ORCID_APPLICANT, [employment("X Foundation", 2, (2023, 1, 1), (2026, 6, 1))]))
        ties = C.employment_overlap(a, b, window=self.WINDOW)
        self.assertEqual(len(ties), 1)
        self.assertEqual(ties[0]["overlap_start"], (2024, 12, 31))
        self.assertTrue(ties[0]["in_window"])

    def test_the_same_overlap_outside_the_window_is_not_a_conflict(self):
        a = C.extract_employments(orcid_record(
            ORCID_REVIEWER, [employment("X Foundation", 1, (2010, 1, 1), (2012, 1, 1))]))
        b = C.extract_employments(orcid_record(
            ORCID_APPLICANT, [employment("X Foundation", 2, (2011, 1, 1), (2013, 1, 1))]))
        ties = C.employment_overlap(a, b, window=self.WINDOW)
        self.assertEqual(len(ties), 1)
        self.assertFalse(ties[0]["in_window"])
        ledger = C.record_checked(C.new_ledger(), C.SOURCE_ORCID)
        result = C.screen_verdict(ledger, affiliation_ties=ties)
        self.assertEqual(result["verdict"], C.VERDICT_CLEAR)
        self.assertEqual(result["tie_kind"], C.TIE_NONE)

    def test_publication_year_window_edges(self):
        self.assertTrue(C.year_in_window(2020, self.WINDOW))
        self.assertTrue(C.year_in_window(2024, self.WINDOW))
        self.assertFalse(C.year_in_window(2019, self.WINDOW))
        self.assertFalse(C.year_in_window(2025, self.WINDOW))

    def test_interval_overlap_rejects_inverted_intervals(self):
        with self.assertRaises(C.ExpectedError):
            C.interval_overlap((2020, 1, 2), (2020, 1, 1), (2020, 1, 1), (2020, 1, 3))

    def test_window_years_must_be_ordered(self):
        with self.assertRaises(C.ExpectedError):
            C.coi_window_from_years(2024, 2020)


class TestGithubContributionOverlap(unittest.TestCase):

    def setUp(self):
        self.contribs = C.extract_contributors(GITHUB_CONTRIBUTORS, "owner/repo")

    def test_contributions_counts_extracted(self):
        self.assertEqual(self.contribs["dohernandez"], 412)
        self.assertEqual(self.contribs["typofixer"], 1)

    def test_logins_lowercased(self):
        payload = [{"login": "DoHernandez", "contributions": 5}]
        self.assertEqual(C.extract_contributors(payload, "o/r"), {"dohernandez": 5})

    def test_missing_contributions_count_is_external(self):
        payload = [{"login": "someone"}]
        with self.assertRaises(C.ExternalError) as ctx:
            C.extract_contributors(payload, "o/r")
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)
        self.assertIn("contributions", ctx.exception.detail)

    def test_empty_contributor_list_is_external_not_clean(self):
        with self.assertRaises(C.ExternalError) as ctx:
            C.extract_contributors([], "owner/repo")
        self.assertEqual(ctx.exception.tag, C.TAG_EXTERNAL)

    def test_ranks_are_deterministic(self):
        ranks = C.rank_contributors(self.contribs)
        self.assertEqual(ranks["topmaintainer"], 1)
        self.assertEqual(ranks["dohernandez"], 2)
        self.assertEqual(ranks["typofixer"], 9)

    def test_rank_ties_broken_by_login(self):
        ranks = C.rank_contributors({"bob": 10, "alice": 10})
        self.assertEqual(ranks["alice"], 1)
        self.assertEqual(ranks["bob"], 2)

    def test_two_top_contributors_overlap(self):
        tie = C.contribution_overlap("Owner/Repo", self.contribs, "dohernandez", "vbuterin")
        self.assertIsNotNone(tie)
        self.assertEqual(tie["tie_kind"], C.TIE_CODE_CONTRIBUTION)
        self.assertEqual(tie["tie_basis"], "owner/repo")
        self.assertEqual(tie["contributions_a"], 412)
        self.assertEqual(tie["contributions_b"], 301)
        self.assertEqual((tie["rank_a"], tie["rank_b"]), (2, 3))
        self.assertTrue(tie["both_top_n"])
        self.assertEqual(tie["top_n"], 5)

    def test_one_typo_fix_commit_is_a_tie_but_not_top_n(self):
        tie = C.contribution_overlap("owner/repo", self.contribs, "topmaintainer", "typofixer")
        self.assertIsNotNone(tie)
        self.assertFalse(tie["both_top_n"])
        self.assertEqual(tie["min_contributions"], 1)

    def test_no_overlap_when_one_login_is_absent(self):
        self.assertIsNone(
            C.contribution_overlap("owner/repo", self.contribs, "dohernandez", "nobodyhere"))

    def test_repo_id_forms_produce_one_tie_basis(self):
        a = C.contribution_overlap("https://github.com/Owner/Repo.git", self.contribs,
                                   "dohernandez", "vbuterin")
        b = C.contribution_overlap("owner/repo", self.contribs, "dohernandez", "vbuterin")
        self.assertEqual(a["tie_basis"], b["tie_basis"])

    def test_same_login_twice_is_expected_error(self):
        with self.assertRaises(C.ExpectedError):
            C.contribution_overlap("owner/repo", self.contribs, "dohernandez", "DoHernandez")

    def test_org_membership_overlap(self):
        tie = C.org_membership_overlap("EthereumOrg", GITHUB_ORG_MEMBERS,
                                       "dohernandez", "topmaintainer")
        self.assertIsNotNone(tie)
        self.assertEqual(tie["tie_kind"], C.TIE_ORG_MEMBERSHIP)
        self.assertEqual(tie["tie_basis"], "github.com/ethereumorg")
        self.assertTrue(tie["public_only"])

    def test_org_membership_no_overlap(self):
        self.assertIsNone(
            C.org_membership_overlap("ethereumorg", GITHUB_ORG_MEMBERS, "dohernandez", "typofixer"))

    def test_empty_org_member_list_is_external(self):
        with self.assertRaises(C.ExternalError):
            C.org_membership_overlap("ethereumorg", [], "a", "b")

    def test_contributors_url_shape(self):
        self.assertEqual(C.build_github_contributors_url("Owner/Repo"),
                         "https://api.github.com/repos/owner/repo/contributors?per_page=100")

    def test_org_members_url_shape(self):
        self.assertEqual(C.build_github_org_members_url("EthereumOrg"),
                         "https://api.github.com/orgs/ethereumorg/members?per_page=100")


class TestGithubBatching(unittest.TestCase):
    """60 requests per hour per IP unauthenticated, so capture is batched and never looped."""

    def test_plan_deduplicates_repositories(self):
        plan = C.plan_github_batch(["Owner/Repo", "owner/repo/", "https://github.com/a/b"])
        self.assertEqual([repo for repo, _ in plan], ["a/b", "owner/repo"])

    def test_plan_refuses_to_exceed_the_budget(self):
        repos = ["owner/repo%d" % i for i in range(61)]
        with self.assertRaises(C.ExpectedError) as ctx:
            C.plan_github_batch(repos)
        self.assertEqual(ctx.exception.tag, C.TAG_EXPECTED)
        self.assertIn("60", ctx.exception.detail)

    def test_plan_accounts_for_budget_already_spent(self):
        repos = ["owner/repo%d" % i for i in range(5)]
        self.assertEqual(len(C.plan_github_batch(repos, budget=60, spent=55)), 5)
        with self.assertRaises(C.ExpectedError):
            C.plan_github_batch(repos, budget=60, spent=56)

    def test_batch_makes_exactly_one_request_per_distinct_repo(self):
        fake = FakeFetch([("/contributors", ok(GITHUB_CONTRIBUTORS))])
        out = C.fetch_github_contributors_batch(fake, ["a/b", "a/b", "c/d"])
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(out["requests_spent"], 2)
        self.assertEqual(sorted(out["cache"].keys()), ["a/b", "c/d"])
        self.assertEqual(out["failed"], {})

    def test_batch_records_a_403_per_repo_and_keeps_the_rest(self):
        fake = FakeFetch(
            [("repos/rate/limited/contributors",
              err(403, {"x-ratelimit-remaining": "0", "x-ratelimit-limit": "60"})),
             ("/contributors", ok(GITHUB_CONTRIBUTORS))])
        out = C.fetch_github_contributors_batch(fake, ["a/b", "rate/limited"])
        self.assertIn("a/b", out["cache"])
        self.assertEqual(out["failed"]["rate/limited"]["tag"], C.TAG_EXTERNAL)
        self.assertNotIn("rate/limited", out["cache"])

    def test_batch_aborts_after_a_transport_failure(self):
        fake = FakeFetch([("aaa/aaa", err(503)), ("/contributors", ok(GITHUB_CONTRIBUTORS))])
        out = C.fetch_github_contributors_batch(fake, ["aaa/aaa", "zzz/zzz"])
        self.assertEqual(out["failed"]["aaa/aaa"]["tag"], C.TAG_TRANSIENT)
        self.assertEqual(out["failed"]["zzz/zzz"]["tag"], C.TAG_TRANSIENT)
        self.assertEqual(out["cache"], {})
        self.assertEqual(len(fake.calls), 1)

    def test_cache_shape_is_storable(self):
        fake = FakeFetch([("/contributors", ok(GITHUB_CONTRIBUTORS))])
        out = C.fetch_github_contributors_batch(fake, ["a/b"])
        self.assertEqual(json.loads(json.dumps(out["cache"]))["a/b"]["dohernandez"], 412)


class TestSourceLedger(unittest.TestCase):

    def test_checked_and_failed_are_recorded_facts(self):
        led = C.new_ledger()
        C.record_checked(led, C.SOURCE_OPENALEX)
        C.record_failed(led, C.SOURCE_GITHUB, C.ExternalError("rate limited", source="github"))
        checked, failed = C.ledger_summary(led)
        self.assertEqual(checked, "openalex")
        self.assertEqual(failed, "github:[EXTERNAL]")

    def test_a_failed_source_cannot_also_count_as_checked(self):
        led = C.new_ledger()
        C.record_checked(led, C.SOURCE_GITHUB)
        C.record_failed(led, C.SOURCE_GITHUB, C.ExternalError("403", source="github"))
        self.assertEqual(led["checked"], [])

    def test_unknown_source_rejected(self):
        with self.assertRaises(C.ExpectedError):
            C.record_checked(C.new_ledger(), "scopus")

    def test_failure_without_a_valid_tag_rejected(self):
        with self.assertRaises(C.ExpectedError):
            C.record_failed(C.new_ledger(), C.SOURCE_GITHUB, {"tag": "[OOPS]"})

    def test_the_reason_a_source_failed_reaches_the_rendered_line(self):
        """`failed=orcid:[EXTERNAL]` is not actionable; the detail behind it is.

        A rate limit means wait, a mistyped iD means correct the registration, and an unplaceable
        employment date means appeal with better evidence. All three render as the same tag, so the
        tag alone cannot tell a reviewer which of the three they are looking at.
        """
        led = C.record_checked(C.new_ledger(), C.SOURCE_OPENALEX)
        C.record_failed(led, C.SOURCE_ORCID, C.ExternalError(
            "0000-0002-1825-0097: 2 employment row(s) could not be placed in time",
            source="orcid"))
        result = C.screen_verdict(led)
        self.assertEqual(result["verdict"], C.VERDICT_INSUFFICIENT)
        self.assertEqual(result["sources_failed"], "orcid:[EXTERNAL]")
        line = C.render_verdict_line(result)
        self.assertIn("failed=orcid:[EXTERNAL]", line)
        self.assertIn("why: orcid: 0000-0002-1825-0097: 2 employment row(s)", line)

    def test_details_are_sorted_by_source_so_validators_agree(self):
        led = C.new_ledger()
        C.record_failed(led, C.SOURCE_ORCID, C.ExternalError("orcid said no", source="orcid"))
        C.record_failed(led, C.SOURCE_GITHUB, C.ExternalError("github said no", source="github"))
        C.record_checked(led, C.SOURCE_OPENALEX)
        self.assertEqual(C.ledger_details(led),
                         "github: github said no; orcid: orcid said no")

    def test_a_long_detail_is_capped_so_the_head_of_the_rationale_survives(self):
        led = C.new_ledger()
        C.record_failed(led, C.SOURCE_GITHUB, C.ExternalError("x" * 400, source="github"))
        rendered = C.ledger_details(led)
        self.assertTrue(rendered.endswith("..."))
        self.assertEqual(len(rendered), len("github: ") + C.LEDGER_DETAIL_CAP)

    def test_a_result_assembled_without_the_detail_field_still_renders(self):
        """The field is newer than the function that reads it, so the read is by `.get`."""
        line = C.render_verdict_line({
            "verdict": C.VERDICT_INSUFFICIENT, "tie_kind": C.TIE_NONE, "tie_basis": "",
            "sources_checked": "openalex", "sources_failed": "github:[EXTERNAL]",
        })
        self.assertIn("failed=github:[EXTERNAL]", line)
        self.assertNotIn("why:", line)


class TestModelOutputIsClassificationOnly(unittest.TestCase):
    """The model is asked what the evidence says, never what the contract should do."""

    RECORDS = ("https://openalex.org/W2741809807", "owner/repo")

    def test_identity_label_accepted(self):
        out = C.classify_identity_link(
            {"label": "SAME_PERSON", "basis": "owner/repo"}, self.RECORDS)
        self.assertEqual(out["label"], "SAME_PERSON")

    def test_unresolved_is_an_allowed_answer(self):
        self.assertEqual(C.classify_identity_link("UNRESOLVED", self.RECORDS)["label"],
                         "UNRESOLVED")

    def test_identity_basis_must_be_in_the_fetched_records(self):
        with self.assertRaises(C.LlmError) as ctx:
            C.classify_identity_link({"label": "SAME_PERSON", "basis": "invented/repo"},
                                     self.RECORDS)
        self.assertEqual(ctx.exception.tag, C.TAG_LLM_ERROR)

    def test_same_person_without_a_basis_is_llm_error(self):
        with self.assertRaises(C.LlmError):
            C.classify_identity_link({"label": "SAME_PERSON"}, self.RECORDS)

    def test_materiality_labels(self):
        for label in ("MATERIAL", "UNCLEAR"):
            out = C.classify_materiality({"label": label, "tie_basis": "owner/repo"}, self.RECORDS)
            self.assertEqual(out["label"], label)
        self.assertEqual(C.classify_materiality("NOT_MATERIAL", self.RECORDS)["label"],
                         "NOT_MATERIAL")

    def test_invented_tie_basis_is_llm_error(self):
        with self.assertRaises(C.LlmError) as ctx:
            C.classify_materiality({"label": "MATERIAL", "tie_basis": "https://openalex.org/W999"},
                                   self.RECORDS)
        self.assertEqual(ctx.exception.tag, C.TAG_LLM_ERROR)

    def test_free_text_label_is_llm_error(self):
        for junk in ("this reviewer should be excluded", "yes", "", 42, None, ["MATERIAL"]):
            with self.assertRaises(C.LlmError, msg=repr(junk)):
                C.classify_materiality(junk, self.RECORDS)

    def test_malformed_dict_is_llm_error(self):
        with self.assertRaises(C.LlmError):
            C.classify_materiality({"verdict": "CONFLICT"}, self.RECORDS)

    def test_verify_tie_basis_rejects_an_absent_record(self):
        self.assertTrue(C.verify_tie_basis("owner/repo", self.RECORDS))
        with self.assertRaises(C.LlmError):
            C.verify_tie_basis("owner/other", self.RECORDS)


class TestVerdictAssembly(unittest.TestCase):

    WINDOW = C.coi_window_from_years(2020, 2026)

    def _all_checked(self):
        led = C.new_ledger()
        for src in C.ALL_SOURCES:
            C.record_checked(led, src)
        return led

    def test_no_tie_and_all_sources_answered_is_clear(self):
        result = C.screen_verdict(self._all_checked())
        self.assertEqual(result["verdict"], C.VERDICT_CLEAR)
        self.assertEqual(result["weight_bp"], C.WEIGHT_FULL)
        self.assertEqual(result["tie_kind"], C.TIE_NONE)

    def test_clear_always_carries_its_qualifier(self):
        line = C.render_verdict_line(C.screen_verdict(self._all_checked()))
        self.assertIn("does not mean no conflict exists", line)

    def test_unscreened_is_not_clear(self):
        result = C.screen_verdict(self._all_checked(), declared_any_handle=False)
        self.assertEqual(result["verdict"], C.VERDICT_UNSCREENED)
        self.assertNotEqual(result["verdict"], C.VERDICT_CLEAR)
        self.assertEqual(result["weight_bp"], C.WEIGHT_FULL)
        self.assertTrue(result["flagged"])

    def test_material_label_yields_conflict_and_zero_weight(self):
        graph = C.extract_coauthorship(OPENALEX_WORKS_REVIEWER, AID_REVIEWER)
        ties = C.coauthorship_overlap(graph, AID_APPLICANT, window=self.WINDOW)
        recent = [t for t in ties if t["year"] == 2024]
        result = C.screen_verdict(self._all_checked(), coauthor_ties=recent,
                                  materiality_label="MATERIAL")
        self.assertEqual(result["verdict"], C.VERDICT_CONFLICT)
        self.assertEqual(result["weight_bp"], C.WEIGHT_ZERO)
        self.assertEqual(result["tie_kind"], C.TIE_COAUTHOR)
        self.assertEqual(result["tie_basis"], "https://openalex.org/W2741809807")

    def test_unclear_label_reduces_rather_than_zeroes(self):
        graph = C.extract_coauthorship(OPENALEX_WORKS_REVIEWER, AID_REVIEWER)
        ties = C.coauthorship_overlap(graph, AID_APPLICANT)
        big = [t for t in ties if t["author_count"] == 40]
        result = C.screen_verdict(self._all_checked(), coauthor_ties=big,
                                  materiality_label="UNCLEAR")
        self.assertEqual(result["verdict"], C.VERDICT_MATERIAL_UNCLEAR)
        self.assertEqual(result["weight_bp"], C.WEIGHT_PARTIAL)

    def test_not_material_never_becomes_conflict(self):
        tie = C.contribution_overlap(
            "owner/repo", C.extract_contributors(GITHUB_CONTRIBUTORS), "topmaintainer",
            "typofixer")
        result = C.screen_verdict(self._all_checked(), contribution_ties=[tie],
                                  materiality_label="NOT_MATERIAL")
        self.assertNotEqual(result["verdict"], C.VERDICT_CONFLICT)
        self.assertIn(result["verdict"], (C.VERDICT_MATERIAL_UNCLEAR, C.VERDICT_CLEAR))

    def test_tie_with_no_band_does_not_silently_pass(self):
        tie = C.contribution_overlap(
            "owner/repo", C.extract_contributors(GITHUB_CONTRIBUTORS), "dohernandez", "vbuterin")
        result = C.screen_verdict(self._all_checked(), contribution_ties=[tie])
        self.assertNotEqual(result["verdict"], C.VERDICT_CLEAR)
        self.assertEqual(result["weight_bp"], C.WEIGHT_PARTIAL)

    def test_garbage_materiality_label_is_llm_error(self):
        tie = C.contribution_overlap(
            "owner/repo", C.extract_contributors(GITHUB_CONTRIBUTORS), "dohernandez", "vbuterin")
        with self.assertRaises(C.LlmError):
            C.screen_verdict(self._all_checked(), contribution_ties=[tie],
                             materiality_label="DEFINITELY_EXCLUDE_THEM")

    def test_no_source_answered_is_insufficient(self):
        led = C.new_ledger()
        for src in C.ALL_SOURCES:
            C.record_failed(led, src, C.ExternalError("unreachable", source=src))
        result = C.screen_verdict(led)
        self.assertEqual(result["verdict"], C.VERDICT_INSUFFICIENT)
        self.assertIsNone(result["weight_bp"])
        self.assertFalse(result["weight_changed"])

    def test_strongest_tie_kind_is_named_first(self):
        graph = C.extract_coauthorship(OPENALEX_WORKS_REVIEWER, AID_REVIEWER)
        coauthor = C.coauthorship_overlap(graph, AID_APPLICANT)[:1]
        contrib = [C.contribution_overlap("owner/repo",
                                          C.extract_contributors(GITHUB_CONTRIBUTORS),
                                          "dohernandez", "vbuterin")]
        result = C.screen_verdict(self._all_checked(), coauthor_ties=coauthor,
                                  contribution_ties=contrib, materiality_label="MATERIAL")
        self.assertEqual(result["tie_kind"], C.TIE_COAUTHOR)


class TestCentralRisk(unittest.TestCase):
    """THE test. A source returning 403 must never produce a clean verdict.

    The whole product gates voting weight on the absence of a conflict, so a rate-limited source
    that reads as clean is the single failure that would discredit it. Every assertion here is on
    the classification and the verdict string, never on a truthy return.
    """

    def test_403_screening_is_insufficient_not_clear(self):
        fake = FakeFetch([("/contributors",
                           err(403, {"x-ratelimit-remaining": "0", "x-ratelimit-limit": "60"},
                               payload={"message": "API rate limit exceeded"}))])
        ledger = C.new_ledger()

        # OpenAlex answers and finds nothing between these two authors.
        graph = C.extract_coauthorship(OPENALEX_WORKS_STRANGER, AID_STRANGER)
        C.record_checked(ledger, C.SOURCE_OPENALEX)
        coauthor_ties = C.coauthorship_overlap(graph, AID_APPLICANT)
        self.assertEqual(coauthor_ties, [], "precondition: OpenAlex finds no tie")

        # GitHub is rate limited.
        batch = C.fetch_github_contributors_batch(fake, ["owner/repo"])
        self.assertEqual(batch["cache"], {})
        failure = batch["failed"]["owner/repo"]
        self.assertEqual(failure["tag"], C.TAG_EXTERNAL)
        C.record_failed(ledger, C.SOURCE_GITHUB, failure)

        result = C.screen_verdict(ledger, coauthor_ties=coauthor_ties)

        self.assertNotEqual(result["verdict"], C.VERDICT_CLEAR)
        self.assertEqual(result["verdict"], C.VERDICT_INSUFFICIENT)
        self.assertIsNone(result["weight_bp"])
        self.assertIs(result["weight_changed"], False)
        self.assertIs(result["retryable"], True)
        self.assertEqual(result["sources_failed"], "github:[EXTERNAL]")
        self.assertEqual(result["tie_kind"], C.TIE_NONE)

        line = C.render_verdict_line(result)
        self.assertIn("INSUFFICIENT", line)
        self.assertNotIn(C.VERDICT_CLEAR, line)
        self.assertNotIn("does not mean no conflict exists", line)

    def test_429_screening_is_also_insufficient(self):
        fake = FakeFetch([("/contributors", err(429, {"x-ratelimit-remaining": "0"}))])
        batch = C.fetch_github_contributors_batch(fake, ["owner/repo"])
        self.assertEqual(batch["failed"]["owner/repo"]["tag"], C.TAG_EXTERNAL)
        ledger = C.record_checked(C.new_ledger(), C.SOURCE_OPENALEX)
        C.record_failed(ledger, C.SOURCE_GITHUB, batch["failed"]["owner/repo"])
        result = C.screen_verdict(ledger)
        self.assertEqual(result["verdict"], C.VERDICT_INSUFFICIENT)
        self.assertNotEqual(result["verdict"], C.VERDICT_CLEAR)

    def test_403_and_429_reach_the_identical_verdict(self):
        verdicts = []
        for status in (403, 429):
            fake = FakeFetch([("/contributors", err(status, {"x-ratelimit-remaining": "0"}))])
            batch = C.fetch_github_contributors_batch(fake, ["owner/repo"])
            ledger = C.record_checked(C.new_ledger(), C.SOURCE_ORCID)
            C.record_failed(ledger, C.SOURCE_GITHUB, batch["failed"]["owner/repo"])
            verdicts.append(C.screen_verdict(ledger)["verdict"])
        self.assertEqual(verdicts, [C.VERDICT_INSUFFICIENT, C.VERDICT_INSUFFICIENT])

    def test_orcid_xml_two_hundred_does_not_read_as_clean(self):
        # The nastiest case in the manifest: HTTP 200 plus 44 KB of unparseable XML.
        fake = FakeFetch([("pub.orcid.org", {"status": 200, "headers": {}, "json": None,
                                             "text": "<?xml version='1.0'?><record/>"})])
        ledger = C.record_checked(C.new_ledger(), C.SOURCE_OPENALEX)
        try:
            C.fetch_orcid_record(fake, ORCID_REVIEWER)
            self.fail("a 200 with an XML body must not be treated as a usable record")
        except C.QuorumError as exc:
            self.assertEqual(exc.tag, C.TAG_EXTERNAL)
            C.record_failed(ledger, C.SOURCE_ORCID, exc)
        result = C.screen_verdict(ledger)
        self.assertEqual(result["verdict"], C.VERDICT_INSUFFICIENT)

    def test_empty_openalex_results_do_not_read_as_clean(self):
        ledger = C.new_ledger()
        try:
            C.extract_coauthorship(OPENALEX_EMPTY, AID_REVIEWER)
            self.fail("an empty results array must not be treated as no co-authors")
        except C.QuorumError as exc:
            self.assertEqual(exc.tag, C.TAG_EXTERNAL)
            C.record_failed(ledger, C.SOURCE_OPENALEX, exc)
        self.assertEqual(C.screen_verdict(ledger)["verdict"], C.VERDICT_INSUFFICIENT)

    def test_every_absence_path_classifies_as_external(self):
        cases = {
            "empty openalex results": lambda: C.extract_coauthorship(OPENALEX_EMPTY, AID_REVIEWER),
            "openalex author no match": lambda: C.parse_openalex_authors(OPENALEX_EMPTY),
            "empty github contributors": lambda: C.extract_contributors([], "o/r"),
            "empty github org members": lambda: C.org_membership_overlap("o", [], "a", "b"),
            "orcid 404": lambda: C.classify_status(404, source="orcid"),
            "github 403": lambda: C.classify_status(403, {"x-ratelimit-remaining": "0"},
                                                    source="github"),
            "github 429": lambda: C.classify_status(429, source="github"),
            "orcid missing employments": lambda: C.extract_employments(
                {"activities-summary": {}}),
        }
        for name, fn in cases.items():
            with self.subTest(case=name):
                try:
                    fn()
                    self.fail(name + " returned instead of raising")
                except C.QuorumError as exc:
                    self.assertEqual(exc.tag, C.TAG_EXTERNAL, name)


if __name__ == "__main__":
    # verbosity=1 keeps the standard compact report. Use -v for the per-test listing.
    unittest.main(verbosity=1)
