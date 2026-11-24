"""Your settings: who you are, where digests go, and what Claude is allowed to do.

Everything lives in one folder on *your own computer* (never in the repo):

    ~/.config/chat-catchup/config.json   your settings
    ~/.config/chat-catchup/state.json    what has been read and filled in so far

Set CHAT_CATCHUP_HOME to use a different folder.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

FILL_MODES = ("ask", "auto", "off")
REPLY_MODES = ("ask", "off")
FORMATS = ("md", "docx")

DEFAULTS = {
    "me": {
        # Names people use for you in chats and sheets. The first one is your main name.
        "names": [],
        # Exactly what gets typed into sign-up sheets, e.g. "Alex R."
        "sign_up_as": "",
        "email": "",
        # Subteams / roles that make a message relevant to you, e.g. ["Programming", "Drive team"]
        "teams": [],
        # Anything else that should always get your attention, e.g. ["Saturday build", "regionals"]
        "keywords": [],
        # Free text Claude uses before it signs you up for anything, e.g. "No Tuesdays. Away Dec 20-Jan 3."
        "availability_notes": "",
    },
    # The Google account your club chats live in (helps when several accounts are signed in).
    "google_account": "",
    "spaces": {"include": [], "exclude": []},
    "lookback_days": 7,
    "max_files_per_run": 40,
    "output": {"folder": "~/Documents/Chat Catchup", "formats": ["md", "docx"]},
    "actions": {
        # ask  = list every sheet edit and wait for a yes (default)
        # auto = only add your name to an empty slot on a sheet that is clearly a sign-up for you
        # off  = never edit sheets
        "fill_sheets": "ask",
        # ask = draft replies and post only the ones you approve (default); off = never reply
        "chat_replies": "ask",
    },
}


class ConfigError(Exception):
    """A problem the user can fix; the message says how."""


def home() -> Path:
    env = os.environ.get("CHAT_CATCHUP_HOME")
    return Path(env).expanduser() if env else Path.home() / ".config" / "chat-catchup"


def config_path() -> Path:
    return home() / "config.json"


def write_json_atomic(path: Path, data) -> None:
    """Write JSON so a crash never leaves a half-written file. Files are private (0600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = copy.deepcopy(base)
        for key, value in over.items():
            out[key] = _merge(base[key], value) if key in base else copy.deepcopy(value)
        return out
    return copy.deepcopy(over)


def load() -> dict:
    path = config_path()
    if not path.exists():
        raise ConfigError(
            f"No settings yet ({path}). Run first-time setup: "
            "catchup.py config init --name \"Your Name\""
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid JSON ({exc}). Fix it or delete it and run setup again.")
    return _merge(DEFAULTS, raw)


def save(cfg: dict) -> Path:
    write_json_atomic(config_path(), cfg)
    return config_path()


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def validate(cfg: dict) -> list:
    """Return a list of plain-English problems (empty list = all good)."""
    problems = []
    me = cfg.get("me", {})
    if not any(str(n).strip() for n in me.get("names", [])):
        problems.append("me.names is empty - add at least one name people call you")
    if not str(me.get("sign_up_as", "")).strip():
        problems.append("me.sign_up_as is empty - this is the text typed into sign-up sheets")
    for key in ("names", "teams", "keywords"):
        if not _is_str_list(me.get(key, [])):
            problems.append(f"me.{key} must be a list of text values")
    spaces = cfg.get("spaces", {})
    for key in ("include", "exclude"):
        if not _is_str_list(spaces.get(key, [])):
            problems.append(f"spaces.{key} must be a list of chat names")
    for key in ("lookback_days", "max_files_per_run"):
        value = cfg.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            problems.append(f"{key} must be a whole number of at least 1")
    actions = cfg.get("actions", {})
    if actions.get("fill_sheets") not in FILL_MODES:
        problems.append(f"actions.fill_sheets must be one of {', '.join(FILL_MODES)}")
    if actions.get("chat_replies") not in REPLY_MODES:
        problems.append(f"actions.chat_replies must be one of {', '.join(REPLY_MODES)}")
    formats = cfg.get("output", {}).get("formats", [])
    if not _is_str_list(formats) or not formats or any(f not in FORMATS for f in formats):
        problems.append(f"output.formats must be a non-empty list drawn from {', '.join(FORMATS)}")
    if not str(cfg.get("output", {}).get("folder", "")).strip():
        problems.append("output.folder is empty")
    return problems


def init(names, *, sign_up_as=None, email="", account="", teams=(), keywords=(),
         folder=None, lookback_days=None, force=False) -> dict:
    names = [n.strip() for n in names if n and n.strip()]
    if not names:
        raise ConfigError("Give at least one name, e.g. --name \"Alex\"")
    if config_path().exists() and not force:
        raise ConfigError(f"{config_path()} already exists. Use `config set` to change it, or --force to start over.")
    cfg = copy.deepcopy(DEFAULTS)
    cfg["me"].update(
        names=names,
        sign_up_as=(sign_up_as or names[0]).strip(),
        email=email.strip(),
        teams=[t.strip() for t in teams if t.strip()],
        keywords=[k.strip() for k in keywords if k.strip()],
    )
    cfg["google_account"] = account.strip()
    if folder:
        cfg["output"]["folder"] = folder
    if lookback_days:
        cfg["lookback_days"] = lookback_days
    problems = validate(cfg)
    if problems:
        raise ConfigError("; ".join(problems))
    save(cfg)
    return cfg


def set_value(cfg: dict, dotted: str, raw: str) -> dict:
    """Change one setting, e.g. set_value(cfg, "actions.fill_sheets", "auto"). Validates before returning."""
    parts = dotted.split(".")
    node, default = cfg, DEFAULTS
    for part in parts[:-1]:
        if not isinstance(default, dict) or part not in default:
            raise ConfigError(f"Unknown setting '{dotted}'")
        node, default = node[part], default[part]
    last = parts[-1]
    if not isinstance(default, dict) or last not in default:
        raise ConfigError(f"Unknown setting '{dotted}'")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    node[last] = value
    problems = validate(cfg)
    if problems:
        raise ConfigError("; ".join(problems))
    return cfg


def output_folder(cfg: dict) -> Path:
    return Path(cfg["output"]["folder"]).expanduser()
