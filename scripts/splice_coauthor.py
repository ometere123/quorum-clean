#!/usr/bin/env python3
"""Splice the overlap-detection core into the Quorum Clean contract, and prove the copy behaves.

A GenLayer Intelligent Contract is a single module and cannot import a sibling Python file. So
`_build/quorum-coauthor/coauthor.py` is written and unit-tested standalone, then copied verbatim
into `quorum-clean/contracts/QuorumClean.py` between two markers. Copying code is how copies
drift, and the copy is the one that decides whether a reviewer's vote counts, so the copy is what
this script checks.

    python quorum-clean/scripts/splice_coauthor.py --write     # splice, then verify
    python quorum-clean/scripts/splice_coauthor.py             # verify only, exit 1 on drift

WHY THIS IS NOT A COPY OF conveyance/scripts/splice_rdap.py. Six things differ, and each is a
place where copying the earlier script would have produced a check that passes without checking.

1. THE SUITE IS CLASS-BASED. `test_rdap.py` is bare module-level functions, so that script could
   call each one and count. `test_coauthor.py` is 176 tests across 20 `TestCase` classes with
   `setUpClass` fixtures, so this one loads them with `unittest.TestLoader` and reads a result
   object. Iterating `vars(suite)` here would have found the classes, called none of the tests,
   and reported a clean run over zero assertions.

2. THE REGION IMPORTS NOTHING. `rdap.py` begins at `import hashlib` and its digest starts there.
   `coauthor.py` has zero imports by design, and its own suite asserts that, so this script
   asserts the region imports nothing and that the contract's head supplies all four of
   `dataclasses`, `genlayer`, `hashlib` and `json`. An import appearing in the region would mean
   the standalone module had grown a dependency the contract cannot satisfy.

3. THE RAW-DIGEST SCAN COVERS THE CONTRACT, NOT THE REGION. The region takes no digests at all;
   `_sha256_hex` lives in the contract head and is called once, from `screen`. Pointing the
   earlier version of this check at the region would have scanned a file with zero digest calls
   and passed vacuously. So it scans the contract's own head and tail, where the calls are.

4. THE TAXONOMY BASE CLASS IS `QuorumError`, NOT `Refusal`, AND THE MARSHALLING IS DIFFERENT.
   Conveyance returned `{"error": ...}` dicts out of its blocks. This contract returns a fixed
   five-key observation whichever way the source went, so "did this handler absorb the failure"
   cannot be answered by looking for an `"error"` key. It is answered by requiring the handler to
   raise, to name its bound exception, or to call `record_failed`.

5. GATE 2 IS CHECKED BEHAVIOURALLY AND EXHAUSTIVELY. The central rule of this product is that
   CLEAR requires every needed source to have returned usable data. The suite tests that rule at
   named points; this script enumerates all 96 combinations of ledger state and tie presence and
   asserts no CLEAR survives a failed source, and separately that CONFLICT and MATERIAL_UNCLEAR
   still do. A gate that blocked the positive verdicts too would be safe and useless, so both
   halves are asserted.

6. TWO CHECKS EXIST BECAUSE THIS CONTRACT DECIDES A WEIGHT. `screen` must never name a verdict
   constant on the right of an assignment, so the verdict can only come from the tested module.
   And in `adjudicate_appeal`, every branch that reaches CLEAR must sit below the test on
   `sources_failed`, so no appeal can clear a pair over a source that never answered.

Four of the 176 standalone tests read `coauthor.py` from disk by absolute path, so re-running them
against the spliced copy passes without looking at it. That is a limit of those tests, not a
failure of them, and closing it is what the structural layer is for. All four are named in the
report.
"""

import ast
import io
import json
import os
import sys
import hashlib
import traceback
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
REPO = os.path.dirname(PROJECT)

SOURCE = os.path.join(REPO, "_build", "quorum-coauthor", "coauthor.py")
SUITE_DIR = os.path.join(REPO, "_build", "quorum-coauthor")
CONTRACT = os.path.join(PROJECT, "contracts", "QuorumClean.py")

BEGIN = "# --- QUORUM-COAUTHOR SPLICE BEGIN ---"
END = "# --- QUORUM-COAUTHOR SPLICE END ---"

#: The module the suite imports, and the suite itself.
MODULE_NAME = "coauthor"
SUITE_NAME = "test_coauthor"

#: Exactly what the region may import: nothing. `coauthor.py` is import-free on purpose and its
#: own `test_module_has_zero_imports` says so about the file on disk. This says it about the copy.
REGION_IMPORTS = ()

#: Exactly what the contract's own head and tail may import. All four, because the region supplies
#: none of them.
CONTRACT_IMPORTS = ("dataclasses", "genlayer", "hashlib", "json")

BANNED_CALLS = {"open", "input", "eval", "exec", "compile", "__import__", "globals",
                "locals", "print"}
BANNED_ATTRS = {"urlopen", "socket", "system", "popen", "getenv", "environ", "time",
                "now", "utcnow", "monotonic", "random", "urandom", "read_bytes",
                "read_text", "write_bytes"}
BANNED_TOUCHES = ("environ", "argv", "stdin", "stdout", "stderr")

