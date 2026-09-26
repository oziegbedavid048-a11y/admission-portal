"""Turning a pasted course list into catalogue rows.

Schools send their catalogue as a table in a PDF, a page on their site or a
spreadsheet. Retyping it is where mistakes come from, so this reads the paste
instead: the admissions desk copies the block, the parser works out which column
is the course, the duration, the tuition and the intake, and the result is shown
back as an editable table before anything is written.

Nothing here touches the database. Parsing is deliberately a pure function of
the pasted text so it can be tested on real pastes, and so the preview the
admissions desk confirms is exactly what gets saved.

Three shapes are common, and all three are handled:

  * a table copied from a spreadsheet or a PDF, tab or pipe separated, with or
    without a header row,
  * a list where each line separates its fields with a dash, a pipe or a comma,
  * a bare list of course names, where only the name can be recovered.

A line may also name the country, the school or the city, either labelled
("Country: Spain") or on its own above the courses. Those become the defaults
for the whole paste and remain editable afterwards.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# ── Vocabulary ───────────────────────────────────────────────────────

LEVEL_PATTERNS = [
    ("phd", r"\b(ph\.?d|doctora(?:te|l)|dba)\b"),
    ("masters", r"\b(master|masters|msc|m\.sc|mba|mim|ma|llm|postgraduate|pgd)\b"),
    ("diplomas", r"\b(diploma|certificate|foundation|othm|pathway)\b"),
    ("bachelors", r"\b(bachelor|bachelor's|bsc|b\.sc|bba|ba|beng|llb|undergraduate|licence)\b"),
]

# A cell is a heading if it says what the column holds. The first match wins, so
# the more specific words come first.
HEADER_KEYWORDS = [
    ("qualification_level", ("accreditation", "rncp", "qualification", "award", "certification")),
    ("duration", ("duration", "length", "years", "study time")),
    ("tuition", ("tuition", "fee", "fees", "price", "cost", "amount", "annual")),
    ("intake", ("intake", "start", "starts", "entry", "session", "semester")),
    ("scholarship", ("scholarship", "discount", "bursary", "waiver")),
    ("note", ("note", "notes", "remark", "comment", "total", "deposit", "other expenses")),
    ("level", ("level", "degree type", "programme type", "program type", "type")),
    ("name", ("course", "programme", "program", "name", "title", "study")),
]

LABEL_PATTERNS = {
    "country": r"^(?:country|destination)\s*[:\-]\s*(.+)$",
    "school": r"^(?:school|university|institution|college|academy|campus name)\s*[:\-]\s*(.+)$",
    "location": r"^(?:city|location|campus|town)\s*[:\-]\s*(.+)$",
    "badge": r"^(?:badge|status|partnership)\s*[:\-]\s*(.+)$",
    "tagline": r"^(?:tagline|about|summary|description)\s*[:\-]\s*(.+)$",
    "tuition_summary": r"^(?:tuition range|fee range|tuition summary)\s*[:\-]\s*(.+)$",
    "currency": r"^(?:currency)\s*[:\-]\s*(.+)$",
    "application_fee": r"^(?:application fee|app fee)\s*[:\-]\s*(.+)$",
}

SCHOOL_WORDS = (
    "university",
    "universidad",
    "universite",
    "université",
    "school",
    "college",
    "academy",
    "institute",
    "instituto",
    "business school",
    "polytechnic",
    "campus",
)

MONTHS = (
    "january february march april may june july august september october "
    "november december jan feb mar apr jun jul aug sep sept oct nov dec"
).split()

CURRENCY_SYMBOLS = {
    "€": "EUR",
    "£": "GBP",
    "$": "USD",
    "₦": "NGN",
}

CURRENCY_CODES = ("EUR", "GBP", "USD", "NGN", "CAD", "AUD", "CHF", "PLN", "SEK")

DURATION_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*[-–]?\s*(year|yr|yrs|years|month|months|semester|semesters)\b",
    re.IGNORECASE,
)

QUALIFICATION_RE = re.compile(
    r"\b((?:othm\s+)?level\s*\d+(?:\s*\([^)]*\))?|rncp\s*\d+[\w\- ]*)",
    re.IGNORECASE,
)

MONEY_RE = re.compile(
    r"(?:(?P<sym>[€£$₦])\s*)?"
    r"(?P<num>\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"(?:\s*(?P<code>EUR|GBP|USD|NGN|CAD|AUD|CHF|PLN|SEK))?",
    re.IGNORECASE,
)

SPLIT_CANDIDATES = ("\t", "|", ";", " – ", " — ", " - ")


# ── Results ──────────────────────────────────────────────────────────


@dataclass
class ParsedCourse:
    name: str = ""
    level: str = "other"
    duration: str = ""
    qualification_level: str = ""
    tuition: Decimal | None = None
    intake: str = ""
    scholarship: str = ""
    note: str = ""

    def as_dict(self):
        return {
            "name": self.name,
            "level": self.level,
            "duration": self.duration,
            "qualification_level": self.qualification_level,
            "tuition": self.tuition,
            "intake": self.intake,
            "scholarship": self.scholarship,
            "note": self.note,
        }


@dataclass
class ParsedPaste:
    country: str = ""
    school: str = ""
    location: str = ""
    badge: str = ""
    tagline: str = ""
    tuition_summary: str = ""
    currency: str = ""
    application_fee: Decimal | None = None
    courses: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# ── Small helpers ────────────────────────────────────────────────────


def _normalise(value):
    """Smart quotes and hard spaces out, tabs left alone."""
    if value is None:
        return ""
    value = value.replace(" ", " ").replace("’", "'").replace("‘", "'")
    return value.replace("“", '"').replace("”", '"')


def _clean_line(value):
    """Tidy a whole line without touching its tabs.

    A tab is the column separator a spreadsheet paste relies on, so the usual
    whitespace collapse has to wait until the line is split into cells.
    """
    value = _normalise(value)
    value = re.sub(r"[   ]+", " ", value)
    return value.strip(" •·*–-").strip()


def _clean(value):
    """Tidy one cell. Whitespace inside a cell is only ever spacing."""
    value = _normalise(value)
    return re.sub(r"\s+", " ", value).strip(" •·*").strip()


def _looks_like_amount(text):
    """A money figure, as opposed to a stray digit inside a name like C3S."""
    match = MONEY_RE.search(text or "")
    if not match:
        return False
    if match.group("sym") or match.group("code"):
        return True
    num = match.group("num")
    return len(num.replace(",", "").replace(".", "").replace(" ", "")) >= 3


def parse_money(text):
    """The first amount in a piece of text, and the currency if it is stated.

    Both 7,500 and 7.500 mean seven and a half thousand in the catalogues we are
    given, so a lone separator followed by exactly three digits is thousands. A
    separator followed by one or two digits is a decimal point.
    """
    if not text:
        return None, ""

    match = MONEY_RE.search(text)
    if not match:
        return None, ""

    raw = match.group("num")
    currency = ""
    if match.group("sym"):
        currency = CURRENCY_SYMBOLS.get(match.group("sym"), "")
    elif match.group("code"):
        currency = match.group("code").upper()

    digits = raw.replace(" ", "")
    if "," in digits and "." in digits:
        # Whichever separator comes last is the decimal point.
        decimal_sep = "," if digits.rfind(",") > digits.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        digits = digits.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in digits or "." in digits:
        sep = "," if "," in digits else "."
        tail = digits.rsplit(sep, 1)[1]
        digits = digits.replace(sep, "" if len(tail) == 3 else ".")

    try:
        return Decimal(digits), currency
    except InvalidOperation:
        return None, currency


def detect_level(*texts):
    haystack = " ".join(t for t in texts if t).lower()
    for level, pattern in LEVEL_PATTERNS:
        if re.search(pattern, haystack):
            return level
    return "other"


def _looks_like_duration(cell):
    return bool(DURATION_RE.search(cell))


def _looks_like_intake(cell):
    lowered = cell.lower()
    return any(month in lowered for month in MONTHS)


def _looks_like_money(cell):
    if not cell:
        return False
    stripped = cell.strip()
    if DURATION_RE.search(stripped):
        return False
    return _looks_like_amount(stripped)


def _looks_like_school(line):
    """A school name, not a course row.

    Digits are allowed, because C3S Business School and IE University are real
    names, but anything carrying an amount or a duration is a course row.
    """
    lowered = line.lower()
    if not any(word in lowered for word in SCHOOL_WORDS):
        return False
    if DURATION_RE.search(line) or _looks_like_amount(line):
        return False
    return True


# ── Row splitting ────────────────────────────────────────────────────


# "7,000" is one number, not two columns. A comma only separates columns
# when it is not sitting inside a thousands figure, which is what the
# lookaround here says: skip a comma that has a digit before it and exactly
# three digits after it.
_COMMA_SPLIT = re.compile(r"(?<![0-9]),|,(?![0-9]{3}(?:[^0-9]|$))")


def _majority_columns(lines, candidate):
    """How many columns most lines get from this separator, and how many agree."""
    if candidate == ",":
        counts = [len(_COMMA_SPLIT.split(line)) for line in lines if "," in line]
    else:
        counts = [len(line.split(candidate)) for line in lines if candidate in line]
    if not counts:
        return 0, 0
    winner = max(set(counts), key=counts.count)
    return winner, counts.count(winner)


def _pick_delimiter(lines):
    """The separator that carves most of the lines into the same column count.

    Majority rather than unanimity: a country or school name sitting above the
    table has none of these characters in it, and one such line should not rule
    out the separator the rest of the paste is built on.
    """
    needed = max(2, (len(lines) + 1) // 2)
    best, best_columns = None, 1

    for candidate in SPLIT_CANDIDATES:
        columns, agreeing = _majority_columns(lines, candidate)
        if columns > best_columns and agreeing >= needed:
            best, best_columns = candidate, columns
    if best:
        return best

    # A comma is punctuation as often as it is a separator, so it only counts
    # when most lines break into the same three or more columns.
    columns, agreeing = _majority_columns(lines, ",")
    if columns >= 3 and agreeing >= needed:
        return ","
    return None


def _split_row(line, delimiter):
    if delimiter is None:
        return [line]
    if delimiter == ",":
        return [cell.strip() for cell in _COMMA_SPLIT.split(line)]
    return [cell.strip() for cell in line.split(delimiter)]


def _map_header(cells):
    """Match a header row's cells to fields. Returns None if it is not a header."""
    mapping = {}
    for index, cell in enumerate(cells):
        lowered = cell.lower().strip()
        if not lowered:
            continue
        for field_name, words in HEADER_KEYWORDS:
            if field_name in mapping.values():
                continue
            if any(word == lowered or word in lowered for word in words):
                mapping[index] = field_name
                break
    # One matching word is a coincidence; two is a header.
    if len(mapping) >= 2 and "name" in mapping.values():
        return mapping
    return None


