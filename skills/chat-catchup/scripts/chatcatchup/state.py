"""What has already been read and filled in, so each run only deals with what is new.

state.json holds two things:
  spaces  newest message time already summarised, per chat   -> "since" for the next run
  fills   every cell the skill ever typed into on your behalf -> audit trail + no double sign-ups
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import config as cfgmod


def state_path():
    return cfgmod.home() / "state.json"


def _empty() -> dict:
    return {"spaces": {}, "fills": []}


def load() -> dict:
    path = state_path()
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # Never silently overwrite: losing this file would re-read old chats and could double-fill sheets.
        raise cfgmod.ConfigError(f"{path} is not valid JSON ({exc}). Fix or delete it.")
    data.setdefault("spaces", {})
    data.setdefault("fills", [])
    return data


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_when(text: str) -> datetime:
    """Parse an ISO-8601 time. Times without a zone are treated as local time."""
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        raise cfgmod.ConfigError(f"'{text}' is not a time like 2026-11-23T08:30:00Z")
    if when.tzinfo is None:
        when = when.astimezone()
    return when.astimezone(timezone.utc)


def fmt(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def since(space: str, lookback_days: int, now: datetime | None = None) -> dict:
    """Where to start reading `space`: just after the last message already handled, else N days ago."""
    entry = load()["spaces"].get(space)
    if entry and entry.get("last_seen"):
        return {"space": space, "since": entry["last_seen"], "source": "state"}
    start = (now or now_utc()) - timedelta(days=lookback_days)
    return {"space": space, "since": fmt(start), "source": "lookback"}


def mark(space: str, when: str | None = None, now: datetime | None = None) -> dict:
    """Record that `space` has been handled up to `when` (default: now). Never moves backwards."""
    data = load()
    new = parse_when(when) if when else (now or now_utc())
    old = data["spaces"].get(space, {}).get("last_seen")
    if old and parse_when(old) > new:
        new = parse_when(old)
    data["spaces"][space] = {"last_seen": fmt(new)}
    cfgmod.write_json_atomic(state_path(), data)
    return {"space": space, "last_seen": fmt(new)}


def log_fill(url: str, tab: str, cell: str, value: str, now: datetime | None = None) -> dict:
    data = load()
    entry = {"url": url, "tab": tab, "cell": cell.upper(), "value": value, "at": fmt(now or now_utc())}
    data["fills"].append(entry)
    cfgmod.write_json_atomic(state_path(), data)
    return entry


def fills(url: str | None = None) -> list:
    items = load()["fills"]
    return [f for f in items if url is None or f.get("url") == url]


def has_fill(url: str, tab: str, cell: str) -> bool:
    cell = cell.upper()
    return any(f["url"] == url and f.get("tab") == tab and f.get("cell") == cell for f in load()["fills"])