#: The four module-level mutable containers in the region, with why each is safe. A blanket
#: "tuple or frozenset" rule would fail all four, and a bare exemption would be a way of not
#: checking, so each is named with its reason, the mutator scan below covers static mutation, and
#: the behavioural layer observes them unchanged across the whole suite.
MUTABLE_EXEMPT = {
    "_ASCII_FOLD": "read only by `.get`, one character at a time, inside `fold_ascii`",
    "_INSTITUTION_ABBREV": "read only by key while normalizing an institution name",
    "ORCID_HEADERS": "always `dict(ORCID_HEADERS)`-copied before it reaches fetch, which is the "
                     "pattern that makes a module-level dict safe to share",
    "GITHUB_HEADERS": "always `dict(GITHUB_HEADERS)`-copied before it reaches fetch, same pattern",
}

#: Names that must never be the argument to a digest call. ORCID content-negotiates the same
#: person into a 22,492 byte JSON record or a 44,000 byte XML one, and OpenAlex reorders
#: authorship arrays between reads, so a digest of a body is a digest of formatting and would make
#: agreement impossible rather than unlikely.
UNHASHABLE_NAMES = ("raw", "body", "payload", "response", "text", "excerpt")
DIGEST_CALLS = ("_sha256_hex", "sha256_hex")

#: The base of the four-tag taxonomy, and the ledger call that records a source as unreachable.
TAXONOMY_BASE = "QuorumError"
RECORD_FAILED = "record_failed"

#: The four standalone tests that read coauthor.py from disk by absolute path.
VACUOUS_AGAINST_SPLICE = (
    "test_module_has_zero_imports",
    "test_markers_bracket_the_whole_module_body",
    "test_every_public_callable_is_inside_the_region",
    "test_splice_region_digest_is_reproducible",
)


def read(path):
    return io.open(path, encoding="utf-8", newline="").read()


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_region(text, label):
    """The text between the two markers, normalized exactly as the standalone suite does.

    These four lines are copied out of `splice_region` in `test_coauthor.py` rather than
    reimplemented, because the whole point of anchoring on the source's own markers is that the
    digest the suite prints and the digest this script asserts are one number. A normalization
    that differed by a trailing newline would make them two.
    """
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("%s must carry each marker exactly once; found %d BEGIN and %d END"
                         % (label, text.count(BEGIN), text.count(END)))
    start = text.index(BEGIN) + len(BEGIN)
    stop = text.index(END)
    if stop < start:
        raise SystemExit("%s has the END marker before the BEGIN marker" % label)
    region = text[start:stop]
    return "\n".join(region.replace("\r\n", "\n").split("\n")).strip() + "\n"


def marker_lines(text):
    """(line of BEGIN, line of END), 1-based, for attributing an AST node to a side."""
    return (text[:text.index(BEGIN)].count("\n") + 1,
            text[:text.index(END)].count("\n") + 1)


def split_contract(text):
    """The contract as (head, tail), where head ends with the BEGIN line and tail starts at END."""
    begin = text.index(BEGIN)
    head_end = text.index("\n", begin) + 1
    end = text.index(END)
    tail_start = text.rindex("\n", 0, end) + 1
    return text[:head_end], text[tail_start:]


def write_splice():
    region = extract_region(read(SOURCE), os.path.relpath(SOURCE, REPO))
    text = read(CONTRACT)
    current = extract_region(text, os.path.relpath(CONTRACT, REPO))
    if current == region:
        print("region already current; nothing rewritten")
        return
    head, tail = split_contract(text)
    io.open(CONTRACT, "w", encoding="utf-8", newline="\n").write(
        head + "\n" + region + "\n" + tail)
    print("spliced %d lines (%d bytes) of %s into %s"
          % (region.count("\n"), len(region.encode("utf-8")),
             os.path.basename(SOURCE), os.path.relpath(CONTRACT, REPO)))


# ----------------------------------------------------------------------------------
# Layer 1: textual
# ----------------------------------------------------------------------------------

def check_textual(region, current):
    want, got = sha256(region), sha256(current)
    if want != got:
        print("  FAIL region differs from source")
        print("       source  sha256 %s (%d lines, %d bytes)"
              % (want, region.count("\n"), len(region.encode("utf-8"))))
        print("       spliced sha256 %s (%d lines, %d bytes)"
              % (got, current.count("\n"), len(current.encode("utf-8"))))
        want_lines, got_lines = region.splitlines(), current.splitlines()
        for i in range(min(len(want_lines), len(got_lines))):
            if want_lines[i] != got_lines[i]:
                print("       first difference at region line %d:" % (i + 1))
                print("         source:  %r" % want_lines[i][:120])
                print("         spliced: %r" % got_lines[i][:120])
                break
        else:
            print("       identical for %d lines, then the lengths diverge (%d vs %d)"
                  % (min(len(want_lines), len(got_lines)), len(want_lines), len(got_lines)))
        return False
    print("  pass region is byte-identical to source, sha256 %s, %d lines, %d bytes"
          % (want, region.count("\n"), len(region.encode("utf-8"))))
    return True


# ----------------------------------------------------------------------------------
# Layer 2: structural, against the spliced region rather than against coauthor.py
# ----------------------------------------------------------------------------------