# ── Building a course from a row ─────────────────────────────────────


def _course_from_mapped(cells, mapping):
    course = ParsedCourse()
    leftovers = []

    for index, cell in enumerate(cells):
        cell = _clean(cell)
        if not cell:
            continue
        target = mapping.get(index)
        if target is None:
            leftovers.append(cell)
            continue
        if target == "tuition":
            amount, _ = parse_money(cell)
            course.tuition = amount
        elif target == "level":
            course.level = detect_level(cell)
        else:
            setattr(course, target, cell)

    if leftovers:
        course.note = " · ".join(filter(None, [course.note, *leftovers]))
    if course.level == "other":
        course.level = detect_level(course.name, course.qualification_level)
    return course


def _course_from_freeform(cells):
    """Work out what each cell is when there is no header to go by."""
    course = ParsedCourse()
    cells = [_clean(cell) for cell in cells if _clean(cell)]
    if not cells:
        return None

    course.name = cells[0]
    leftovers = []

    for cell in cells[1:]:
        if not course.duration and _looks_like_duration(cell) and not _looks_like_money(cell):
            course.duration = cell
            continue
        if not course.qualification_level and QUALIFICATION_RE.search(cell):
            course.qualification_level = cell
            continue
        if course.tuition is None and _looks_like_money(cell):
            amount, _ = parse_money(cell)
            if amount is not None:
                course.tuition = amount
                continue
        if not course.intake and _looks_like_intake(cell):
            course.intake = cell
            continue
        if not course.scholarship and "scholarship" in cell.lower():
            course.scholarship = cell
            continue
        leftovers.append(cell)

    # A single cell often carries everything: "Master in AI – 1 year – €9,900".
    if len(cells) == 1:
        _enrich_from_name(course)

    if leftovers:
        course.note = " · ".join(leftovers)

    course.level = detect_level(course.name, course.qualification_level)
    return course


