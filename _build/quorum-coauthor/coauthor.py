"""Quorum Clean: co-authorship, employment and contribution overlap detection.

Standalone, unit-testable source for the deterministic core of PRD 04 ("Quorum Clean",
genlayer-prds/04-reviewer-integrity-gate.md). A GenLayer Intelligent Contract cannot import a
sibling Python file, so this module is developed and tested here and then spliced verbatim into
contracts/quorum_clean.py behind a drift guard. See README.md for the splice contract.

Deliberate constraints, all load bearing:

  * ZERO imports. Not even `re` or `json`. Everything here is plain-string and integer work so the
    spliced copy cannot depend on a module that is unavailable inside a contract.
  * No I/O, no clock, no filesystem. HTTP happens only through an injected `fetch` callable.
    "Now" is never read; every date window arrives as an argument.
  * Absence is never success. Empty results, 403, 429, 404 and an unparseable body are all
    source-unreachable conditions. None of them may be reported as "no conflict found". The whole
    product gates voting weight on the absence of a conflict, so an unreachable source that reads
    as clean is the one failure that would discredit it.
  * The model is asked what the evidence says, never what the contract should do. Every function
    here that touches model output is classification only; the weight decision is made in code.

Injected fetch contract (the adapter in the contract wraps gl.nondet.web.request):

    fetch(url, headers=None) -> {
        "status":  int,            # note: `.status`, matching the SDK field name
        "headers": {str: str},     # lowercase keys
        "json":    parsed body or None if the body was not JSON,
        "text":    raw body as str,
    }

    A transport failure is signalled by the adapter raising TransientError, or by returning
    status 0, which this module maps to [TRANSIENT].

Everything between the two SPLICE markers below is what gets copied into
`quorum-clean/contracts/QuorumClean.py`. `test_coauthor.py` recomputes the digest of that exact
region and `quorum-clean/scripts/splice_coauthor.py` recomputes it the same way, so the suite's
number and the guard's number are one number rather than two that measure nearly the same text.
"""

# --- QUORUM-COAUTHOR SPLICE BEGIN ---

# ---------------------------------------------------------------------------
# 1. Error taxonomy. Exactly these four tags, build-wide.
# ---------------------------------------------------------------------------

TAG_EXPECTED = "[EXPECTED]"      # caller error: bad handle, bad argument, our own bad request
TAG_EXTERNAL = "[EXTERNAL]"      # source unreachable or unusable: 403/429/404/empty/unparseable
TAG_TRANSIENT = "[TRANSIENT]"    # transport failure: connection died, status 0, 5xx
TAG_LLM_ERROR = "[LLM_ERROR]"    # malformed model output

ALL_TAGS = (TAG_EXPECTED, TAG_EXTERNAL, TAG_TRANSIENT, TAG_LLM_ERROR)


class QuorumError(Exception):
    """Base for every failure this module raises. `tag` is one of ALL_TAGS."""

    tag = TAG_EXPECTED

    def __init__(self, detail, source=""):
        self.detail = detail
        self.source = source
        Exception.__init__(self, self.tag + " " + detail)

    def as_dict(self):
        return {"tag": self.tag, "detail": self.detail, "source": self.source}


class ExpectedError(QuorumError):
    tag = TAG_EXPECTED


class ExternalError(QuorumError):
    tag = TAG_EXTERNAL


class TransientError(QuorumError):
    tag = TAG_TRANSIENT


class LlmError(QuorumError):
    tag = TAG_LLM_ERROR


# ---------------------------------------------------------------------------
# 2. Verdicts, weights and tie kinds. PRD section 5 and section 6 storage.
# ---------------------------------------------------------------------------

VERDICT_CLEAR = "CLEAR"                      # no publicly evidenced tie in the sources checked
VERDICT_CONFLICT = "CONFLICT"
VERDICT_MATERIAL_UNCLEAR = "MATERIAL_UNCLEAR"
VERDICT_UNSCREENED = "UNSCREENED"            # no handles declared; NOT clean
VERDICT_INSUFFICIENT = "INSUFFICIENT"        # sources unreachable; NOT clean; retryable

WEIGHT_FULL = 10000       # basis points
WEIGHT_PARTIAL = 5000     # MATERIAL_UNCLEAR reduces rather than zeroes
WEIGHT_ZERO = 0

TIE_COAUTHOR = "COAUTHOR"
TIE_SHARED_AFFILIATION = "SHARED_AFFILIATION"
TIE_CODE_CONTRIBUTION = "CODE_CONTRIBUTION"
TIE_ORG_MEMBERSHIP = "ORG_MEMBERSHIP"
TIE_NONE = "NONE"

# Measured live 2026-08-25 and pinned in _build/fixtures/quorum-clean/manifest.json. These are
# recorded as constants so a capture script and the contract cannot drift apart on payload size.
MEASURED_OPENALEX_AUTHORS_BYTES = 6800
MEASURED_OPENALEX_WORKS_SELECT_BYTES = 6918
MEASURED_OPENALEX_WORKS_NO_SELECT_BYTES = 34362   # 5x the select= payload
MEASURED_ORCID_JSON_BYTES = 22492
MEASURED_ORCID_XML_BYTES = 44000                  # what you get without the Accept header
MEASURED_GITHUB_CONTRIBUTORS_BYTES = 14054
GITHUB_UNAUTH_HOURLY_LIMIT = 60                   # per hour, per IP, unauthenticated


# ---------------------------------------------------------------------------
# 3. Entity normalization.
#
# THE RULE, in one sentence: a name is normalized by folding Latin accents to ASCII, lowercasing,
# replacing every character that is not a letter or a digit with a space, expanding a fixed closed
# table of structural abbreviations, dropping a fixed closed list of structural words, and joining
# the surviving tokens with single spaces in their original order.
#
# Nothing else is removed. There is no acronym synthesis, no stemming, no edit-distance matching
# and no token reordering, because a normalization aggressive enough to merge two genuinely
# different institutions is worse than one that misses a match: the first downweights an innocent
# reviewer, the second only fails to find a tie that the appeal path can still raise.
# ---------------------------------------------------------------------------

# Latin-1 and Latin Extended-A folding, spelled out so no import is needed.
_ASCII_FOLD = {
    "À": "a", "Á": "a", "Â": "a", "Ã": "a", "Ä": "a", "Å": "a",
    "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a",
    "Ç": "c", "ç": "c",
    "È": "e", "É": "e", "Ê": "e", "Ë": "e",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "Ì": "i", "Í": "i", "Î": "i", "Ï": "i",
    "ì": "i", "í": "i", "î": "i", "ï": "i",
    "Ñ": "n", "ñ": "n",
    "Ò": "o", "Ó": "o", "Ô": "o", "Õ": "o", "Ö": "o", "Ø": "o",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "o", "ø": "o",
    "Ù": "u", "Ú": "u", "Û": "u", "Ü": "u",
    "ù": "u", "ú": "u", "û": "u", "ü": "u",
    "Ý": "y", "ý": "y", "ÿ": "y",
    "ß": "ss", "Æ": "ae", "æ": "ae", "Œ": "oe", "œ": "oe",
    "Ł": "l", "ł": "l", "Š": "s", "š": "s", "Ž": "z", "ž": "z",
    "Č": "c", "č": "c", "Ř": "r", "ř": "r",
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": " ", "—": " ", " ": " ",
}

# Structural abbreviations only. Every entry expands a word that carries no discriminating
# information about WHICH institution is meant. "tech" is deliberately absent: Caltech and
# Georgia Tech are different places and expanding it invites a false merge.
_INSTITUTION_ABBREV = {
    "univ": "university",
    "universite": "university",
    "universitat": "university",
    "universitaet": "university",
    "universidad": "university",
    "universita": "university",
    "inst": "institute",
    "institut": "institute",
    "natl": "national",
    "nat": "national",
    "intl": "international",
    "fdn": "foundation",
    "found": "foundation",
    "lab": "laboratory",
    "labs": "laboratory",
    "laboratories": "laboratory",
    "dept": "department",
    "dep": "department",
    "div": "division",
    "ctr": "center",
    "centre": "center",
    "hosp": "hospital",
    "acad": "academy",
    "assoc": "association",
    "org": "organization",
    "organisation": "organization",
    "co": "company",
    "corp": "corporation",
    "inc": "incorporated",
    "ltd": "limited",
    "gmbh": "company",
    "and": "and",
}

# Purely structural words. Dropping these can never change which institution is denoted.
_INSTITUTION_STOPWORDS = frozenset((
    "the", "of", "for", "at", "in", "de", "der", "des", "du", "da", "di", "la", "le", "el",
    "and", "amp",
))


def _fold_ascii(raw):
    out = []
    for ch in raw:
        out.append(_ASCII_FOLD.get(ch, ch))
    return "".join(out)