def _imports_of(tree, keep):
    """Top-level module names imported by nodes `keep(node)` accepts."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and keep(node):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and keep(node):
            if node.level:
                found.add("<relative>")
            found.add((node.module or "").split(".")[0])
    return found


def check_region_imports(region_tree):
    got = _imports_of(region_tree, lambda node: True)
    want = set(REGION_IMPORTS)
    if got != want:
        print("  FAIL the region imports %s; it must import nothing at all. An import here means "
              "the standalone module grew a dependency, and the contract has no way to satisfy "
              "one that GenVM does not already provide."
              % (", ".join(sorted(got)) or "nothing"))
        return False
    print("  pass the region imports nothing, so the spliced copy cannot depend on a module that "
          "is unavailable inside a contract")
    return True


def check_contract_imports(contract_tree, begin_line, end_line):
    got = _imports_of(contract_tree,
                      lambda node: not (begin_line < node.lineno < end_line))
    want = set(CONTRACT_IMPORTS)
    if got != want:
        print("  FAIL the contract's own head and tail import %s; expected exactly %s"
              % (", ".join(sorted(got)) or "nothing", ", ".join(sorted(want))))
        return False
    print("  pass the contract's own head and tail import exactly %s, which is all four that the "
          "import-free region needs supplied for it" % ", ".join(sorted(want)))
    return True


def check_no_status_code(region_tree, contract_tree, skip=None):
    """`.status_code` does not exist on a GenVM web response. It is `.status`.

    The published SDK example reads `.status_code`, and following it produces an `AttributeError`
    inside a consensus block, after the round has been paid for. One check, against a mistake that
    was actually made in this project once.

    Deliberately an attribute scan rather than a substring scan. Both files name the hazard in
    prose so a future reader meets the explanation at the moment it matters, and flagging that
    text would punish documenting the bug. `getattr(x, "status_code")` is covered too, because it
    is the one spelling an attribute scan alone would miss.
    """
    bad = []
    for label, tree, filt in (("the region", region_tree, None),
                              ("the contract", contract_tree, skip)):
        for node in ast.walk(tree):
            if filt is not None and filt(node):
                continue
            if isinstance(node, ast.Attribute) and node.attr == "status_code":
                bad.append((label, node.lineno, "reads .status_code"))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "getattr" and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == "status_code"):
                bad.append((label, node.lineno, 'calls getattr(..., "status_code")'))
    if bad:
        for label, lineno, what in bad:
            print("  FAIL %s %s at line %d. A GenVM web response exposes .status; the published "
                  "example is wrong about this." % (label, what, lineno))
        return False
    print("  pass neither the region nor the contract reads .status_code, by attribute or by "
          "getattr; both only name it in prose to warn about it")
    return True


def check_no_digest_over_a_raw_body(contract_tree, begin_line, end_line):
    """A digest may never be taken over a fetched body or a decoded body string.

    Pointed at the contract rather than the region, because the region takes no digests: the only
    digest in this build is `_sha256_hex`, defined in the contract head and called once, on the
    output of `_canonical_evidence`. Scanning the region would have been a check over zero call
    sites.

    Measured: ORCID serves one person as 22,492 bytes of JSON with an Accept header and 44,000
    bytes of XML without it, both HTTP 200. OpenAlex returns authorship arrays in a different
    order between reads of the same work. Hashing either body would make validators disagree about
    identical evidence, so the digest is taken over parsed facts and this check is what keeps it
    that way.
    """
    bad = []
    for node in ast.walk(contract_tree):
        if begin_line < getattr(node, "lineno", 0) < end_line:
            continue
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in DIGEST_CALLS):
            continue
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            for inner in ast.walk(arg):
                name = None
                if isinstance(inner, ast.Name):
                    name = inner.id
                elif isinstance(inner, ast.Attribute):
                    name = inner.attr
                elif isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                    continue
                if name and name.lower() in UNHASHABLE_NAMES:
                    bad.append((node.lineno, node.func.id, name))
    if bad:
        for lineno, call, name in bad:
            print("  FAIL contract line %d takes %s(...) over %r, which is a fetched or decoded "
                  "response value. One source formats the same record two ways at 200, so a "
                  "digest of a body is a digest of formatting." % (lineno, call, name))
        return False
    calls = [n.lineno for n in ast.walk(contract_tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id in DIGEST_CALLS
             and not (begin_line < n.lineno < end_line)]
    if not calls:
        print("  FAIL the contract takes no digest at all, so this check measured nothing. "
              "`evidence_digest` has to be computed somewhere.")
        return False
    print("  pass the contract's %d digest call site(s) at line(s) %s never reach a fetched or "
          "decoded body (%s)"
          % (len(calls), ", ".join(str(n) for n in calls), "/".join(UNHASHABLE_NAMES)))
    return True


def _handler_kinds(handler):
    if isinstance(handler.type, ast.Name):
        return [handler.type.id]
    if isinstance(handler.type, ast.Tuple):
        return [e.id for e in handler.type.elts if isinstance(e, ast.Name)]
    if handler.type is None:
        return ["<bare>"]
    return []


def check_broad_handlers_are_last(tree, label):
    """A broad `except Exception` must never sit above `except QuorumError` in the same try.

    Python matches handlers in order, so `except Exception` first would catch every tagged
    `QuorumError` and re-tag it. A refusal that arrives as `[EXPECTED]` and leaves as
    `[TRANSIENT]` tells a caller to retry something that will never succeed, which is worse than
    either tag on its own.
    """
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        names = [(h.lineno, _handler_kinds(h)) for h in node.handlers]
        broad_at = [ln for ln, kinds in names
                    if "Exception" in kinds or "BaseException" in kinds or "<bare>" in kinds]
        tagged_at = [ln for ln, kinds in names if TAXONOMY_BASE in kinds
                     or any(k.endswith("Error") and k != "Exception" for k in kinds)]
        if broad_at and tagged_at and min(broad_at) < min(tagged_at):
            bad.append((min(broad_at), min(tagged_at)))
    if bad:
        for broad, tagged in bad:
            print("  FAIL %s has a broad handler at line %d above a tagged handler at line %d, so "
                  "every tagged refusal in that try would be caught and re-tagged"
                  % (label, broad, tagged))
        return False
    print("  pass no broad handler in %s precedes a tagged handler in the same try, so no tag can "
          "be flattened on the way out" % label)
    return True


def check_contract_never_swallows_a_refusal(contract_tree, begin_line, end_line):
    """Every `except QuorumError` in the contract must raise, name the exception, or record it.

    This is the "absence is never success" rule as a static check. `except QuorumError: pass`
    would turn an unreachable source into a clean verdict, which is the exact failure this whole
    product is built to avoid, and it is two characters away from correct code.

    The test is not "returns an error dict", the way it was for Conveyance. Every block here
    returns the same five keys whichever way the source went, so a returned dict proves nothing.
    What proves something is that the handler used the exception it caught: re-raised it, named it
    in what it returned or appended, or passed it to `record_failed`.
    """
    bad = []
    checked = 0
    for node in ast.walk(contract_tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if begin_line < node.lineno < end_line:
            continue
        if TAXONOMY_BASE not in _handler_kinds(node):
            continue
        checked += 1
        raises = any(isinstance(n, ast.Raise) for n in ast.walk(node))
        bound = node.name
        uses_bound = bound is not None and any(
            isinstance(n, ast.Name) and n.id == bound for n in ast.walk(node))
        records = any(isinstance(n, ast.Call)
                      and ((isinstance(n.func, ast.Name) and n.func.id == RECORD_FAILED)
                           or (isinstance(n.func, ast.Attribute) and n.func.attr == RECORD_FAILED))
                      for n in ast.walk(node))
        if not (raises or uses_bound or records):
            bad.append(node.lineno)
    if bad:
        for lineno in bad:
            print("  FAIL the `except %s` at contract line %d neither re-raises, names the "
                  "exception it caught, nor calls %s(), so a refused source would read as a "
                  "verdict" % (TAXONOMY_BASE, lineno, RECORD_FAILED))
        return False
    if checked == 0:
        print("  FAIL the contract catches %s nowhere, so this check measured nothing. The blocks "
              "have to absorb a source failure somewhere." % TAXONOMY_BASE)
        return False
    print("  pass all %d `except %s` handlers in the contract use the exception they caught, by "
          "re-raising it, naming it, or recording it as a failed source"
          % (checked, TAXONOMY_BASE))
    return True


def check_broad_handlers_are_annotated(contract_text, begin_line, end_line):
    """Every broad `except Exception` in the contract must carry a `# noqa: BLE001 - <reason>`.

    There are five, and they fall into two kinds. Three sit in argument validators and convert a
    malformed caller argument into a deterministic revert, re-raising rather than continuing. Two
    absorb a condition on purpose: a body that is not JSON, and a URL that does not resolve, are
    facts about the evidence rather than errors in this contract.

    A reason is required after the marker, not just the marker, because a bare `# noqa` is a way of
    silencing the check rather than answering it. This exists so a sixth broad handler cannot
    arrive by accident and quietly widen what gets swallowed.
    """
    lines = contract_text.replace("\r\n", "\n").split("\n")
    bad = []
    found = 0
    for i, line in enumerate(lines, start=1):
        if begin_line < i < end_line:
            continue
        stripped = line.strip()
        if not (stripped.startswith("except Exception") or stripped.startswith("except:")
                or stripped.startswith("except BaseException")):
            continue
        found += 1
        marker = "noqa: BLE001"
        if marker not in line:
            bad.append((i, "no `# %s` note" % marker, stripped[:60]))
        elif line.split(marker, 1)[1].strip(" -\t") == "":
            bad.append((i, "a bare `# %s` with no reason" % marker, stripped[:60]))
    if bad:
        for lineno, why, text in bad:
            print("  FAIL contract line %d has a broad handler with %s: %s" % (lineno, why, text))
        return False
    if found == 0:
        print("  FAIL the contract has no broad handler at all, so this check measured nothing")
        return False
    print("  pass all %d broad handlers in the contract carry a `# noqa: BLE001` note with a "
          "stated reason, so nothing is swallowed without saying why" % found)
    return True


def check_no_io(tree, label, skip=None):
    ok = True
    for node in ast.walk(tree):
        if skip is not None and skip(node):
            continue
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name) and target.id in BANNED_CALLS:
                print("  FAIL %s calls %s() at line %d" % (label, target.id, node.lineno))
                ok = False
            if isinstance(target, ast.Attribute) and target.attr in BANNED_ATTRS:
                print("  FAIL %s calls .%s() at line %d" % (label, target.attr, node.lineno))
                ok = False
        if isinstance(node, ast.Attribute) and node.attr in BANNED_TOUCHES:
            print("  FAIL %s touches %s at line %d" % (label, node.attr, node.lineno))
            ok = False
    if ok:
        print("  pass %s makes no filesystem, clock, randomness or stream call" % label)
    return ok


def check_module_state(region_tree):
    """Module-level containers, checked against a named exemption list rather than a blanket rule.

    Every module-level assignment must be an immutable literal, or one of the four names in
    MUTABLE_EXEMPT with the reason recorded there. A fifth name appearing as a `set(...)`,
    `dict(...)` or list literal is a failure, because the spliced copy is shared by every validator
    and a mutation would desynchronise them without any of them erring.
    """
    builders = ("set", "list", "dict", "bytearray")
    mutators = ("update", "setdefault", "popitem", "append", "extend", "add", "discard",
                "clear", "pop", "insert", "remove", "sort")
    ok = True
    module_names = set()
    flagged = set()

    for node in region_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        module_names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            mutable = isinstance(node.value, (ast.List, ast.Dict, ast.Set)) or (
                isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id in builders)
            if not mutable:
                continue
            flagged.add(target.id)
            if target.id not in MUTABLE_EXEMPT:
                print("  FAIL module-level mutable container %s at region line %d is not in the "
                      "exemption list. Make it a tuple or a frozenset, or add it with a reason."
                      % (target.id, node.lineno))
                ok = False

    stale = sorted(set(MUTABLE_EXEMPT) - flagged)
    if stale:
        print("  FAIL the exemption list names %s, which no longer exists as a module-level "
              "mutable container. A stale exemption is a check that stopped checking."
              % ", ".join(stale))
        ok = False

    for node in ast.walk(region_tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in mutators \
                and isinstance(node.func.value, ast.Name) \
                and node.func.value.id in module_names:
            print("  FAIL the region mutates module-level %s with .%s() at line %d"
                  % (node.func.value.id, node.func.attr, node.lineno))
            ok = False

    # Subscript and augmented assignment, checked separately from the method scan above because
    # `ORCID_HEADERS["Accept"] = ...` is a mutation that calls nothing. At module level it would
    # also escape the behavioural check, which snapshots the containers after the region has
    # already executed, so a mutation baked in at import time would appear in the baseline.
    for node in ast.walk(region_tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for target in targets:
            root = target
            while isinstance(root, (ast.Subscript, ast.Attribute)):
                root = root.value
            if target is root:
                continue
            if isinstance(root, ast.Name) and root.id in module_names:
                print("  FAIL the region writes into module-level %s by subscript or attribute at "
                      "line %d" % (root.id, node.lineno))
                ok = False

    if ok:
        print("  pass module-level state in the region is immutable except %d named containers, "
              "and none is mutated by method, subscript or augmented assignment:"
              % len(MUTABLE_EXEMPT))
        for name in sorted(MUTABLE_EXEMPT):
            print("       %-22s %s" % (name, MUTABLE_EXEMPT[name]))
    return ok


def _function_named(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def check_screen_never_names_a_verdict(contract_tree):
    """`screen` may compare against a verdict constant but may never assign one.

    The verdict has to come out of `screen_verdict`, which is the function 176 standalone tests
    are pointed at. If `screen` could write `sc.status = VERDICT_CLEAR` itself, the tested
    resolution order would become one implementation of the rule and the contract would become
    another, and the two would eventually disagree in the direction nobody checks.

    Comparisons are allowed and are the point of the distinction: `screen` legitimately asks
    whether a screening is already INSUFFICIENT before re-running it. Reading a constant is not
    deciding one.
    """
    fn = _function_named(contract_tree, "screen")
    if fn is None:
        print("  FAIL the contract has no `screen` function to check")
        return False
    bad = []
    for node in ast.walk(fn):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        for inner in ast.walk(value):
            if isinstance(inner, ast.Name) and inner.id.startswith("VERDICT_"):
                bad.append((node.lineno, inner.id))
    if bad:
        for lineno, name in bad:
            print("  FAIL `screen` assigns %s at contract line %d. The verdict must come from "
                  "screen_verdict(), which is what the standalone suite tests." % (name, lineno))
        return False
    compares = sorted(set(
        inner.id for node in ast.walk(fn) if isinstance(node, ast.Compare)
        for inner in ast.walk(node)
        if isinstance(inner, ast.Name) and inner.id.startswith("VERDICT_")))
    print("  pass `screen` names no verdict constant on the right of an assignment; it only "
          "compares against %s, so the verdict itself can only come from screen_verdict()"
          % (", ".join(compares) or "none"))
    return True


def check_appeal_cannot_clear_over_a_failed_source(contract_tree):
    """In `adjudicate_appeal`, every branch reaching CLEAR sits below the `sources_failed` test.

    The chain is a single linear if/elif, so a CLEAR assignment at a greater line number than the
    `sources_failed` comparison is a CLEAR that is only reachable when that comparison was false.
    That is the one rule spanning all four appeal grounds: overturning a finding removes a reason
    to distrust a pair, it does not read the source that never answered.

    What this proves is the ordering, not the semantics of the chain. It would not catch a rewrite
    into nested ifs where the ordering stopped implying the guard, which is why the chain is
    written flat and this docstring says so.
    """
    fn = _function_named(contract_tree, "adjudicate_appeal")
    if fn is None:
        print("  FAIL the contract has no `adjudicate_appeal` function to check")
        return False

    guard_lines = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        if isinstance(node.left, ast.Name) and node.left.id == "sources_failed":
            guard_lines.append(node.lineno)
    if not guard_lines:
        print("  FAIL `adjudicate_appeal` never compares `sources_failed`, so an appeal could "
              "clear a pair over a source that never answered")
        return False

    clear_lines = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) \
                and node.value.id == "VERDICT_CLEAR":
            clear_lines.append(node.lineno)
    if not clear_lines:
        print("  FAIL `adjudicate_appeal` never assigns VERDICT_CLEAR, so this check measured "
              "nothing. An overturned appeal has to be able to clear a fully covered pair.")
        return False

    guard = min(guard_lines)
    early = [ln for ln in clear_lines if ln < guard]
    if early:
        print("  FAIL `adjudicate_appeal` reaches VERDICT_CLEAR at line(s) %s, above the "
              "`sources_failed` test at line %d, so an appeal could clear a pair over a source "
              "that never answered" % (", ".join(str(n) for n in early), guard))
        return False

    nested = [n.lineno for n in ast.walk(fn)
              if isinstance(n, ast.If)
              for m in ast.walk(n)
              if isinstance(m, ast.If) and m is not n and m not in n.orelse]
    print("  pass all %d VERDICT_CLEAR assignments in `adjudicate_appeal` (line(s) %s) sit below "
          "the `sources_failed` test at line %d, in a flat if/elif chain%s"
          % (len(clear_lines), ", ".join(str(n) for n in clear_lines), guard,
             "" if not nested else " (note: %d nested if(s) present)" % len(nested)))
    return True


def region_callables(region_tree):
    return ([n.name for n in region_tree.body if isinstance(n, ast.FunctionDef)],
            [n.name for n in region_tree.body if isinstance(n, ast.ClassDef)])


def contract_constant(contract_tree, name):
    """One module-level integer constant from the contract, or None."""
    for node in contract_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                    return node.value.value
    return None


def check_callables(module, region_tree, expected):
    """Every top-level def and class in the region resolves, and the count matches the contract.

    `coauthor.py` has no `__all__`, so this counts statements rather than reading a list. A splice
    that truncated the file mid-function would otherwise only surface as a `NameError` during a
    live screening, after the bond was already posted.
    """
    funcs, classes = region_callables(region_tree)
    names = funcs + classes
    missing = [n for n in names if not hasattr(module, n)]
    if missing:
        print("  FAIL the spliced region defines but does not expose: %s" % ", ".join(missing))
        return False
    not_callable = [n for n in names if not callable(getattr(module, n))]
    if not_callable:
        print("  FAIL not callable after execution: %s" % ", ".join(not_callable))
        return False
    if expected is None:
        print("  FAIL the contract declares no EMBEDDED_FUNCTION_COUNT to check %d callables "
              "against" % len(names))
        return False
    if len(names) != expected:
        print("  FAIL the region defines %d callables (%d def, %d class); the contract declares "
              "EMBEDDED_FUNCTION_COUNT = %d" % (len(names), len(funcs), len(classes), expected))
        return False
    print("  pass all %d region callables resolve and are callable (%d def, %d class), matching "
          "the contract's EMBEDDED_FUNCTION_COUNT" % (len(names), len(funcs), len(classes)))
    return True


# ----------------------------------------------------------------------------------
# Layer 3: behavioural
# ----------------------------------------------------------------------------------

def load_region_as_module(region):
    """Execute the spliced region as a module named `coauthor`.

    Nothing is pre-bound. The region imports nothing and needs nothing, so if that ever stops
    being true the exec fails here rather than passing quietly.
    """
    import types
    module = types.ModuleType(MODULE_NAME)
    module.__file__ = CONTRACT + " (embedded region)"
    exec(compile(region, "<QuorumClean.py embedded coauthor path>", "exec"),   # noqa: S102
         module.__dict__)
    return module


def snapshot(obj):
    """A comparable, order-independent rendering of one container."""
    if isinstance(obj, (set, frozenset)):
        return "set:" + json.dumps(sorted(repr(x) for x in obj))
    if isinstance(obj, dict):
        return "dict:" + json.dumps({str(k): repr(v) for k, v in obj.items()}, sort_keys=True)
    if isinstance(obj, (list, tuple)):
        return "seq:" + json.dumps([repr(x) for x in obj])
    return "value:" + repr(obj)


def snapshot_exempt(module):
    return dict((name, snapshot(getattr(module, name))) for name in sorted(MUTABLE_EXEMPT)
                if hasattr(module, name))


def check_exempt_unmutated(module, before):
    """The four exempted containers, compared before and after the full suite run.

    The static scan proves nothing writes to them through their module-level name. This proves
    nothing wrote to them through an alias, a local binding, or a returned reference either,
    across every path 176 tests exercise. It is the difference between reasoning that the shared
    state is safe and observing that it was not touched.
    """
    after = snapshot_exempt(module)
    if sorted(before) != sorted(after):
        print("  FAIL the exempted container set changed during the run: %s became %s"
              % (sorted(before), sorted(after)))
        return False
    changed = [name for name in before if before[name] != after[name]]
    if changed:
        for name in changed:
            print("  FAIL module-level %s was mutated during the suite run" % name)
            print("       before %s" % before[name][:160])
            print("       after  %s" % after[name][:160])
        return False
    print("  pass all %d exempted containers are byte-identical before and after the suite run, "
          "so the shared module state is observed unmutated and not merely argued to be"
          % len(before))
    return True


def check_gate_two_exhaustively(module):
    """The central rule, enumerated rather than sampled.

    CLEAR requires that every source needed for the pair actually returned usable data. A failed
    source with no tie found forces INSUFFICIENT, never CLEAR. Finding a tie is monotone, so the
    positive verdicts are deliberately NOT blocked by an unrelated failure: a rate limit costs the
    round its clean verdicts and none of its positive ones.

    Four properties are asserted over every attempted-source / failed-source / tie / band
    combination, and the third and fourth are the ones that stop this from being a check a useless
    gate would also pass:

      1. no CLEAR while any source is recorded as failed
      2. every source failed -> INSUFFICIENT, whatever else is true
      3. a tie found by a source that did answer -> CONFLICT or MATERIAL_UNCLEAR, no matter what
         else failed alongside it
      4. full coverage and no tie -> CLEAR

    A tie is only ever offered where a source actually answered, because a tie found by a source
    that returned nothing is not a state this contract can reach, and asserting over impossible
    inputs is how a check comes to describe something other than the program.
    """
    sources = list(module.ALL_SOURCES)
    tie_kinds = {
        module.SOURCE_OPENALEX: (module.TIE_COAUTHOR, "coauthor_ties", "W2741809807"),
        module.SOURCE_ORCID: (module.TIE_SHARED_AFFILIATION, "affiliation_ties", "ror.org/013meh722"),
        module.SOURCE_GITHUB: (module.TIE_CODE_CONTRIBUTION, "contribution_ties", "openai/whisper"),
    }
    positive = (module.VERDICT_CONFLICT, module.VERDICT_MATERIAL_UNCLEAR)

    cleared_over_a_failure = []
    not_insufficient_when_blind = []
    blocked_positives = []
    missing_clear = []
    clean_when_complete = 0
    positives_over_a_failure = 0
    total = 0

    for mask in range(1, 1 << len(sources)):
        attempted = [s for i, s in enumerate(sources) if mask & (1 << i)]
        for fail_mask in range(1 << len(attempted)):
            failed = [s for i, s in enumerate(attempted) if fail_mask & (1 << i)]
            answered = [s for s in attempted if s not in failed]
            # A tie can only be carried by a source that answered, so the tie cases are enumerated
            # per answering source rather than as a free flag.
            tie_options = [(None, None)] + [(s, label) for s in answered
                                            for label in ("MATERIAL", "UNCLEAR", "NOT_MATERIAL")]
            for tie_source, label in tie_options:
                total += 1
                ledger = module.new_ledger()
                for source in attempted:
                    if source in failed:
                        module.record_failed(ledger, source, {
                            "tag": module.TAG_EXTERNAL,
                            "detail": "starved on purpose",
                        })
                    else:
                        module.record_checked(ledger, source)

                groups = {"coauthor_ties": [], "affiliation_ties": [],
                          "contribution_ties": [], "membership_ties": []}
                if tie_source is not None:
                    kind, group, basis = tie_kinds[tie_source]
                    groups[group].append({"tie_kind": kind, "tie_basis": basis,
                                          "in_window": True, "undetermined": False})

                result = module.screen_verdict(
                    ledger,
                    coauthor_ties=groups["coauthor_ties"],
                    affiliation_ties=groups["affiliation_ties"],
                    contribution_ties=groups["contribution_ties"],
                    membership_ties=groups["membership_ties"],
                    materiality_label=label,
                    declared_any_handle=True,
                )
                verdict = result["verdict"]
                case = (tuple(attempted), tuple(failed), tie_source, label, verdict)

                if failed and verdict == module.VERDICT_CLEAR:
                    cleared_over_a_failure.append(case)
                if not answered and verdict != module.VERDICT_INSUFFICIENT:
                    not_insufficient_when_blind.append(case)
                if tie_source is not None:
                    if verdict not in positive:
                        blocked_positives.append(case)
                    elif failed:
                        positives_over_a_failure += 1
                if not failed and tie_source is None:
                    if verdict == module.VERDICT_CLEAR:
                        clean_when_complete += 1
                    else:
                        missing_clear.append(case)

    for label, bad in (("returned CLEAR with a failed source", cleared_over_a_failure),
                       ("did not return INSUFFICIENT with every source failed",
                        not_insufficient_when_blind),
                       ("lost a positive verdict to an unrelated source failure; finding a tie is "
                        "monotone and a rate limit must cost the clean verdicts only",
                        blocked_positives),
                       ("did not return CLEAR under full coverage with no tie", missing_clear)):
        if bad:
            print("  FAIL %d of %d combinations %s" % (len(bad), total, label))
            for case in bad[:3]:
                print("       attempted=%s failed=%s tie_from=%s band=%s got %s"
                      % (",".join(case[0]) or "none", ",".join(case[1]) or "none",
                         case[2] or "none", case[3] or "none", case[4]))
            return False

    if clean_when_complete == 0 or positives_over_a_failure == 0:
        print("  FAIL the enumeration reached CLEAR %d times and a positive-over-a-failure %d "
              "times; a zero on either side means this check measured only one half of the rule"
              % (clean_when_complete, positives_over_a_failure))
        return False

    print("  pass gate 2 holds across all %d combinations of attempted sources, failed sources, "
          "which source carried the tie, and materiality band" % total)
    print("       no CLEAR survives a failed source, and every source failing always gives "
          "INSUFFICIENT")
    print("       %d combinations still reach CONFLICT or MATERIAL_UNCLEAR with another source "
          "failed, so the gate costs the clean verdicts only" % positives_over_a_failure)
    print("       %d fully covered tie-free combinations do reach CLEAR, so the gate is not "
          "simply refusing to clear anything" % clean_when_complete)
    return True


def run_suite_against(module):
    """Run the standalone suite with `coauthor` bound to the spliced copy.

    Loaded with `unittest.TestLoader` rather than by walking `vars()`, because this suite is 176
    tests across 20 `TestCase` classes with `setUpClass` fixtures. Walking the module namespace
    would find the classes, call none of the tests, and report a clean run over nothing.
    """
    if SUITE_DIR not in sys.path:
        sys.path.insert(0, SUITE_DIR)
    sys.modules[MODULE_NAME] = module
    sys.modules.pop(SUITE_NAME, None)
    suite_module = __import__(SUITE_NAME)

    loaded = unittest.TestLoader().loadTestsFromModule(suite_module)
    buffer = io.StringIO()
    result = unittest.TextTestRunner(stream=buffer, verbosity=0).run(loaded)

    broken = [(str(case), tb) for case, tb in list(result.failures) + list(result.errors)]
    skipped = [(str(case), why) for case, why in result.skipped]
    passed = result.testsRun - len(broken) - len(skipped)
    for name, tb in broken:
        print("  FAIL %s" % name)
        print("       " + tb.strip().replace("\n", "\n       ")[:2000])
    return passed, skipped, broken, result.testsRun


def main(argv):
    write = "--write" in argv[1:]

    if write:
        write_splice()
        print("")

    source = read(SOURCE)
    contract_text = read(CONTRACT)
    region = extract_region(source, os.path.relpath(SOURCE, REPO))
    current = extract_region(contract_text, os.path.relpath(CONTRACT, REPO))
    begin_line, end_line = marker_lines(contract_text)

    print("splice guard: %s -> %s" % (os.path.relpath(SOURCE, REPO),
                                      os.path.relpath(CONTRACT, REPO)))
    print("  source file sha256 %s (%d lines, %d bytes)"
          % (sha256(source), source.count("\n"), len(source.encode("utf-8"))))
    print("  contract markers at lines %d and %d" % (begin_line, end_line))
    print("")

    if current.strip() == "":
        print("  FAIL the region between the markers is empty; run with --write first")
        return 1

    results = []
    print("textual")
    results.append(check_textual(region, current))
    print("")

    print("structural, against the spliced region and not against coauthor.py")
    try:
        region_tree = ast.parse(current)
    except SyntaxError as exc:
        print("  FAIL the spliced region does not parse: %s at line %s" % (exc.msg, exc.lineno))
        return 1
    contract_tree = ast.parse(contract_text)
    in_region = lambda node: begin_line < getattr(node, "lineno", 0) < end_line

    results.append(check_region_imports(region_tree))
    results.append(check_contract_imports(contract_tree, begin_line, end_line))
    results.append(check_no_status_code(region_tree, contract_tree, skip=in_region))
    results.append(check_no_digest_over_a_raw_body(contract_tree, begin_line, end_line))
    results.append(check_broad_handlers_are_last(region_tree, "the region"))
    results.append(check_contract_never_swallows_a_refusal(
        contract_tree, begin_line, end_line))
    results.append(check_broad_handlers_are_annotated(contract_text, begin_line, end_line))
    results.append(check_no_io(region_tree, "the region"))
    results.append(check_no_io(contract_tree, "the contract", skip=in_region))
    results.append(check_module_state(region_tree))
    results.append(check_screen_never_names_a_verdict(contract_tree))
    results.append(check_appeal_cannot_clear_over_a_failed_source(contract_tree))
    print("")

    print("behavioural, the standalone suite re-run against the spliced copy")
    try:
        module = load_region_as_module(current)
    except Exception as exc:                                             # noqa: BLE001
        print("  FAIL the region will not execute as a module: %r" % (exc,))
        traceback.print_exc()
        return 1
    results.append(check_callables(
        module, region_tree, contract_constant(contract_tree, "EMBEDDED_FUNCTION_COUNT")))
    results.append(check_gate_two_exhaustively(module))

    before = snapshot_exempt(module)
    passed, skipped, broken, total = run_suite_against(module)
    if broken:
        print("  FAIL %d of %d tests failed against the spliced copy" % (len(broken), total))
        results.append(False)
    else:
        print("  pass %d of %d tests pass against the spliced copy, %d skipped"
              % (passed, total, len(skipped)))
        results.append(True)
    for name, why in skipped:
        print("  skip %s: %s" % (name, str(why)[:150]))
    results.append(check_exempt_unmutated(module, before))
    print("  note %d of those %d read coauthor.py from disk by absolute path, so they say nothing "
          "about the splice: %s. All four are re-checked above, against the region."
          % (len(VACUOUS_AGAINST_SPLICE), total, ", ".join(VACUOUS_AGAINST_SPLICE)))
    print("")

    if all(results):
        print("splice verified: %d checks, %d tests (%d passed, %d skipped), region sha256 %s"
              % (len(results), total, passed, len(skipped), sha256(region)))
        return 0
    print("splice NOT verified: %d of %d checks failed"
          % (len([r for r in results if not r]), len(results)))
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
