"""Turn the digest (a JSON object Claude builds) into a document you can open anywhere.

Both formats come from one list of "blocks", so the Markdown and the Word file always say the
same thing. See references/digest-format.md for the JSON shape.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

STATUS_LABEL = {
    "filled": "Filled in for you",
    "proposed": "Waiting for your OK",
    "already_listed": "You're already on it",
    "skipped": "Skipped",
}
REPLY_LABEL = {"proposed": "Draft - not sent", "sent": "Sent", "skipped": "Skipped"}


def safe_url(value):
    """Only ever link to http(s). Chat content is untrusted, so no javascript: or file: links."""
    return value if isinstance(value, str) and re.match(r"^https?://", value.strip(), re.I) else None


def _s(value) -> str:
    return "" if value is None else str(value).strip()


def _items(value) -> list:
    return [v for v in (value or []) if isinstance(v, dict)]


def _sort_key(entry: dict, date_field: str):
    when = _s(entry.get(date_field))
    return (0, when) if re.match(r"^\d{4}-\d{2}-\d{2}", when) else (1, when)


def build_blocks(d: dict) -> list:
    """Block tuples: (kind, text, url, extra). kind: title meta h2 h3 para bullet check quote."""
    blocks = []
    blocks.append(("title", _s(d.get("title")) or f"Chat Catch-up - {date.today().isoformat()}", None, None))

    period = d.get("period") or {}
    meta = []
    if period.get("from") or period.get("to"):
        meta.append(f"Covers {_s(period.get('from')) or '?'} to {_s(period.get('to')) or '?'}")
    if d.get("generated_at"):
        meta.append(f"Written {_s(d['generated_at'])}")
    if meta:
        blocks.append(("meta", " | ".join(meta), None, None))

    if d.get("tldr"):
        blocks.append(("h2", "The short version", None, None))
        blocks += [("bullet", _s(t), None, None) for t in d["tldr"] if _s(t)]

    actions = sorted(_items(d.get("action_items")), key=lambda a: (a.get("status") == "done", _sort_key(a, "due")))
    if actions:
        blocks.append(("h2", "What you need to do", None, None))
        for a in actions:
            text = _s(a.get("task"))
            if _s(a.get("due")):
                text += f" - due {_s(a['due'])}"
            if _s(a.get("space")):
                text += f" ({_s(a['space'])})"
            blocks.append(("check", text, safe_url(a.get("link")), (a.get("status") == "done", _s(a.get("why")))))

    decisions = _items(d.get("decisions_needed"))
    if decisions:
        blocks.append(("h2", "Decisions only you can make", None, None))
        for x in decisions:
            where = f" ({_s(x['space'])})" if _s(x.get("space")) else ""
            blocks.append(("bullet", _s(x.get("question")) + where, safe_url(x.get("link")), _s(x.get("why"))))

    signups = _items(d.get("signups"))
    if signups:
        blocks.append(("h2", "Sign-ups", None, None))
        for s in signups:
            label = STATUS_LABEL.get(_s(s.get("status")), _s(s.get("status")))
            where = " ".join(p for p in (_s(s.get("tab")), _s(s.get("cell"))) if p)
            text = f"{label}: {_s(s.get('what'))}"
            if _s(s.get("sheet")):
                text += f" - {_s(s['sheet'])}"
            if where:
                text += f" [{where}]"
            if _s(s.get("value")):
                text += f" as \"{_s(s['value'])}\""
            blocks.append(("bullet", text, safe_url(s.get("url")), _s(s.get("note"))))

    dates = sorted(_items(d.get("dates")), key=lambda x: _sort_key(x, "when"))
    if dates:
        blocks.append(("h2", "Coming up", None, None))
        for x in dates:
            space = f" ({_s(x['space'])})" if _s(x.get("space")) else ""
            blocks.append(("bullet", f"{_s(x.get('when'))}: {_s(x.get('what'))}{space}", safe_url(x.get("link")), None))

    replies = _items(d.get("suggested_replies"))
    if replies:
        blocks.append(("h2", "Replies", None, None))
        for r in replies:
            label = REPLY_LABEL.get(_s(r.get("status")), "Draft - not sent")
            to = f" - replying to: {_s(r['in_reply_to'])}" if _s(r.get("in_reply_to")) else ""
            blocks.append(("h3", f"{_s(r.get('space'))} ({label}){to}", None, None))
            blocks.append(("quote", _s(r.get("draft")), None, None))

    spaces = _items(d.get("spaces"))
    if spaces:
        blocks.append(("h2", "Chat by chat", None, None))
        for sp in spaces:
            unread = f" ({_s(sp['unread'])} new)" if _s(sp.get("unread")) else ""
            blocks.append(("h3", _s(sp.get("name")) + unread, None, None))
            if _s(sp.get("summary")):
                blocks.append(("para", _s(sp["summary"]), None, None))
            blocks += [("bullet", _s(h), None, None) for h in sp.get("highlights", []) if _s(h)]
            for link in _items(sp.get("links")):
                kind = f"[{_s(link['kind'])}] " if _s(link.get("kind")) else ""
                title = _s(link.get("title")) or _s(link.get("url"))
                blocks.append(("bullet", f"{kind}{title}", safe_url(link.get("url")), _s(link.get("note"))))

    skipped = _items(d.get("skipped"))
    if skipped:
        blocks.append(("h2", "Couldn't check", None, None))
        blocks += [("bullet", f"{_s(x.get('space') or x.get('what'))}: {_s(x.get('reason'))}", safe_url(x.get("url")), None) for x in skipped]

    if d.get("notes"):
        blocks.append(("h2", "Notes", None, None))
        blocks += [("bullet", _s(n), None, None) for n in d["notes"] if _s(n)]
    return blocks


def blocks_to_md(blocks: list) -> str:
    lines = []
    for kind, text, url, extra in blocks:
        link = f" ([open]({url}))" if url else ""
        if kind == "title":
            lines += [f"# {text}", ""]
        elif kind == "meta":
            lines += [f"_{text}_", ""]
        elif kind == "h2":
            lines += ["", f"## {text}", ""]
        elif kind == "h3":
            lines += ["", f"### {text}", ""]
        elif kind == "para":
            lines += [text, ""]
        elif kind == "quote":
            lines += [f"> {t}" for t in text.splitlines() or [""]] + [""]
        elif kind == "bullet":
            lines.append(f"- {text}{link}")
            if extra:
                lines.append(f"  _{extra}_")
        elif kind == "check":
            done, why = extra or (False, "")
            lines.append(f"- [{'x' if done else ' '}] {text}{link}")
            if why:
                lines.append(f"  _{why}_")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def _add_hyperlink(paragraph, url: str, text: str) -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    rel_id = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    props.append(underline)
    props.append(color)
    run.append(props)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def blocks_to_docx(blocks: list, path: Path) -> None:
    import docx  # raises ImportError if python-docx is missing; caller handles it

    document = docx.Document()
    for kind, text, url, extra in blocks:
        if kind == "title":
            document.add_heading(text, level=0)
            continue
        if kind in ("h2", "h3"):
            document.add_heading(text, level=1 if kind == "h2" else 2)
            continue
        if kind == "meta":
            document.add_paragraph().add_run(text).italic = True
            continue
        style = {"bullet": "List Bullet", "check": "List Bullet", "quote": "Quote"}.get(kind)
        paragraph = document.add_paragraph(style=style)
        note = ""
        if kind == "check":
            done, note = extra or (False, "")
            text = ("☑ " if done else "☐ ") + text
        elif kind == "bullet":
            note = extra or ""
        paragraph.add_run(text)
        if url:
            paragraph.add_run(" (")
            _add_hyperlink(paragraph, url, "open")
            paragraph.add_run(")")
        if note:
            paragraph.add_run("\n")
            paragraph.add_run(note).italic = True
    document.save(str(path))


def _free_stem(folder: Path, base: str, formats) -> str:
    n = 1
    while True:
        stem = base if n == 1 else f"{base} ({n})"
        if not any((folder / f"{stem}.{fmt}").exists() for fmt in formats):
            return stem
        n += 1


def write_outputs(digest: dict, out_dir: Path, formats, today: date | None = None) -> dict:
    """Write the digest in each format. Never overwrites an earlier digest."""
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    blocks = build_blocks(digest)
    stem = _free_stem(out_dir, f"Chat Catch-up {(today or date.today()).isoformat()}", formats)
    written, warnings = [], []
    for fmt in formats:
        path = out_dir / f"{stem}.{fmt}"
        if fmt == "md":
            path.write_text(blocks_to_md(blocks), encoding="utf-8")
            written.append(str(path))
        elif fmt == "docx":
            try:
                blocks_to_docx(blocks, path)
                written.append(str(path))
            except ImportError:
                warnings.append("Skipped the Word file: run `python3 -m pip install python-docx` to enable it.")
        else:
            warnings.append(f"Unknown format '{fmt}' skipped.")
    return {"written": written, "warnings": warnings}
