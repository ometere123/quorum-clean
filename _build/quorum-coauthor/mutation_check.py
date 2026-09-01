"""Mutation check: prove the suite fails when the module's safety properties are broken.

Not part of the deliverable. Copies coauthor.py into a temp dir with one targeted edit, runs the
suite against the mutant, and reports which tests died. A mutation that nothing catches means the
corresponding test is decorative.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "coauthor.py")
TEST = os.path.join(HERE, "test_coauthor.py")

MUTATIONS = [
    ("M1 403 failure falls through to CLEAR",
     '    if ledger["failed"]:\n        tags = ",".join',
     '    if False:\n        tags = ",".join'),
    ("M2 403/429 treated as a usable response",
     "    if 200 <= st <= 299:\n        return None",
     "    if 200 <= st <= 299 or st in (403, 429):\n        return None"),
    ("M3 institution normalization over-merges",
     '    "the", "of", "for", "at", "in",',
     '    "classic", "los", "angeles", "berkeley", "the", "of", "for", "at", "in",'),
    ("M4 COI window boundary made exclusive",
     "    if lo > hi:\n        return None",
     "    if lo >= hi:\n        return None"),
    ("M5 select= guard disabled",
     '    if "select" not in params:',
     '    if False:'),
    ("M6 empty OpenAlex results treated as no co-authors",
     '        raise ExternalError("OpenAlex works returned 0 results for " + focus, '
     'source="openalex")',
     '        return {"author_id": focus, "works": [], "coauthor_ids": frozenset(), '
     '"undated_work_ids": ()}'),
    ("M7 ORCID Accept header guard disabled",
     '    if "application/json" not in accept:',
     '    if False:'),
    ("M8 missing contributions count defaults to zero",
     '        if "contributions" not in item or item["contributions"] is None:',
     '        if False:'),
]


def run_mutant(label, old, new):
    src = open(SRC, encoding="utf-8").read()
    if src.count(old) != 1:
        return label, "SKIP", "anchor matched %d times" % src.count(old), []
    tmp = tempfile.mkdtemp(prefix="qc-mut-")
    try:
        # The suite reads ../fixtures/quorum-clean/manifest.json, so mirror the layout.
        work = os.path.join(tmp, "quorum-coauthor")
        os.makedirs(work)
        shutil.copytree(os.path.join(HERE, "..", "fixtures"), os.path.join(tmp, "fixtures"))
        with open(os.path.join(work, "coauthor.py"), "w", encoding="utf-8") as fh:
            fh.write(src.replace(old, new))
        shutil.copy(TEST, os.path.join(work, "test_coauthor.py"))
        proc = subprocess.run([sys.executable, "test_coauthor.py"], cwd=work,
                              capture_output=True, text=True, timeout=240)
        out = proc.stdout + proc.stderr
        dead = sorted({ln.split(" ")[1] for ln in out.splitlines()
                       if ln.startswith(("FAIL: ", "ERROR: "))})
        status = "CAUGHT" if proc.returncode != 0 else "SURVIVED"
        return label, status, "%d failing tests" % len(dead), dead[:6]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    survived = 0
    for label, old, new in MUTATIONS:
        lbl, status, detail, dead = run_mutant(label, old, new)
        print("%-9s %-46s %s" % (status, lbl, detail))
        for name in dead:
            print("            - " + name)
        if status != "CAUGHT":
            survived += 1
    print("")
    print("mutations: %d, uncaught: %d" % (len(MUTATIONS), survived))
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