def _tokenize(raw):
    """Lowercase, fold accents, split on every non-alphanumeric character."""
    if not isinstance(raw, str):
        raise ExpectedError("normalization input is not a string: " + repr(type(raw).__name__))
    folded = _fold_ascii(raw).lower()
    scrubbed = []
    for ch in folded:
        scrubbed.append(ch if (ch.isalnum() and ch.isascii()) else " ")
    return [t for t in "".join(scrubbed).split(" ") if t]


def normalize_institution(raw):
    """Normalize an institution name to a comparison key. See THE RULE above.

    Two sources spelling one institution differently resolve to one key. Two genuinely different
    institutions must not, so only the closed abbreviation and stop-word tables are applied.
    Returns "" for input that normalizes away entirely, and "" never matches anything: callers
    must treat an empty key as unusable evidence, not as a match.
    """
    tokens = _tokenize(raw)
    out = []
    for tok in tokens:
        tok = _INSTITUTION_ABBREV.get(tok, tok)
        if tok in _INSTITUTION_STOPWORDS:
            continue
        out.append(tok)
    return " ".join(out)


def institutions_match(a, b):
    """True only when both names normalize to the same non-empty key."""
    ka = normalize_institution(a)
    kb = normalize_institution(b)
    return bool(ka) and ka == kb


def normalize_person_name(raw):
    """Normalize a person name for DISPLAY and de-duplication only.

    Identity in Quorum Clean comes from declared handles, never from a name (PRD section 4:
    "Never resolve identity from a name alone"). This function exists so the same human-entered
    label renders identically across sources; it must not be used to link two records. A trailing
    "Lastname, Firstname" form is reordered to "firstname lastname" so the two forms of one label
    agree, and that reordering is exactly why the result is unsafe for identity.
    """
    if not isinstance(raw, str):
        raise ExpectedError("normalization input is not a string")
    if raw.count(",") == 1:
        last, first = raw.split(",", 1)
        if _tokenize(last) and _tokenize(first):
            raw = first + " " + last
    return " ".join(_tokenize(raw))


def normalize_repo_id(raw):
    """Normalize a repository identifier to lowercase "owner/name".

    Accepts "Owner/Name", "https://github.com/Owner/Name(.git)", "git@github.com:Owner/Name.git"
    and any of those with a trailing slash. Only the host prefix, a trailing ".git", a trailing
    slash and letter case are removed; GitHub owner and repository names are case-insensitive, so
    this merges nothing that GitHub itself treats as distinct. Raises ExpectedError on anything
    that is not resolvable to exactly one owner and one name.
    """
    if not isinstance(raw, str):
        raise ExpectedError("repo id is not a string")
    s = raw.strip()
    if not s:
        raise ExpectedError("repo id is empty")
    for prefix in ("https://", "http://", "ssh://", "git://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    if s.lower().startswith("git@"):
        s = s[4:].replace(":", "/", 1)
    for host in ("www.github.com/", "github.com/", "api.github.com/repos/"):
        if s.lower().startswith(host):
            s = s[len(host):]
            break
    while s.endswith("/"):
        s = s[:-1]
    if s.lower().endswith(".git"):
        s = s[:-4]
    parts = [p for p in s.split("/") if p]
    if len(parts) != 2:
        raise ExpectedError("repo id must be owner/name, got: " + raw)
    owner, name = parts[0].lower(), parts[1].lower()
    for part in (owner, name):
        for ch in part:
            if not (ch.isalnum() and ch.isascii()) and ch not in "-_.":
                raise ExpectedError("illegal character in repo id: " + raw)
    return owner + "/" + name


def normalize_github_login(raw):
    """GitHub logins are case-insensitive; lowercase is the whole rule."""
    if not isinstance(raw, str):
        raise ExpectedError("github login is not a string")
    s = raw.strip()
    if s.startswith("@"):
        s = s[1:]
    if not s:
        raise ExpectedError("github login is empty")
    for ch in s:
        if not (ch.isalnum() and ch.isascii()) and ch != "-":
            raise ExpectedError("illegal character in github login: " + raw)
    return s.lower()


# ---------------------------------------------------------------------------
# 4. Dates and COI window arithmetic.
#
# A date is a plain (year, month, day) tuple of ints. Tuple comparison is already chronological
# comparison, so no date library and therefore no import is needed, and there is no clock: the
# window always arrives as an argument.
#
# BOUNDARY RULE: every interval in this module is CLOSED, i.e. INCLUSIVE AT BOTH ENDS.
#   * An overlap that ends exactly on the first day of the COI window IS inside the window.
#   * An overlap that starts exactly on the last day of the COI window IS inside the window.
# Two intervals overlap iff max(starts) <= min(ends). A shared employer on strictly disjoint
# intervals is not a tie, which is the "non-overlapping windows -> CLEAR" row of the PRD test plan.
#
# Partial dates are widened, never narrowed: a start date given as a bare year becomes 1 January
# and an end date given as a bare year becomes 31 December. Widening can only create a candidate
# overlap that then goes to materiality; narrowing could destroy a real one and produce a false
# CLEAR, and a false CLEAR is the failure this whole product exists to avoid. Any record whose
# bounds were imputed carries imputed=True so the caller can refuse to assert CONFLICT on slack
# alone. A record with no usable start date at all is unusable evidence, never "no overlap".
# ---------------------------------------------------------------------------

OPEN_END = (9999, 12, 31)      # employment with no end date: "present"
_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year, month):
    if not (1 <= month <= 12):
        raise ExpectedError("month out of range: " + str(month))
    if month == 2 and _is_leap(year):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def make_date(year, month=None, day=None, end=False):
    """Build a (y, m, d) tuple, widening a partial date. `end=True` widens upward.

    Returns (date_tuple, imputed_bool). Raises ExpectedError when the year is unusable, because a
    record with no year cannot be placed inside or outside a window and must not be guessed at.
    """
    y = _as_int(year, "year")
    if y is None:
        raise ExpectedError("date has no usable year")
    if y < 1000 or y > 9999:
        raise ExpectedError("year out of range: " + str(y))
    m = _as_int(month, "month")
    d = _as_int(day, "day")
    imputed = m is None or d is None
    if m is None:
        m = 12 if end else 1
    if not (1 <= m <= 12):
        raise ExpectedError("month out of range: " + str(m))
    if d is None:
        d = days_in_month(y, m) if end else 1
    if not (1 <= d <= days_in_month(y, m)):
        raise ExpectedError("day out of range: " + str(d))
    return (y, m, d), imputed