def _enrich_from_name(course):
    """Pull a duration, a qualification and an amount out of a single string.

    Whatever is recognised is taken off the course name, so the name left behind
    is the name and not the whole line.
    """
    text = course.name

    qualification = QUALIFICATION_RE.search(text)
    if qualification:
        course.qualification_level = _clean(qualification.group(0))
        text = text.replace(qualification.group(0), " ")

    duration = DURATION_RE.search(text)
    if duration:
        course.duration = _clean(duration.group(0))
        text = text.replace(duration.group(0), " ")

    money = MONEY_RE.search(text) if _looks_like_amount(text) else None
    if money:
        amount, _ = parse_money(money.group(0))
        if amount is not None:
            course.tuition = amount
            text = text.replace(money.group(0), " ")

    course.name = _clean(text)


# ── The entry point ──────────────────────────────────────────────────


def parse_paste(text, known_countries=()):
    """Read a pasted block into a country, a school and a list of courses.

    `known_countries` are the destination names already on file, which lets a
    bare line such as "Spain" be recognised as the country rather than taken for
    a course.
    """
    result = ParsedPaste()
    if not text or not text.strip():
        result.warnings.append("Nothing was pasted.")
        return result

    known = {name.lower(): name for name in known_countries}
    lines = []

    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue

        labelled = False
        for target, pattern in LABEL_PATTERNS.items():
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                value = _clean(match.group(1))
                if target == "application_fee":
                    amount, currency = parse_money(value)
                    result.application_fee = amount
                    if currency and not result.currency:
                        result.currency = currency
                elif target == "currency":
                    result.currency = value.upper()[:8]
                else:
                    setattr(result, target, value)
                labelled = True
                break
        if labelled:
            continue

        lines.append(line)

    # A bare country or school name above the list applies to everything below.
    while lines:
        head = lines[0]
        if not result.country and head.lower() in known:
            result.country = known[head.lower()]
            lines.pop(0)
            continue
        if not result.school and _looks_like_school(head):
            name, _, city = head.partition(",")
            result.school = _clean(name)
            if city and not result.location:
                result.location = _clean(city)
            lines.pop(0)
            continue
        break

    if not lines:
        result.warnings.append("No course lines were found in the paste.")
        return result

    delimiter = _pick_delimiter(lines)
    rows = [_split_row(line, delimiter) for line in lines]

    mapping = _map_header(rows[0]) if delimiter else None
    if mapping:
        rows = rows[1:]

    for row in rows:
        course = _course_from_mapped(row, mapping) if mapping else _course_from_freeform(row)
        if course is None or not course.name:
            continue
        # A row that is really a section heading, such as a level name on its
        # own, carries nothing else and should not become a course.
        if len(row) == 1 and not any(
            [course.duration, course.qualification_level, course.tuition, course.intake]
        ):
            if _looks_like_school(course.name) and not result.school:
                result.school = course.name
                continue
            if course.name.lower() in known and not result.country:
                result.country = known[course.name.lower()]
                continue
        course.name = course.name[:250]
        result.courses.append(course)

    if not result.courses:
        result.warnings.append("No courses could be read from the paste.")
    if not result.country:
        result.warnings.append("The country was not named in the paste, so choose one below.")
    if not result.school:
        result.warnings.append("The school was not named in the paste, so name it below.")
    missing_tuition = sum(1 for course in result.courses if course.tuition is None)
    if missing_tuition:
        result.warnings.append(
            f"{missing_tuition} course(s) came through without a tuition figure. "
            "Fill them in below or leave them to show as on request."
        )

    return result
