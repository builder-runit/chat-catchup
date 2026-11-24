#!/usr/bin/env python3
"""chat-catchup helper. Claude drives the browser; this script does the exact, repeatable parts.

  catchup.py doctor                         check that everything is set up
  catchup.py config init|show|set|path      your settings
  catchup.py state since|mark|log-fill|fills|show    what was already handled
  catchup.py links --messages msgs.json     find + classify links in chat messages
  catchup.py sheet-scan --file grid.tsv     find your name / open slots in a sheet
  catchup.py render --input digest.json     write the digest document(s)

Everything prints JSON on stdout. Problems print one plain sentence on stderr and exit 1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chatcatchup import __version__, config, links, render, sheets, state  # noqa: E402


def out(data) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def read_text(path: str | None) -> str:
    return Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()


# ---------- commands ----------

def cmd_doctor(args) -> None:
    report = {"version": __version__, "python": sys.version.split()[0], "problems": [], "hints": []}
    if sys.version_info < (3, 9):
        report["problems"].append("Python 3.9 or newer is required")
    try:
        import docx  # noqa: F401
        report["word_files"] = "available"
    except ImportError:
        report["word_files"] = "missing (optional): python3 -m pip install python-docx"
        report["hints"].append("Without python-docx the digest is written as Markdown only.")
    path = config.config_path()
    report["config_path"] = str(path)
    if not path.exists():
        report["problems"].append("No settings yet - run `config init`")
    else:
        try:
            cfg = config.load()
            report["problems"] += config.validate(cfg)
            folder = config.output_folder(cfg)
            report["output_folder"] = str(folder)
            report["output_folder_exists"] = folder.exists()
        except config.ConfigError as exc:
            report["problems"].append(str(exc))
    report["ok"] = not report["problems"]
    out(report)


def cmd_config(args) -> None:
    if args.config_cmd == "path":
        out({"config": str(config.config_path()), "state": str(state.state_path())})
    elif args.config_cmd == "init":
        cfg = config.init(
            args.name, sign_up_as=args.sign_up_as, email=args.email or "", account=args.account or "",
            teams=args.team, keywords=args.keyword, folder=args.folder,
            lookback_days=args.lookback_days, force=args.force,
        )
        out({"saved": str(config.config_path()), "config": cfg})
    elif args.config_cmd == "show":
        cfg = config.load()
        out({"path": str(config.config_path()), "problems": config.validate(cfg), "config": cfg})
    elif args.config_cmd == "set":
        cfg = config.set_value(config.load(), args.key, args.value)
        config.save(cfg)
        out({"saved": str(config.config_path()), args.key: args.value})


def cmd_state(args) -> None:
    if args.state_cmd == "since":
        out(state.since(args.space, config.load()["lookback_days"]))
    elif args.state_cmd == "mark":
        out(state.mark(args.space, args.time))
    elif args.state_cmd == "log-fill":
        out(state.log_fill(args.url, args.tab, args.cell, args.value))
    elif args.state_cmd == "fills":
        out(state.fills(args.url))
    elif args.state_cmd == "show":
        out(state.load())


def cmd_links(args) -> None:
    if args.messages:
        data = json.loads(Path(args.messages).read_text(encoding="utf-8"))
        messages = data["messages"] if isinstance(data, dict) else data
    else:
        messages = [{"text": read_text(args.file)}]
    found = links.collect(messages)
    out({"count": len(found), "links": found})


def cmd_sheet_scan(args) -> None:
    names, email, teams, keywords = list(args.name), args.email or "", [], []
    try:
        me = config.load()["me"]
        names += me["names"]
        email = email or me["email"]
        teams, keywords = me["teams"], me["keywords"]
    except config.ConfigError:
        if not names:
            raise config.ConfigError("No settings yet: run `config init`, or pass --name \"Your Name\"")
    result = sheets.scan(read_text(args.file), names, [email] if email else [], teams, keywords, args.max_slots)
    if args.url:
        result["url"] = args.url
    if args.tab:
        result["tab"] = args.tab
    out(result)


def cmd_render(args) -> None:
    digest = json.loads(read_text(args.input))
    try:
        cfg = config.load()
        folder, formats = config.output_folder(cfg), cfg["output"]["formats"]
    except config.ConfigError:
        folder, formats = Path(config.DEFAULTS["output"]["folder"]).expanduser(), config.DEFAULTS["output"]["formats"]
    if args.out_dir:
        folder = Path(args.out_dir)
    if args.formats:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    out(render.write_outputs(digest, folder, formats))


# ---------- argument parsing ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="catchup.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check setup").set_defaults(func=cmd_doctor)

    c = sub.add_parser("config", help="your settings")
    cs = c.add_subparsers(dest="config_cmd", required=True)
    cs.add_parser("path")
    ci = cs.add_parser("init")
    ci.add_argument("--name", action="append", default=[], required=True, help="a name people call you (repeat for nicknames; first is main)")
    ci.add_argument("--sign-up-as", help="exact text typed into sign-up sheets (default: first name)")
    ci.add_argument("--email")
    ci.add_argument("--account", help="the Google account your club chats live in")
    ci.add_argument("--team", action="append", default=[], help="subteam or role (repeatable)")
    ci.add_argument("--keyword", action="append", default=[], help="always-relevant word or phrase (repeatable)")
    ci.add_argument("--folder", help="where digests are saved")
    ci.add_argument("--lookback-days", type=int)
    ci.add_argument("--force", action="store_true", help="overwrite existing settings")
    cs.add_parser("show")
    cset = cs.add_parser("set")
    cset.add_argument("key", help="dotted name, e.g. actions.fill_sheets")
    cset.add_argument("value", help="text, or JSON for lists, e.g. '[\"Programming\"]'")
    c.set_defaults(func=cmd_config)

    s = sub.add_parser("state", help="what was already handled")
    ss = s.add_subparsers(dest="state_cmd", required=True)
    for name in ("since", "mark"):
        sp = ss.add_parser(name)
        sp.add_argument("--space", required=True)
        if name == "mark":
            sp.add_argument("--time", help="newest message time handled (ISO-8601); default now")
    lf = ss.add_parser("log-fill")
    for flag in ("--url", "--tab", "--cell", "--value"):
        lf.add_argument(flag, required=True)
    fl = ss.add_parser("fills")
    fl.add_argument("--url")
    ss.add_parser("show")
    s.set_defaults(func=cmd_state)

    l = sub.add_parser("links", help="classify links in messages")
    l.add_argument("--messages", help="JSON file: a list of {text, links?, space?, sender?, time?}")
    l.add_argument("--file", help="plain text file (default: read stdin)")
    l.set_defaults(func=cmd_links)

    sc = sub.add_parser("sheet-scan", help="find your name / open slots in a sheet")
    sc.add_argument("--file", help="A1 grid or CSV (default: read stdin)")
    sc.add_argument("--name", action="append", default=[], help="extra name to look for (repeatable)")
    sc.add_argument("--email")
    sc.add_argument("--url")
    sc.add_argument("--tab")
    sc.add_argument("--max-slots", type=int, default=50)
    sc.set_defaults(func=cmd_sheet_scan)

    r = sub.add_parser("render", help="write the digest document(s)")
    r.add_argument("--input", help="digest JSON file (default: read stdin)")
    r.add_argument("--out-dir", help="override the output folder")
    r.add_argument("--formats", help="comma list from: md,docx")
    r.set_defaults(func=cmd_render)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (config.ConfigError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"catchup.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