def _as_int(value, label):
    """Coerce an int-or-numeric-string to int. None and "" mean absent, not zero."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ExpectedError(label + " is a bool")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        neg = s.startswith("-")
        body = s[1:] if neg else s
        if not body or not body.isdigit():
            raise ExpectedError(label + " is not numeric: " + repr(value))
        n = int(body)
        return -n if neg else n
    raise ExpectedError(label + " has unusable type " + type(value).__name__)


def interval_overlap(a_start, a_end, b_start, b_end):
    """Closed-interval intersection. Returns (start, end) or None when disjoint.

    Inclusive at both ends: touching intervals overlap on the single shared day.
    """
    for name, val in (("a_start", a_start), ("a_end", a_end),
                      ("b_start", b_start), ("b_end", b_end)):
        if not (isinstance(val, tuple) and len(val) == 3):
            raise ExpectedError(name + " is not a (y, m, d) tuple")
    if a_start > a_end or b_start > b_end:
        raise ExpectedError("interval start is after its end")
    lo = a_start if a_start > b_start else b_start
    hi = a_end if a_end < b_end else b_end
    if lo > hi:
        return None
    return (lo, hi)


def coi_window_from_years(start_year, end_year):
    """Build a closed COI window spanning whole calendar years.

    The PRD fixes no numeric window length, so the window is always supplied by the caller (the
    round operator declares it) and never derived from a clock inside this module.
    """
    sy = _as_int(start_year, "start_year")
    ey = _as_int(end_year, "end_year")
    if sy is None or ey is None:
        raise ExpectedError("COI window needs both years")
    if sy > ey:
        raise ExpectedError("COI window start year is after its end year")
    return ((sy, 1, 1), (ey, 12, 31))


def overlap_in_window(overlap_start, overlap_end, window):
    """True when a closed overlap interval intersects the closed COI window at all.

    Inclusive at both ends. An overlap ending exactly on window[0] is in window; an overlap
    starting exactly on window[1] is in window. The same overlap shifted one day further out is
    not, which is the pair of boundary conditions the test suite pins.
    """
    if not (isinstance(window, tuple) and len(window) == 2):
        raise ExpectedError("window is not a (start, end) pair")
    return interval_overlap(overlap_start, overlap_end, window[0], window[1]) is not None


def months_of_overlap(start, end):
    """Inclusive count of calendar months touched by a closed interval. Materiality input only."""
    if start > end:
        raise ExpectedError("interval start is after its end")
    return (end[0] * 12 + end[1]) - (start[0] * 12 + start[1]) + 1


def year_in_window(publication_year, window):
    """Place a bare publication year inside the closed COI window.

    A work with no publication_year is UNDETERMINED, and the manifest is explicit that it "cannot
    be silently treated as in-window or out-of-window", so this raises rather than returning False.
    Returns True or False only when the year is actually known.
    """
    y = _as_int(publication_year, "publication_year")
    if y is None:
        raise ExternalError("work has no publication_year; window position is undetermined",
                            source="openalex")
    start, end = window
    return start[0] <= y <= end[0]


def fmt_date(d):
    """Stable YYYY-MM-DD rendering, or "present" for the open-end sentinel. Used in tie_basis,
    so it must be byte-identical across validators."""
    if d == OPEN_END:
        return "present"
    return "%04d-%02d-%02d" % (d[0], d[1], d[2])


# ---------------------------------------------------------------------------
# 5. HTTP response classification. Shared by all three sources.
# ---------------------------------------------------------------------------

OPENALEX_HOST = "https://api.openalex.org"
ORCID_HOST = "https://pub.orcid.org"
GITHUB_HOST = "https://api.github.com"


def classify_status(status, headers=None, source=""):
    """Map an HTTP status onto the error taxonomy. Returns None when the response is usable.

    * 200..299                -> None (usable)
    * 0                       -> [TRANSIENT] (adapter signalled a dead transport)
    * 400, 405, 414, 422      -> [EXPECTED] (we built a bad request; that is our bug, not theirs)
    * 403, 429                -> [EXTERNAL] rate limited. Measured limit is 60/hour/IP
    *                            unauthenticated on GitHub, so this is a normal operating
    *                            condition, not an edge case, and it is NEVER an absence of
    *                            conflict.
    * 401, 404, other 4xx     -> [EXTERNAL] source will not give us the record
    * 5xx                     -> [TRANSIENT] retryable at the transport level
    """
    st = _as_int(status, "status")
    if st is None:
        raise TransientError("response carried no status", source=source)
    hdrs = _lower_headers(headers)
    if 200 <= st <= 299:
        return None
    if st == 0:
        raise TransientError("transport failure (status 0)", source=source)
    if st in (400, 405, 414, 422):
        raise ExpectedError("request rejected as malformed (HTTP %d)" % st, source=source)
    if st in (403, 429):
        remaining = hdrs.get("x-ratelimit-remaining")
        limit = hdrs.get("x-ratelimit-limit")
        if remaining == "0":
            raise ExternalError(
                "rate limited (HTTP %d, x-ratelimit-remaining 0, limit %s)" % (st, limit or "?"),
                source=source)
        raise ExternalError("access refused (HTTP %d)" % st, source=source)
    if 500 <= st <= 599:
        raise TransientError("source error (HTTP %d)" % st, source=source)
    if 300 <= st <= 499:
        raise ExternalError("record not available (HTTP %d)" % st, source=source)
    raise ExternalError("unexpected status %d" % st, source=source)


def _lower_headers(headers):
    if not headers:
        return {}
    if not isinstance(headers, dict):
        raise ExpectedError("headers is not a dict")
    out = {}
    for k, v in headers.items():
        out[str(k).lower()] = v
    return out


def _call(fetch, url, headers=None, source=""):
    """Invoke the injected fetch, normalize the response, and classify the status.

    Any exception from the adapter that is not already a QuorumError is a transport failure and
    becomes [TRANSIENT]. A QuorumError from the adapter is passed through with its own tag.
    """
    if not callable(fetch):
        raise ExpectedError("fetch is not callable", source=source)
    try:
        resp = fetch(url, headers)
    except QuorumError:
        raise
    except Exception as exc:                                  # noqa: BLE001 - adapter boundary
        raise TransientError("fetch raised " + type(exc).__name__ + ": " + str(exc), source=source)
    if not isinstance(resp, dict):
        raise TransientError("fetch returned " + type(resp).__name__ + ", expected dict",
                             source=source)
    classify_status(resp.get("status"), resp.get("headers"), source=source)
    return {
        "status": _as_int(resp.get("status"), "status"),
        "headers": _lower_headers(resp.get("headers")),
        "json": resp.get("json"),
        "text": resp.get("text") or "",
        "url": url,
    }


# ---------------------------------------------------------------------------
# 6. OpenAlex: author resolution and the co-authorship graph.
#
# Every OpenAlex call carries select=. Measured 2026-08-25: 6,918 B with select= against 34,362 B
# without, a 5x reduction. Inside a consensus block every validator fetches independently, so
# payload size is a consensus cost and a call without select= is a bug even when it returns 200.
# select= also pins the field set, which is what keeps responses stable across validators.
# ---------------------------------------------------------------------------

OPENALEX_WORKS_SELECT = "id,title,authorships,publication_year"
OPENALEX_WORKS_PER_PAGE = 50
# Every field the deterministic path reads. assert_openalex_select refuses a URL that omits one,
# because a select= list missing publication_year silently disables the COI window arithmetic.
OPENALEX_REQUIRED_SELECT_FIELDS = ("id", "authorships", "publication_year")


def _query_params(url):
    """Split a URL query string into an ordered list of (key, value) pairs. No import needed."""
    if not isinstance(url, str):
        raise ExpectedError("url is not a string")
    if "?" not in url:
        return []
    query = url.split("?", 1)[1]
    if "#" in query:
        query = query.split("#", 1)[0]
    pairs = []
    for chunk in query.split("&"):
        if not chunk:
            continue
        if "=" in chunk:
            k, v = chunk.split("=", 1)
        else:
            k, v = chunk, ""
        pairs.append((k, v))
    return pairs


def assert_openalex_select(url):
    """Refuse an OpenAlex works URL that does not carry a usable select=.

    This is the guard the PRD's payload discipline reduces to, and it lives inside this module so a
    select=-less URL cannot reach the network from any call path. Raises ExpectedError, tagged
    [EXPECTED], because a missing select= is our own bug and not a source failure.
    """
    params = dict(_query_params(url))
    if "select" not in params:
        raise ExpectedError(
            "OpenAlex URL has no select= (measured %d B without it against %d B with it, a 5x "
            "consensus payload cost): %s"
            % (MEASURED_OPENALEX_WORKS_NO_SELECT_BYTES,
               MEASURED_OPENALEX_WORKS_SELECT_BYTES, url),
            source="openalex")
    raw = params["select"].strip()
    if not raw:
        raise ExpectedError("OpenAlex select= is empty: " + url, source="openalex")
    fields = [f.strip() for f in raw.replace("%2C", ",").replace("%2c", ",").split(",") if f.strip()]
    for required in OPENALEX_REQUIRED_SELECT_FIELDS:
        if required not in fields:
            raise ExpectedError(
                "OpenAlex select= is missing the required field '%s': %s" % (required, url),
                source="openalex")
    return True


def validate_openalex_author_id(raw):
    """OpenAlex author ids look like A5069172917. Accepts a bare id or a full openalex.org URL."""
    if not isinstance(raw, str):
        raise ExpectedError("openalex author id is not a string")
    s = raw.strip()
    if "/" in s:
        s = s.rstrip("/").rsplit("/", 1)[1]
    if len(s) < 2 or s[0] not in "Aa" or not s[1:].isdigit():
        raise ExpectedError("not an OpenAlex author id: " + raw, source="openalex")
    return "A" + s[1:]


def build_openalex_author_search_url(name):
    """authors?search={name}. Measured 6,800 B. Used for display resolution ONLY: PRD section 4
    forbids resolving identity from a name, so nothing downstream may treat a hit here as a link."""
    if not isinstance(name, str) or not name.strip():
        raise ExpectedError("author search name is empty", source="openalex")
    return OPENALEX_HOST + "/authors?search=" + _urlencode(name.strip())


def build_openalex_works_url(author_id, per_page=OPENALEX_WORKS_PER_PAGE, cursor=None):
    """works?filter=author.id:{id}&select=...&per-page=50, matching the pinned capture example."""
    aid = validate_openalex_author_id(author_id)
    pp = _as_int(per_page, "per_page")
    if pp is None or pp < 1 or pp > 200:
        raise ExpectedError("per_page out of range: " + str(per_page), source="openalex")
    url = (OPENALEX_HOST + "/works?filter=author.id:" + aid
           + "&select=" + OPENALEX_WORKS_SELECT + "&per-page=" + str(pp))
    if cursor:
        if not isinstance(cursor, str):
            raise ExpectedError("cursor is not a string", source="openalex")
        url += "&cursor=" + _urlencode(cursor)
    assert_openalex_select(url)      # belt and braces: the builder checks its own output
    return url


_SAFE_URL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~")


def _urlencode(raw):
    """Percent-encode, no import. Deterministic uppercase hex so validators agree byte-for-byte."""
    out = []
    for ch in raw:
        if ch in _SAFE_URL_CHARS:
            out.append(ch)
        else:
            for byte in ch.encode("utf-8"):
                out.append("%%%02X" % byte)
    return "".join(out)


def fetch_openalex_works(fetch, author_id, per_page=OPENALEX_WORKS_PER_PAGE):
    """Fetch one page of works for an author. Raises with a tag; never returns a partial success."""
    url = build_openalex_works_url(author_id, per_page)
    resp = _call(fetch, url, None, source="openalex")
    payload = resp["json"]
    if payload is None:
        raise ExternalError("OpenAlex response was not parseable JSON", source="openalex")
    return payload


def parse_openalex_authors(payload):
    """Parse authors?search= results. Empty results is [EXTERNAL], never a clean screening.

    The manifest pins results_count 0 -> INSUFFICIENT: "a name that resolves to nobody is
    INSUFFICIENT and retryable, and must never resolve to the nearest plausible author". Several
    candidates is also not resolvable here; the caller must send that to the identity-link
    consensus step, which is allowed to answer none.
    """
    results = _require_list(payload, "results", "openalex")
    if not results:
        raise ExternalError("OpenAlex author search returned 0 results", source="openalex")
    out = []
    for item in results:
        if not isinstance(item, dict):
            raise ExternalError("OpenAlex author entry is not an object", source="openalex")
        try:
            aid = validate_openalex_author_id(item.get("id") or "")
        except ExpectedError:
            raise ExternalError("OpenAlex author entry has no usable id", source="openalex")
        out.append({
            "author_id": aid,
            "display_name": item.get("display_name") or "",
            "name_key": normalize_person_name(item.get("display_name") or ""),
            "orcid": normalize_orcid_maybe(item.get("orcid")),
            "works_count": _as_int(item.get("works_count"), "works_count"),
        })
    out.sort(key=lambda r: r["author_id"])
    return out


def _require_list(payload, key, source):
    if not isinstance(payload, dict):
        raise ExternalError(source + " payload is not an object", source=source)
    if key not in payload:
        raise ExternalError(source + " payload has no '" + key + "' key", source=source)
    value = payload[key]
    if value is None:
        raise ExternalError(source + " '" + key + "' is null", source=source)
    if not isinstance(value, list):
        raise ExternalError(source + " '" + key + "' is not a list", source=source)
    return value


def extract_coauthorship(payload, focus_author_id):
    """Extract the co-authorship graph for one author from a works?select= payload.

    Returns {"author_id", "works": [...], "coauthor_ids": frozenset, "undated_work_ids": [...]}.
    Each work is {"work_id", "title", "year", "author_count", "coauthor_ids"} where coauthor_ids
    excludes the focus author. Works are sorted by work_id and every id list is sorted, because
    validators must produce byte-identical evidence.

    An empty works list is [EXTERNAL]: an author page that returns nothing is an unusable source,
    not proof that the author has no co-authors. A work missing publication_year is kept and its
    id is reported in undated_work_ids so the caller can record it rather than silently placing it
    inside or outside the COI window.

    The focus author id is deliberately NOT required to appear in the returned authorships, and
    the next reader will want to add that check, so here is why it must not be added. OpenAlex
    merges author entities, and a query on a superseded id returns the works with only the
    canonical id on their authorships. Those works really are that author's works; requiring the
    queried id to appear would turn every merged reviewer into a permanently failed source, which
    is the opposite of what the strictness elsewhere in this module is for. The intersection does
    not need it either: whether B co-authored a work is decided by B's id appearing on that work,
    which is unaffected by what A's id resolved to. The absence that does matter, a payload with
    no works in it at all, is caught above.
    """
    focus = validate_openalex_author_id(focus_author_id)
    results = _require_list(payload, "results", "openalex")
    if not results:
        raise ExternalError("OpenAlex works returned 0 results for " + focus, source="openalex")
    works = []
    all_coauthors = set()
    undated = []
    for item in results:
        if not isinstance(item, dict):
            raise ExternalError("OpenAlex work entry is not an object", source="openalex")
        work_id = item.get("id")
        if not isinstance(work_id, str) or not work_id.strip():
            raise ExternalError("OpenAlex work entry has no id", source="openalex")
        work_id = work_id.strip().rstrip("/")
        if "authorships" not in item:
            raise ExternalError(
                "OpenAlex work " + work_id + " has no authorships; select= list is wrong",
                source="openalex")
        authorships = item["authorships"]
        if not isinstance(authorships, list):
            raise ExternalError("authorships is not a list on " + work_id, source="openalex")
        ids = set()
        for a in authorships:
            if not isinstance(a, dict):
                raise ExternalError("authorship entry is not an object on " + work_id,
                                    source="openalex")
            author = a.get("author")
            if not isinstance(author, dict):
                continue
            raw_id = author.get("id")
            if not isinstance(raw_id, str) or not raw_id.strip():
                continue
            try:
                ids.add(validate_openalex_author_id(raw_id))
            except ExpectedError:
                continue
        if not ids:
            raise ExternalError(
                "OpenAlex work " + work_id + " has no resolvable author ids", source="openalex")
        year = None
        if item.get("publication_year") is None:
            undated.append(work_id)
        else:
            year = _as_int(item.get("publication_year"), "publication_year")
        coauthors = ids - {focus}
        works.append({
            "work_id": work_id,
            "title": item.get("title") or "",
            "year": year,
            "author_count": len(ids),
            "coauthor_ids": tuple(sorted(coauthors)),
        })
        all_coauthors |= coauthors
    works.sort(key=lambda w: w["work_id"])
    undated.sort()
    return {
        "author_id": focus,
        "works": works,
        "coauthor_ids": frozenset(all_coauthors),
        "undated_work_ids": tuple(undated),
    }


def coauthorship_overlap(graph_a, author_b_id, window=None):
    """Deterministic co-authorship intersection: which of A's works also list B as an author.

    No model is involved. Returns a list of tie records sorted by work_id, each carrying the facts
    the materiality prompt is later allowed to band: work_id, year, author_count, in_window.
    Works whose year is unknown are returned with in_window=None and undetermined=True, so an
    undated work can never be silently dropped as out-of-window.
    """
    b = validate_openalex_author_id(author_b_id)
    if b == graph_a["author_id"]:
        raise ExpectedError("cannot screen an author against themselves", source="openalex")
    ties = []
    for w in graph_a["works"]:
        if b not in w["coauthor_ids"]:
            continue
        in_window = None
        undetermined = w["year"] is None
        if window is not None and not undetermined:
            in_window = year_in_window(w["year"], window)
        ties.append({
            "tie_kind": TIE_COAUTHOR,
            "tie_basis": w["work_id"],
            "year": w["year"],
            "author_count": w["author_count"],
            "in_window": in_window,
            "undetermined": undetermined,
            "title": w["title"],
        })
    ties.sort(key=lambda t: t["tie_basis"])
    return ties


def shared_third_party_coauthors(graph_a, graph_b):
    """Sorted tuple of author ids that appear in both graphs, excluding the two focus authors.

    A shared collaborator is weaker evidence than direct co-authorship and is reported separately
    so it is never presented as the same kind of tie.
    """
    focus = {graph_a["author_id"], graph_b["author_id"]}
    return tuple(sorted((graph_a["coauthor_ids"] & graph_b["coauthor_ids"]) - focus))


# ---------------------------------------------------------------------------
# 7. ORCID: employment history and affiliation overlap.
#
# ORCID content-negotiates. WITH `Accept: application/json` it returns 22,492 B of JSON; WITHOUT it
# it returns HTTP 200 and 44,000 B of XML. The 200 is what makes this dangerous: a check that only
# asks "did the request succeed" sees success, then finds no employment overlap in bytes it cannot
# parse, and reports a clean screening. So the header is asserted before the call and the body
# shape is asserted after it, and an unparseable body is [EXTERNAL], never an absence of conflict.
# ---------------------------------------------------------------------------

ORCID_HEADERS = {"Accept": "application/json"}


def orcid_check_digit(first_fifteen):
    """The ISO 7064 MOD 11-2 check character for the first fifteen digits of an ORCID iD.

    ORCID iDs are not opaque strings. The sixteenth character is a check digit over the other
    fifteen, and it exists so that a mistyped iD can be caught by the party holding it rather than
    by the server that will not find it. Verified against five published iDs in the test suite,
    including the `X` form, which is what remainder 10 renders as.
    """
    total = 0
    for ch in first_fifteen:
        total = (total + int(ch)) * 2
    remainder = (12 - total % 11) % 11
    return "X" if remainder == 10 else str(remainder)


def normalize_orcid(raw):
    """Validate and normalize an ORCID iD to 0000-0000-0000-000X form.

    Accepts a bare id or an orcid.org URL. The final character may be the checksum digit X.

    The check digit is VERIFIED, not merely required to be digit-shaped. This is the whole reason
    ORCID puts one there, and skipping it is expensive in a way that is easy to miss: a single
    mistyped digit passes every shape test, is stored as a declared handle, and then 404s at every
    screening forever. That surfaces as [EXTERNAL] and INSUFFICIENT, which tells the caller the
    source was unreachable and the screening is worth retrying, and both halves of that are false.
    No retry can ever succeed, because the iD identifies nobody.

    Verifying it here turns that permanent dead end into an [EXPECTED] revert at registration, at
    the moment the typo is still visible to the person who made it, and at a cost of no network
    call at all.
    """
    if not isinstance(raw, str):
        raise ExpectedError("orcid is not a string")
    s = raw.strip()
    if not s:
        raise ExpectedError("orcid is empty")
    for prefix in ("https://", "http://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
    for host in ("www.orcid.org/", "orcid.org/", "pub.orcid.org/v3.0/"):
        if s.lower().startswith(host):
            s = s[len(host):]
            break
    s = s.rstrip("/").upper()
    digits = s.replace("-", "")
    if len(digits) != 16:
        raise ExpectedError("orcid must have 16 characters: " + raw)
    for ch in digits[:15]:
        if not ch.isdigit():
            raise ExpectedError("orcid has a non-digit: " + raw)
    if not (digits[15].isdigit() or digits[15] == "X"):
        raise ExpectedError("orcid checksum character is invalid: " + raw)
    wanted = orcid_check_digit(digits[:15])
    if digits[15] != wanted:
        raise ExpectedError(
            "orcid check digit is wrong: " + raw + " ends in " + digits[15] + " but the first "
            "fifteen digits require " + wanted + ". One character is mistyped; an iD that fails "
            "this check identifies nobody, so no screening against it could ever succeed.")
    return "-".join((digits[0:4], digits[4:8], digits[8:12], digits[12:16]))


def normalize_orcid_maybe(raw):
    """Best-effort normalization for a field that is legitimately allowed to be absent.

    Returns "" for absent or unusable input. Used on the OpenAlex `orcid` field, which the manifest
    notes is what a declared ORCID is checked against at registration.
    """
    if not raw or not isinstance(raw, str):
        return ""
    try:
        return normalize_orcid(raw)
    except ExpectedError:
        return ""


def check_handle_consistency(declared_orcid, openalex_orcid_field):
    """Deterministic handle-consistency check. PRD section 4 step 2.

    When both are declared and both are present they must agree; a mismatch is [EXPECTED] and
    reverts at registration, before any screening runs. A missing OpenAlex orcid field is not a
    contradiction, only an absence, so it passes.
    """
    declared = normalize_orcid(declared_orcid) if declared_orcid else ""
    found = normalize_orcid_maybe(openalex_orcid_field)
    if declared and found and declared != found:
        raise ExpectedError(
            "declared ORCID " + declared + " contradicts the OpenAlex orcid field " + found,
            source="openalex")
    return True


def assert_orcid_json_headers(headers):
    """Refuse an ORCID call that does not ask for JSON.

    Tagged [EXPECTED] because omitting the header is our bug. This guard is the reason the 44 KB
    XML path cannot be entered by accident.
    """
    hdrs = _lower_headers(headers)
    accept = str(hdrs.get("accept", "")).lower()
    if "application/json" not in accept:
        raise ExpectedError(
            "ORCID call must send Accept: application/json (without it ORCID returns HTTP 200 and "
            "%d B of XML instead of %d B of JSON)"
            % (MEASURED_ORCID_XML_BYTES, MEASURED_ORCID_JSON_BYTES),
            source="orcid")
    return True


def build_orcid_record_url(orcid):
    return ORCID_HOST + "/v3.0/" + normalize_orcid(orcid) + "/record"


def guard_orcid_json_body(resp):
    """Assert the body actually is JSON. An XML body is [EXTERNAL], not a successful empty result.

    Checks the parsed payload first, then falls back to sniffing the raw text, because the 200 + XML
    case is exactly the one where status alone is misleading.
    """
    payload = resp.get("json")
    text = resp.get("text") or ""
    ctype = str(resp.get("headers", {}).get("content-type", "")).lower()
    stripped = text.lstrip()
    if stripped.startswith("<"):
        raise ExternalError(
            "ORCID returned a non-JSON (XML) body with HTTP %s; employment history is unparseable, "
            "which is source-unreachable and NOT an absence of conflict" % (resp.get("status"),),
            source="orcid")
    if payload is None:
        raise ExternalError(
            "ORCID body was not parseable JSON (content-type %r)" % (ctype or "absent",),
            source="orcid")
    if not isinstance(payload, dict):
        raise ExternalError("ORCID record is not an object", source="orcid")
    return payload


def fetch_orcid_record(fetch, orcid, headers=None):
    """Fetch and validate one ORCID record. Sends Accept: application/json by construction."""
    hdrs = dict(ORCID_HEADERS) if headers is None else dict(headers)
    assert_orcid_json_headers(hdrs)
    url = build_orcid_record_url(orcid)
    resp = _call(fetch, url, hdrs, source="orcid")
    return guard_orcid_json_body(resp)


def _orcid_date(node, end=False):
    """Read an ORCID date node. Returns (date_tuple, imputed) or (None, False) when absent.

    ORCID nests values as {"year": {"value": "2015"}, "month": null, "day": null}. A null date-node
    on an end-date means "present"; a null start-date means the record is unusable.
    """
    if node is None:
        return None, False
    if not isinstance(node, dict):
        raise ExternalError("ORCID date node is not an object", source="orcid")

    def part(key):
        sub = node.get(key)
        if sub is None:
            return None
        if isinstance(sub, dict):
            return sub.get("value")
        return sub

    year = part("year")
    if year is None or (isinstance(year, str) and not year.strip()):
        return None, False
    return make_date(year, part("month"), part("day"), end=end)


def extract_employments(record):
    """Extract employment affiliations from an ORCID v3.0 record.

    Returns {"orcid", "employments": [...], "unusable": [...]}. Each employment carries the raw
    organization name, its normalized key, a closed [start, end] interval (end = OPEN_END for
    current roles), an imputed flag when a partial date was widened, and the put-code so the tie
    can name a specific record.

    An employment with no usable start date goes to `unusable` rather than being dropped, because
    dropping it would quietly convert missing evidence into an absence of overlap. So does one whose
    dates exist but cannot be placed on a calendar. A record with no employments section at all is
    [EXTERNAL]: the manifest pins employments_present = true, and an unparseable or absent
    employment history is source-unreachable.

    A caller must treat a non-empty `unusable` list as an incompletely read record. This function
    reports what it could and could not place; it does not decide what that costs.
    """
    if not isinstance(record, dict):
        raise ExternalError("ORCID record is not an object", source="orcid")
    ident = ""
    path = record.get("orcid-identifier")
    if isinstance(path, dict):
        ident = normalize_orcid_maybe(path.get("path") or "")
    activities = record.get("activities-summary")
    if not isinstance(activities, dict):
        raise ExternalError("ORCID record has no activities-summary", source="orcid")
    emp_section = activities.get("employments")
    if not isinstance(emp_section, dict):
        raise ExternalError("ORCID record has no employments section", source="orcid")
    groups = emp_section.get("affiliation-group")
    if groups is None:
        raise ExternalError("ORCID employments has no affiliation-group", source="orcid")
    if isinstance(groups, dict):
        groups = [groups]
    if not isinstance(groups, list):
        raise ExternalError("ORCID affiliation-group is not a list", source="orcid")

    employments = []
    unusable = []
    for group in groups:
        if not isinstance(group, dict):
            raise ExternalError("ORCID affiliation-group entry is not an object", source="orcid")
        summaries = group.get("summaries")
        if isinstance(summaries, dict):
            summaries = [summaries]
        if not isinstance(summaries, list):
            raise ExternalError("ORCID affiliation summaries is not a list", source="orcid")
        for wrapper in summaries:
            if not isinstance(wrapper, dict):
                raise ExternalError("ORCID summary entry is not an object", source="orcid")
            summary = wrapper.get("employment-summary")
            if summary is None:
                summary = wrapper
            if not isinstance(summary, dict):
                raise ExternalError("ORCID employment-summary is not an object", source="orcid")
            org = summary.get("organization")
            org_name = ""
            if isinstance(org, dict):
                org_name = org.get("name") or ""
            put_code = summary.get("put-code")
            put_code = "" if put_code is None else str(put_code)
            org_key = normalize_institution(org_name) if org_name else ""
            try:
                start, start_imputed = _orcid_date(summary.get("start-date"), end=False)
                end, end_imputed = _orcid_date(summary.get("end-date"), end=True)
            except ExpectedError as exc:
                # A date the record publishes but nobody can place on a calendar. 29 February in a
                # non-leap year is the live case: ORCID's own canonical record 0000-0002-1825-0097
                # carries 1929-02-29 and 1930-02-29 on both of its employments, and the captured
                # fixture in _build/fixtures/quorum-clean is exactly that record.
                #
                # `make_date` calls it [EXPECTED] and is right to, because a CALLER building that
                # date has a bug. A third party PUBLISHING it does not, and the two cases arrive at
                # the same function. Letting the tag through would abort the whole record and, in
                # the contract, revert the screening outright, since [EXPECTED] is the one tag
                # `_absorb` refuses to absorb. That is a permanent revert: the date will not change
                # on retry, so the pair could never be screened at all.
                #
                # So the row becomes unusable evidence, which is what it is, and the other rows of
                # the same record survive it. It is never dropped: the caller must not read a row
                # it could not place in time as an absence of overlap.
                unusable.append({
                    "org_raw": org_name,
                    "put_code": put_code,
                    "reason": "unusable date: " + exc.detail,
                })
                continue
            if not org_key or start is None:
                unusable.append({
                    "org_raw": org_name,
                    "put_code": put_code,
                    "reason": "missing organization name" if not org_key else "missing start date",
                })
                continue
            if end is None:
                end = OPEN_END
            if start > end:
                unusable.append({
                    "org_raw": org_name,
                    "put_code": put_code,
                    "reason": "start date is after end date",
                })
                continue
            employments.append({
                "org_raw": org_name,
                "org_key": org_key,
                "start": start,
                "end": end,
                "imputed": bool(start_imputed or end_imputed),
                "put_code": put_code,
                "role": summary.get("role-title") or "",
            })
    employments.sort(key=lambda e: (e["org_key"], e["start"], e["end"], e["put_code"]))
    unusable.sort(key=lambda e: (e["org_key"] if "org_key" in e else e["org_raw"], e["put_code"]))
    return {"orcid": ident, "employments": employments, "unusable": unusable}


def employment_overlap(emps_a, emps_b, window=None):
    """Deterministic shared-affiliation detection: same institution, intersecting date intervals.

    No model is involved. Two people at the same institution during overlapping ranges is an
    overlap; the same institution at disjoint times is not. Institutions are compared on the
    normalized key so two spellings of one employer match, and only on that key so two different
    employers do not.

    Returns tie records sorted deterministically, each naming the institution and the overlap
    window (tie_basis is "org name+window", per the PRD storage comment). When a COI window is
    supplied, in_window is computed with closed-interval arithmetic; ties outside it are still
    returned with in_window=False so the caller records what it found rather than hiding it.
    """
    a_list = emps_a["employments"] if isinstance(emps_a, dict) else emps_a
    b_list = emps_b["employments"] if isinstance(emps_b, dict) else emps_b
    ties = []
    for a in a_list:
        for b in b_list:
            if a["org_key"] != b["org_key"]:
                continue
            shared = interval_overlap(a["start"], a["end"], b["start"], b["end"])
            if shared is None:
                continue
            in_window = None
            if window is not None:
                in_window = overlap_in_window(shared[0], shared[1], window)
            ties.append({
                "tie_kind": TIE_SHARED_AFFILIATION,
                "org_key": a["org_key"],
                "org_a": a["org_raw"],
                "org_b": b["org_raw"],
                "overlap_start": shared[0],
                "overlap_end": shared[1],
                "overlap_months": months_of_overlap(shared[0], shared[1]),
                "imputed": bool(a["imputed"] or b["imputed"]),
                "in_window": in_window,
                "tie_basis": a["org_key"] + " " + fmt_date(shared[0]) + ".." + fmt_date(shared[1]),
                "put_codes": (a["put_code"], b["put_code"]),
            })
    ties.sort(key=lambda t: (t["org_key"], t["overlap_start"], t["overlap_end"],
                             t["put_codes"][0], t["put_codes"][1]))
    return ties


# ---------------------------------------------------------------------------
# 8. GitHub: contribution and org-membership overlap.
#
# Unauthenticated GitHub is 60 requests per hour per IP, measured 2026-08-25. Every validator has
# its own IP and burns its own budget, so the limit is per-validator rather than shared, but it is
# tight enough that hitting it is a normal operating condition and not an edge case. Therefore:
#   * capture is BATCHED (one pass over a de-duplicated URL list, never a loop that re-fetches),
#   * results are returned in a cache-shaped dict so the contract can persist them in storage,
#   * 403 and 429 are [EXTERNAL], never "no shared repositories found".
# The contributors endpoint measured 14,054 B.
# ---------------------------------------------------------------------------

GITHUB_CONTRIBUTORS_PER_PAGE = 100
GITHUB_TOP_N = 5              # "top-5 contributor" is a comparison, not an opinion
GITHUB_HEADERS = {"Accept": "application/vnd.github+json"}


def build_github_contributors_url(repo_id, per_page=GITHUB_CONTRIBUTORS_PER_PAGE):
    repo = normalize_repo_id(repo_id)
    pp = _as_int(per_page, "per_page")
    if pp is None or pp < 1 or pp > 100:
        raise ExpectedError("per_page out of range: " + str(per_page), source="github")
    return GITHUB_HOST + "/repos/" + repo + "/contributors?per_page=" + str(pp)


def build_github_org_members_url(org, per_page=GITHUB_CONTRIBUTORS_PER_PAGE):
    if not isinstance(org, str) or not org.strip():
        raise ExpectedError("org is empty", source="github")
    slug = normalize_github_login(org)
    pp = _as_int(per_page, "per_page")
    if pp is None or pp < 1 or pp > 100:
        raise ExpectedError("per_page out of range: " + str(per_page), source="github")
    return GITHUB_HOST + "/orgs/" + slug + "/members?per_page=" + str(pp)


def plan_github_batch(repo_ids, budget=GITHUB_UNAUTH_HOURLY_LIMIT, spent=0):
    """De-duplicate the repositories to fetch and refuse a plan that cannot fit in the budget.

    Returns a sorted list of (repo_id, url) pairs, one entry per distinct repository. Raises
    ExpectedError when the plan would exceed the remaining unauthenticated budget of 60 requests
    per hour per IP, so a caller cannot loop this module into a rate limit: the correct response to
    a budget that is too small is to fetch fewer repositories, not to discover the limit by
    hitting it.
    """
    if not isinstance(repo_ids, (list, tuple)):
        raise ExpectedError("repo_ids is not a list", source="github")
    b = _as_int(budget, "budget")
    s = _as_int(spent, "spent")
    if b is None or b < 0:
        raise ExpectedError("budget must be a non-negative int", source="github")
    if s is None or s < 0:
        raise ExpectedError("spent must be a non-negative int", source="github")
    seen = {}
    for raw in repo_ids:
        repo = normalize_repo_id(raw)
        if repo not in seen:
            seen[repo] = build_github_contributors_url(repo)
    remaining = b - s
    if len(seen) > remaining:
        raise ExpectedError(
            "GitHub batch of %d requests exceeds the remaining unauthenticated budget of %d "
            "(limit %d per hour per IP, %d already spent)"
            % (len(seen), remaining if remaining > 0 else 0, b, s),
            source="github")
    return sorted(seen.items())


def extract_contributors(payload, repo_id=""):
    """Parse a contributors payload into {login: contributions}.

    The manifest pins has_contributions_counts: the count is the overlap weight, and "a contributor
    list without counts cannot distinguish one drive-by commit from a co-maintainer, and the two are
    not the same conflict". So a missing `contributions` field is [EXTERNAL], not a zero.

    An empty contributor list is [EXTERNAL] as well. GitHub returns 200 with an empty array for a
    repository whose contributor list is not yet computed, and treating that as "no shared
    contributors" is exactly the silent pass this module exists to prevent.
    """
    if not isinstance(payload, list):
        raise ExternalError("github contributors payload is not a list", source="github")
    if not payload:
        raise ExternalError("github contributors list is empty for " + (repo_id or "?"),
                            source="github")
    out = {}
    for item in payload:
        if not isinstance(item, dict):
            raise ExternalError("github contributor entry is not an object", source="github")
        login = item.get("login")
        if not isinstance(login, str) or not login.strip():
            continue      # anonymous contributor entries carry no login and cannot be matched
        if "contributions" not in item or item["contributions"] is None:
            raise ExternalError(
                "github contributor " + login + " has no contributions count", source="github")
        count = _as_int(item["contributions"], "contributions")
        key = normalize_github_login(login)
        if key in out:
            out[key] = out[key] + count
        else:
            out[key] = count
    if not out:
        raise ExternalError("github contributors list had no identifiable logins",
                            source="github")
    return out


def rank_contributors(contributors):
    """Rank 1-based by contributions descending, ties broken by login so ranks are deterministic."""
    ordered = sorted(contributors.items(), key=lambda kv: (-kv[1], kv[0]))
    return {login: idx + 1 for idx, (login, _count) in enumerate(ordered)}


def contribution_overlap(repo_id, contributors, login_a, login_b, top_n=GITHUB_TOP_N):
    """Deterministic code-contribution overlap: both handles contribute to the same repository.

    No model is involved. Returns a tie record, or None when at most one of the two appears. The
    record carries both contribution counts and both ranks; `both_top_n` is the deterministic
    comparison the PRD calls out ("top-N contributor is a comparison, not an opinion") and is what
    separates a co-maintainer tie from a single typo-fix commit. This function does not choose a
    verdict; it reports the facts a verdict is computed from.
    """
    repo = normalize_repo_id(repo_id)
    a = normalize_github_login(login_a)
    b = normalize_github_login(login_b)
    if a == b:
        raise ExpectedError("cannot screen a github login against itself", source="github")
    if a not in contributors or b not in contributors:
        return None
    n = _as_int(top_n, "top_n")
    if n is None or n < 1:
        raise ExpectedError("top_n must be a positive int", source="github")
    ranks = rank_contributors(contributors)
    ca, cb = contributors[a], contributors[b]
    ra, rb = ranks[a], ranks[b]
    return {
        "tie_kind": TIE_CODE_CONTRIBUTION,
        "tie_basis": repo,
        "repo": repo,
        "login_a": a,
        "login_b": b,
        "contributions_a": ca,
        "contributions_b": cb,
        "rank_a": ra,
        "rank_b": rb,
        "both_top_n": ra <= n and rb <= n,
        "min_contributions": ca if ca < cb else cb,
        "top_n": n,
    }


def org_membership_overlap(org, members, login_a, login_b):
    """Deterministic public-org-membership overlap.

    Public members only. The manifest is explicit that a private member is invisible here, so a
    negative from this source is never evidence of no shared affiliation, only absence of public
    evidence of one. Returns a tie record or None; a None must not be recorded as a checked-clean
    source, which is why screen_verdict takes sources_failed separately.
    """
    a = normalize_github_login(login_a)
    b = normalize_github_login(login_b)
    if a == b:
        raise ExpectedError("cannot screen a github login against itself", source="github")
    if not isinstance(members, (list, tuple, set, frozenset, dict)):
        raise ExternalError("github org members payload is not a collection", source="github")
    logins = set()
    for item in members:
        if isinstance(item, dict):
            login = item.get("login")
        else:
            login = item
        if isinstance(login, str) and login.strip():
            logins.add(normalize_github_login(login))
    if not logins:
        raise ExternalError("github org members list is empty for " + str(org), source="github")
    if a in logins and b in logins:
        slug = normalize_github_login(org)
        return {
            "tie_kind": TIE_ORG_MEMBERSHIP,
            "tie_basis": "github.com/" + slug,
            "org": slug,
            "login_a": a,
            "login_b": b,
            "public_only": True,
        }
    return None


def fetch_github_contributors_batch(fetch, repo_ids, budget=GITHUB_UNAUTH_HOURLY_LIMIT, spent=0):
    """One batched pass over the distinct repositories. Never loops, never retries.

    Returns {"cache": {repo: {login: contributions}}, "failed": {repo: {tag, detail}},
             "requests_spent": int}. Per-repository failures are recorded with their tag rather
    than raised, because one rate-limited repository must not erase the evidence gathered from the
    others; the caller then has both the findings AND the honest list of what it could not reach.
    A [TRANSIENT] failure aborts the remaining plan, since a dead transport will not recover inside
    one screening and continuing would burn budget for nothing.
    """
    plan = plan_github_batch(repo_ids, budget=budget, spent=spent)
    cache = {}
    failed = {}
    spent_here = 0
    aborted = False
    for repo, url in plan:
        if aborted:
            failed[repo] = {"tag": TAG_TRANSIENT, "detail": "not attempted: batch aborted",
                            "source": "github"}
            continue
        try:
            resp = _call(fetch, url, dict(GITHUB_HEADERS), source="github")
            spent_here += 1
            payload = resp["json"]
            if payload is None:
                raise ExternalError("github body was not parseable JSON", source="github")
            cache[repo] = extract_contributors(payload, repo)
        except TransientError as exc:
            spent_here += 1
            failed[repo] = exc.as_dict()
            aborted = True
        except QuorumError as exc:
            spent_here += 1
            failed[repo] = exc.as_dict()
    return {"cache": cache, "failed": failed, "requests_spent": spent_here}


# ---------------------------------------------------------------------------
# 9. Source accounting.
#
# sources_checked and sources_failed are recorded facts, never inferred (PRD section 7). A source
# that raised is recorded with its tag, and no verdict may be computed without this ledger.
# ---------------------------------------------------------------------------

SOURCE_OPENALEX = "openalex"
SOURCE_ORCID = "orcid"
SOURCE_GITHUB = "github"
ALL_SOURCES = (SOURCE_OPENALEX, SOURCE_ORCID, SOURCE_GITHUB)


def new_ledger():
    return {"checked": [], "failed": {}}


def record_checked(ledger, source):
    if source not in ALL_SOURCES:
        raise ExpectedError("unknown source: " + str(source))
    if source not in ledger["checked"]:
        ledger["checked"].append(source)
        ledger["checked"].sort()
    return ledger


def record_failed(ledger, source, err):
    """Record a source failure. `err` is a QuorumError or a {"tag", "detail"} dict."""
    if source not in ALL_SOURCES:
        raise ExpectedError("unknown source: " + str(source))
    entry = err.as_dict() if isinstance(err, QuorumError) else dict(err)
    tag = entry.get("tag")
    if tag not in ALL_TAGS:
        raise ExpectedError("failure has no valid tag: " + repr(tag))
    ledger["failed"][source] = entry
    if source in ledger["checked"]:
        ledger["checked"].remove(source)
    return ledger


def ledger_summary(ledger):
    """Stable strings for the sources_checked / sources_failed storage fields."""
    checked = ",".join(sorted(ledger["checked"]))
    failed = ",".join(
        s + ":" + ledger["failed"][s]["tag"] for s in sorted(ledger["failed"].keys()))
    return checked, failed


#: Per-source cap inside the rendered detail. The contract already clips each detail to 200 before
#: it reaches the ledger; this second, smaller cap is about the rationale, which holds at most 900
#: characters for every source together plus the verdict line itself.
LEDGER_DETAIL_CAP = 140


def ledger_details(ledger):
    """Why each failed source failed, in one stable line, sorted by source name.

    `ledger_summary` renders `orcid:[EXTERNAL]`, which names the source and the class of failure
    and nothing else. That is enough to compute a verdict and not nearly enough to act on one. A
    reviewer told `INSUFFICIENT | failed=orcid:[EXTERNAL]` cannot tell a rate limit from a
    mistyped iD from a record whose employment dates are unplaceable, and those want three
    different responses: wait, correct the registration, appeal.

    The details were already being computed. Every raise in this module carries a `detail`, and
    `record_failed` stores it; it simply stopped at the storage boundary, because the only reader
    was a function that renders tags. This is that reader.
    """
    parts = []
    for source in sorted(ledger["failed"].keys()):
        detail = str(ledger["failed"][source].get("detail") or "").strip()
        if not detail:
            continue
        if len(detail) > LEDGER_DETAIL_CAP:
            detail = detail[:LEDGER_DETAIL_CAP - 3] + "..."
        parts.append(source + ": " + detail)
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# 10. Model-output handling. Classification only.
#
# House rule for the whole build: the model is asked what the evidence says, never what the
# contract should do. Both functions below take a label out of a closed set and reject anything
# else as [LLM_ERROR]. Neither one returns a verdict or a weight; screen_verdict computes those in
# code from the label plus the deterministic facts.
# ---------------------------------------------------------------------------

IDENTITY_LABELS = ("SAME_PERSON", "DIFFERENT_PERSON", "UNRESOLVED")
MATERIALITY_LABELS = ("MATERIAL", "NOT_MATERIAL", "UNCLEAR")


def classify_identity_link(model_output, fetched_record_ids):
    """Read a cross-source identity-link answer. Returns {"label", "basis"}.

    The model answers only which of IDENTITY_LABELS applies and names the record that establishes
    it. UNRESOLVED is an expected answer and must remain available: forcing a binary here is what
    would downweight an innocent reviewer. A SAME_PERSON answer whose basis is not present in the
    fetched records is [LLM_ERROR], because a link justified by unstated evidence is not defensible
    to the person it affects (EQ_IDENTITY_LINK).
    """
    label, basis = _label_and_basis(model_output, IDENTITY_LABELS, "identity")
    if label == "SAME_PERSON":
        if not basis:
            raise LlmError("identity link SAME_PERSON with no named basis")
        if basis not in set(fetched_record_ids):
            raise LlmError("identity link basis not present in fetched records: " + basis)
    return {"label": label, "basis": basis}


def classify_materiality(model_output, fetched_record_ids):
    """Read a materiality band. Returns {"label", "basis"}.

    UNCLEAR is explicitly an expected answer (EQ_MATERIALITY). The tie_basis is re-checked against
    the fetched records: a model-invented work id or org name is rejected as [LLM_ERROR] with no
    weight change, per PRD section 7 "Verdict re-check".
    """
    label, basis = _label_and_basis(model_output, MATERIALITY_LABELS, "materiality")
    if label in ("MATERIAL", "UNCLEAR"):
        if not basis:
            raise LlmError("materiality " + label + " with no named tie_basis")
        if basis not in set(fetched_record_ids):
            raise LlmError("tie_basis not present in fetched records: " + basis)
    return {"label": label, "basis": basis}


def _label_and_basis(model_output, allowed, what):
    """Accept a dict with "label"/"basis", or a bare label string. Reject everything else."""
    if isinstance(model_output, str):
        label, basis = model_output.strip(), ""
    elif isinstance(model_output, dict):
        label = model_output.get("label")
        basis = model_output.get("basis") or model_output.get("tie_basis") or ""
        if not isinstance(label, str):
            raise LlmError(what + " output has no string label: " + repr(label))
        if not isinstance(basis, str):
            raise LlmError(what + " output basis is not a string: " + repr(basis))
        label, basis = label.strip(), basis.strip()
    else:
        raise LlmError(what + " output is " + type(model_output).__name__ + ", expected dict or str")
    if label.upper() not in allowed:
        raise LlmError(what + " label not in " + "/".join(allowed) + ": " + repr(label))
    return label.upper(), basis


def verify_tie_basis(tie_basis, fetched_record_ids):
    """Deterministic re-check: a CONFLICT must name a record that appears in the fetched data."""
    if not isinstance(tie_basis, str) or not tie_basis.strip():
        raise LlmError("tie_basis is empty")
    if tie_basis.strip() not in set(fetched_record_ids):
        raise LlmError("tie_basis not present in fetched records: " + tie_basis)
    return True


# ---------------------------------------------------------------------------
# 11. Verdict assembly. Deterministic, and the one place weight is decided.
#
# THE CENTRAL RULE: CLEAR requires that every source needed for this pair actually returned usable
# data. If any source failed, and no tie was found, the verdict is INSUFFICIENT, not CLEAR. The PRD
# test plan allows either INSUFFICIENT or "CLEAR with sources_failed recorded"; this module takes
# the strict branch and does not offer the lenient one as an option, because a configuration flag
# that turns a failed source into a clean verdict is precisely how a silent pass gets reintroduced.
#
# INSUFFICIENT changes no weight and is retryable. UNSCREENED is a distinct state from CLEAR: a
# reviewer who declared no handles has not passed a check.
# ---------------------------------------------------------------------------


def screen_verdict(ledger, coauthor_ties=(), affiliation_ties=(), contribution_ties=(),
                   membership_ties=(), materiality_label=None, declared_any_handle=True):
    """Compute {verdict, weight_bp, tie_kind, tie_basis, sources_checked, sources_failed, reason}.

    Order of resolution, and every step is deterministic:
      1. no handles declared            -> UNSCREENED, full weight, flagged, zero prompts
      2. no source returned usable data -> INSUFFICIENT, no weight change
      3. a tie was found                -> CONFLICT / MATERIAL_UNCLEAR from materiality_label
      4. no tie AND a source failed     -> INSUFFICIENT, retryable, NEVER clean
      5. no tie AND all sources usable  -> CLEAR, full weight, zero prompts
    """
    checked, failed = ledger_summary(ledger)
    base = {
        "sources_checked": checked,
        "sources_failed": failed,
        "sources_failed_detail": ledger_details(ledger),
        "tie_kind": TIE_NONE,
        "tie_basis": "",
    }

    if not declared_any_handle:
        base.update({"verdict": VERDICT_UNSCREENED, "weight_bp": WEIGHT_FULL, "flagged": True,
                     "weight_changed": True,
                     "reason": "no handles declared for any source; not screened, not clean"})
        return base

    if not ledger["checked"]:
        base.update({"verdict": VERDICT_INSUFFICIENT, "weight_bp": None, "flagged": True,
                     "weight_changed": False, "retryable": True,
                     "reason": "no source returned usable data; screening is INSUFFICIENT and "
                               "retryable, and absence of evidence is not evidence of no tie"})
        return base

    ties = []
    for group in (coauthor_ties, affiliation_ties, contribution_ties, membership_ties):
        for tie in group or ():
            ties.append(tie)
    # Only ties inside the declared COI window can support a verdict. in_window None means the
    # caller supplied no window, so the tie stands on its own; False means the overlap is real but
    # outside the window, which is deliberately not a conflict.
    in_window_ties = [t for t in ties if t.get("in_window") is not False]

    if in_window_ties:
        in_window_ties.sort(key=lambda t: (_tie_rank(t["tie_kind"]), t["tie_basis"]))
        chosen = in_window_ties[0]
        label = materiality_label
        if label is None:
            base.update({"verdict": VERDICT_MATERIAL_UNCLEAR, "weight_bp": WEIGHT_PARTIAL,
                         "flagged": True, "weight_changed": True,
                         "tie_kind": chosen["tie_kind"], "tie_basis": chosen["tie_basis"],
                         "reason": "a tie was found but materiality was not banded"})
            return base
        if label not in MATERIALITY_LABELS:
            raise LlmError("materiality label not in " + "/".join(MATERIALITY_LABELS)
                           + ": " + repr(label))
        if label == "MATERIAL":
            verdict, weight = VERDICT_CONFLICT, WEIGHT_ZERO
        elif label == "UNCLEAR":
            verdict, weight = VERDICT_MATERIAL_UNCLEAR, WEIGHT_PARTIAL
        else:
            verdict, weight = VERDICT_MATERIAL_UNCLEAR, WEIGHT_PARTIAL
            # NOT_MATERIAL still leaves a named, verified tie on the record. The PRD test plan
            # allows MATERIAL_UNCLEAR or CLEAR for a one-commit tie and forbids CONFLICT; the
            # reduced band is chosen so a real tie is never rendered as no tie at all.
        base.update({"verdict": verdict, "weight_bp": weight,
                     "flagged": verdict != VERDICT_CONFLICT, "weight_changed": True,
                     "tie_kind": chosen["tie_kind"], "tie_basis": chosen["tie_basis"],
                     "reason": "tie found in " + chosen["tie_kind"] + " and banded " + label})
        return base

    if ledger["failed"]:
        tags = ",".join(sorted({ledger["failed"][s]["tag"] for s in ledger["failed"]}))
        base.update({"verdict": VERDICT_INSUFFICIENT, "weight_bp": None, "flagged": True,
                     "weight_changed": False, "retryable": True,
                     "reason": "no tie found in the sources that answered, but " + failed
                               + " did not answer (" + tags + "); an unreachable source is not a "
                               "clean screening"})
        return base

    base.update({"verdict": VERDICT_CLEAR, "weight_bp": WEIGHT_FULL, "flagged": False,
                 "weight_changed": True, "retryable": False,
                 "reason": "no publicly evidenced tie found in the sources checked (" + checked
                           + "); this does not mean no conflict exists"})
    return base


_TIE_ORDER = (TIE_COAUTHOR, TIE_SHARED_AFFILIATION, TIE_CODE_CONTRIBUTION, TIE_ORG_MEMBERSHIP)


def _tie_rank(tie_kind):
    """Strongest evidence first, so the named tie_basis is stable across validators."""
    if tie_kind in _TIE_ORDER:
        return _TIE_ORDER.index(tie_kind)
    return len(_TIE_ORDER)


CLEAR_QUALIFIER = (
    "CLEAR means no publicly evidenced tie was found in the sources checked. It does not mean no "
    "conflict exists. Friendships, family, undisclosed advisory roles, shared investors and prior "
    "employment outside ORCID are invisible to this contract."
)


def render_verdict_line(result):
    """One stable line for the on-chain rationale. CLEAR always carries its qualifier.

    A failed source is rendered twice over: once as `failed=orcid:[EXTERNAL]`, which is the
    machine-readable field, and once as the detail behind it, which is the part a reviewer can act
    on. `sources_failed_detail` is read with `.get` because a caller assembling a result by hand
    predates the field, and a missing detail should render a shorter line rather than raise.
    """
    verdict = result["verdict"]
    parts = [verdict]
    if result.get("tie_basis"):
        parts.append(result["tie_kind"] + "=" + result["tie_basis"])
    parts.append("checked=" + (result["sources_checked"] or "none"))
    if result["sources_failed"]:
        parts.append("failed=" + result["sources_failed"])
        detail = result.get("sources_failed_detail") or ""
        if detail:
            parts.append("why: " + detail)
    if verdict == VERDICT_CLEAR:
        parts.append(CLEAR_QUALIFIER)
    return " | ".join(parts)

# --- QUORUM-COAUTHOR SPLICE END ---


# --- END OF MODULE ---
