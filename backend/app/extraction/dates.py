"""
Turning resume date text into numbers, and computing years of experience.

Done in code, not by the LLM: small models are unreliable at date arithmetic
("Jul 2019 - Dec 2020 plus 03/2022 - Present = ?"), while code is exact and testable.
"""
import re
from dataclasses import dataclass
from datetime import date

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
PRESENT_WORDS = {"present", "current", "currently", "now", "today", "till date", "to date", "ongoing"}

_YEAR_MONTH = re.compile(r"\b(\d{4})[-/.](\d{1,2})\b")          # 2021-06, 2021/6
_MONTH_YEAR_NUM = re.compile(r"\b(\d{1,2})[-/.](\d{4})\b")      # 06/2021, 6-2021
_MONTH_NAME_YEAR = re.compile(r"\b([a-z]{3,9})\.?,?\s*'?(\d{4})\b", re.IGNORECASE)  # Jun 2021, June, 2021
_MONTH_NAME_SHORT_YEAR = re.compile(r"\b([a-z]{3,9})\.?\s*'(\d{2})\b", re.IGNORECASE)  # Jan '20, Jan'20
_YEAR = re.compile(r"\b(19[5-9]\d|20\d{2})\b")                   # 1950-2099
_RANGE_SPLIT = re.compile(r"\s+(?:-|–|—|to|until)\s+|\s*[–—]\s*|(?<=\d{4})-(?=\d{4}\b)", re.IGNORECASE)


@dataclass(frozen=True)
class YearMonth:
    year: int
    month: int | None   # None when the resume only gives a year

    def as_date(self) -> date:
        return date(self.year, self.month or 1, 1)


def is_present(text: str | None) -> bool:
    return bool(text) and text.strip().lower().strip(".") in PRESENT_WORDS


def parse_point(text: str | None) -> YearMonth | None:
    """'Jun 2021' / '06/2021' / '2021-06' / '2021' -> YearMonth. Anything unreadable -> None."""
    if not text:
        return None
    t = text.strip().lower()
    if m := _YEAR_MONTH.search(t):
        month = int(m.group(2))
        return YearMonth(int(m.group(1)), month if 1 <= month <= 12 else None)
    if m := _MONTH_YEAR_NUM.search(t):
        month = int(m.group(1))
        return YearMonth(int(m.group(2)), month if 1 <= month <= 12 else None)
    if (m := _MONTH_NAME_YEAR.search(t)) and m.group(1)[:3] in MONTHS:
        key = m.group(1)[:4] if m.group(1).startswith("sept") else m.group(1)[:3]
        return YearMonth(int(m.group(2)), MONTHS[key])
    if (m := _MONTH_NAME_SHORT_YEAR.search(t)) and m.group(1)[:3] in MONTHS:
        return YearMonth(2000 + int(m.group(2)), MONTHS[m.group(1)[:3]])
    if m := _YEAR.search(t):
        return YearMonth(int(m.group(1)), None)
    return None


def parse_range(start: str | None, end: str | None) -> tuple[YearMonth | None, YearMonth | None, bool]:
    """
    Returns (start, end, is_current). end is None when the job is ongoing.
    Also handles an LLM putting the whole range in 'start' ("Jun 2021 – Present").
    """
    if start and not end:
        parts = _RANGE_SPLIT.split(start.strip(), maxsplit=1)
        if len(parts) == 2:
            start, end = parts
    current = is_present(end)
    return parse_point(start), (None if current else parse_point(end)), current


def _month_index(ym: YearMonth, is_start: bool) -> int:
    # Year-only dates: assume mid-year (July for a start, June for an end) so "2018 - 2020" = 2 years.
    month = ym.month or (7 if is_start else 6)
    return ym.year * 12 + (month - 1)


def interval(start: YearMonth | None, end: YearMonth | None, current: bool, today: date) -> tuple[int, int] | None:
    """A job as (first month index, last month index), or None if the dates can't be used."""
    if start is None:
        return None
    first = _month_index(start, is_start=True)
    last = today.year * 12 + (today.month - 1) if current or end is None else _month_index(end, is_start=False)
    if last < first:
        return None          # e.g. a typo like "2021 - 2019"
    return first, last


def total_months(intervals: list[tuple[int, int]]) -> int:
    """Sum of months covered, counting overlapping jobs only once ("merging intervals")."""
    merged: list[list[int]] = []
    for first, last in sorted(intervals):
        if merged and first <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    return sum(last - first + 1 for first, last in merged)


def months_to_years(months: int) -> float:
    return round(months / 12, 1)
