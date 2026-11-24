"""Look through a sheet for you: where are you mentioned, and where could you sign up?

Input is either
  * the A1 grid that scripts/browser/read_sheet.js prints (first line "#<TAB>A<TAB>B...", each
    following line starts with the real spreadsheet row number), or
  * a plain CSV export (row 1 = first line).

Why the row numbers matter: if Claude ever types into the wrong cell it signs you up in someone
else's slot. So every result here carries its real A1 address (like "B14"), never a guess.
This module only *finds* things. It never edits anything.
"""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass

# Column headers that usually hold people's names.
NAME_COL_RE = re.compile(
    r"\b(names?|who|students?|members?|volunteers?|assigned|assignee|owner|sign[\s-]?ups?|signed|"
    r"attendees?|drivers?|lead|responsible|person|participants?|taking|claimed?|available)\b",
    re.IGNORECASE,
)
_CONTEXT_COLUMNS = 8


@dataclass
class Grid:
    letters: list   # column letters, aligned with every row's cells
    rows: list      # [(sheet row number, [cell text, ...]), ...] in sheet order


def col_letters(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    out, n = "", index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def parse_grid(text: str) -> Grid:
    text = text.lstrip("﻿")
    if text.split("\n", 1)[0].startswith("#\t"):
        return _parse_a1(text)
    return _parse_csv(text)


def _parse_a1(text: str) -> Grid:
    lines = text.rstrip("\n").split("\n")
    letters = [c.strip() for c in lines[0].split("\t")[1:]]
    rows = []
    for line in lines[1:]:
        parts = line.split("\t")
        if not parts[0].strip().isdigit():
            continue
        cells = [c.strip() for c in parts[1:]][: len(letters)]
        cells += [""] * (len(letters) - len(cells))
        rows.append((int(parts[0]), cells))
    return Grid(letters, rows)


def _parse_csv(text: str) -> Grid:
    raw = [[c.strip() for c in row] for row in csv.reader(io.StringIO(text))]
    width = 0
    for row in raw:
        while row and not row[-1]:
            row.pop()
        width = max(width, len(row))
    letters = [col_letters(i) for i in range(width)]
    rows = [(i + 1, row + [""] * (width - len(row))) for i, row in enumerate(raw)]
    return Grid(letters, rows)


def _term_patterns(terms) -> list:
    patterns = []
    for term in terms:
        term = (term or "").strip()
        if len(term) >= 2:
            patterns.append((term, re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)))
    return patterns


def _find_header(rows: list) -> int | None:
    """Index into `rows` of the header row: the first wide-enough row near the top."""
    head = rows[:10]
    counts = [sum(1 for c in cells if c) for _, cells in head]
    if not counts:
        return None
    if max(counts) < 2:
        # One-column sheets (just a list of names) have no wide row; accept a cell that is exactly
        # a name-style header such as "Name" or "Volunteers". A title like "Fall Sign-ups" is not.
        for i, (_, cells) in enumerate(head):
            if any(NAME_COL_RE.fullmatch(c) for c in cells if c):
                return i
        return None
    threshold = max(2, math.ceil(0.6 * max(counts)))
    return next(i for i, n in enumerate(counts) if n >= threshold)


def _context(letters, headers, cells, skip=()) -> dict:
    out = {}
    for i, value in enumerate(cells):
        if value and i not in skip and len(out) < _CONTEXT_COLUMNS:
            out[headers[i] or letters[i]] = value
    return out


def scan(text: str, names, emails=(), teams=(), keywords=(), max_slots: int = 50, interests=(), avoid=()) -> dict:
    grid = parse_grid(text)
    rows = [(n, cells) for n, cells in grid.rows if any(cells)]
    result = {
        "rows_with_data": len(rows), "columns": grid.letters, "header_row": None,
        "name_columns": [], "matches": [], "listed_in_name_column": False,
        "open_slots": [], "open_slot_count": 0, "blocked_slots": [], "append_slots": [], "notes": [],
    }
    if not rows:
        result["notes"].append("The sheet is empty.")
        return result

    header_at = _find_header(rows)
    headers = [""] * len(grid.letters)
    header_row_number = 0
    if header_at is not None:
        header_row_number, headers = rows[header_at][0], list(rows[header_at][1])
        result["header_row"] = header_row_number
    data_rows = [(n, c) for n, c in rows if n > header_row_number]

    name_idx = [i for i, h in enumerate(headers) if h and NAME_COL_RE.search(h)]
    result["name_columns"] = [{"column": grid.letters[i], "header": headers[i]} for i in name_idx]
    if not name_idx:
        result["notes"].append(
            "No name-like column headers found. If this is a grid (days across, roles down) or a free-form "
            "list, read it yourself instead of relying on open_slots."
        )

    # --- where am I mentioned? ---
    groups = [("name", _term_patterns(names)), ("email", _term_patterns(emails)),
              ("team", _term_patterns(teams)), ("keyword", _term_patterns(keywords)),
              ("interest", _term_patterns(interests))]
    for number, cells in rows:
        for i, value in enumerate(cells):
            if not value:
                continue
            matched = {kind: [t for t, p in pats if p.search(value)] for kind, pats in groups}
            matched = {k: v for k, v in matched.items() if v}
            if not matched:
                continue
            cell = f"{grid.letters[i]}{number}"
            result["matches"].append({
                "cell": cell, "text": value, "matched": matched,
                "in_header_row": number == header_row_number,
                "context": _context(grid.letters, headers, cells, skip=(i,)),
            })
            if number > header_row_number and i in name_idx and ("name" in matched or "email" in matched):
                result["listed_in_name_column"] = True

    # --- where could I sign up? ---
    avoid_patterns, interest_patterns = _term_patterns(avoid), _term_patterns(interests)

    def _hits(patterns, context, cells):
        text = " ".join(list(context.values()) + [c for c in cells if c])
        return [t for t, p in patterns if p.search(text)]

    for number, cells in data_rows:
        for i in name_idx:
            if cells[i]:
                continue
            context = _context(grid.letters, headers, cells, skip=name_idx)
            if not context:
                continue  # nothing describes this row, so it is not a slot, just blank space
            cell = f"{grid.letters[i]}{number}"
            blocked_by = _hits(avoid_patterns, context, cells)
            if blocked_by:
                # The user said they never want this kind of thing: report it, never offer it.
                result["blocked_slots"].append({"cell": cell, "column": headers[i], "context": context, "blocked_by": blocked_by})
                continue
            result["open_slot_count"] += 1
            slot = {"cell": cell, "column": headers[i], "context": context}
            wanted = _hits(interest_patterns, context, cells)
            if wanted:
                slot["matches_interest"] = wanted
            result["open_slots"].append(slot)
    # Slots that match what the user wants come first; keep the sheet order otherwise.
    result["open_slots"].sort(key=lambda sl: 0 if sl.get("matches_interest") else 1)
    del result["open_slots"][max_slots:]
    for i in name_idx:
        filled = [n for n, cells in data_rows if cells[i]]
        if filled:
            result["append_slots"].append(
                {"column": grid.letters[i], "header": headers[i], "next_empty_cell": f"{grid.letters[i]}{max(filled) + 1}"}
            )
    return result
