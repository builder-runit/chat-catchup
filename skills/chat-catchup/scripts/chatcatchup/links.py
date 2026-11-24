"""Find the links in chat messages and say what each one is.

Chats hide links in several ways (Google wraps them in google.com/url?q=... redirects, trailing
punctuation sticks to them, the same sheet is posted ten times). This module turns a pile of
messages into a short, de-duplicated, prioritised list of things worth opening.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

URL_RE = re.compile(r"https?://[^\s<>\"'“”‘’]+", re.IGNORECASE)
_TRAILING = ".,;:!?]}>"

_GOOGLE_FILE_RE = re.compile(
    r"^/(?P<product>spreadsheets|document|presentation|forms)(?:/u/\d+)?/d/(?P<pub>e/)?(?P<id>[\w-]+)"
)
_DRIVE_FILE_RE = re.compile(r"^/(?:drive/)?(?:u/\d+/)?file/d/(?P<id>[\w-]+)")
_DRIVE_FOLDER_RE = re.compile(r"/folders/(?P<id>[\w-]+)")

# Lower number = open first. Sheets first: that is where sign-ups and assignments live.
PRIORITY = {
    "gsheet": 0, "gform": 1, "gdoc": 2, "gslides": 3, "gdrive_folder": 4, "gdrive_file": 5,
    "gcalendar": 6, "gsite": 7, "gmeet": 8, "gchat": 9, "external": 10,
}
READABLE = {"gsheet", "gdoc", "gslides", "gform"}


def unwrap(url: str) -> str:
    """Undo google.com/url?q=<real link> redirect wrappers (can be nested)."""
    for _ in range(3):
        parts = urlparse(url)
        if parts.netloc.lower() in ("www.google.com", "google.com") and parts.path == "/url":
            query = parse_qs(parts.query)
            target = next((query[k][0] for k in ("q", "url") if k in query), "")
            if target.lower().startswith(("http://", "https://")):
                url = target
                continue
        break
    return url


def extract_urls(text: str) -> list:
    """All http(s) URLs in `text`, in order, with sentence punctuation removed."""
    urls = []
    for match in URL_RE.finditer(text or ""):
        url = match.group(0)
        while url and (url[-1] in _TRAILING or (url[-1] == ")" and "(" not in url)):
            url = url[:-1]
        if url:
            urls.append(url)
    return urls


def _gid(parts) -> str | None:
    for source in (parts.query, parts.fragment):
        found = parse_qs(source).get("gid")
        if found:
            return found[0]
    return None


def classify(url: str) -> dict:
    """Describe one link: kind, id, whether Claude can read it, and how."""
    url = unwrap(url)
    parts = urlparse(url)
    host = parts.netloc.lower().removeprefix("www.")
    info = {"url": url, "kind": "external", "domain": host, "readable": False}

    if host == "docs.google.com":
        match = _GOOGLE_FILE_RE.match(parts.path)
        if match:
            product, file_id, published = match.group("product"), match.group("id"), bool(match.group("pub"))
            info["id"] = file_id
            if product == "spreadsheets":
                gid = _gid(parts)
                info.update(kind="gsheet", gid=gid, published=published)
            elif product == "document":
                info["kind"] = "gdoc"
            elif product == "presentation":
                info["kind"] = "gslides"
            else:
                info["kind"] = "gform"
    elif host == "forms.gle":
        info.update(kind="gform", id=parts.path.strip("/"))
    elif host == "drive.google.com":
        folder = _DRIVE_FOLDER_RE.search(parts.path)
        file_ = _DRIVE_FILE_RE.match(parts.path)
        opened = parse_qs(parts.query).get("id")
        if folder:
            info.update(kind="gdrive_folder", id=folder.group("id"))
        elif file_:
            info.update(kind="gdrive_file", id=file_.group("id"))
        elif opened:
            info.update(kind="gdrive_file", id=opened[0])
    elif host in ("calendar.google.com", "calendar.app.google"):
        info["kind"] = "gcalendar"
    elif host == "meet.google.com":
        info["kind"] = "gmeet"
    elif host == "chat.google.com" or (host == "mail.google.com" and parts.path.startswith("/chat")):
        info["kind"] = "gchat"
    elif host == "sites.google.com":
        info["kind"] = "gsite"

    info["readable"] = info["kind"] in READABLE
    return info


def _key(info: dict):
    if info.get("id"):
        return (info["kind"], info["id"], info.get("gid"))
    return (info["kind"], info["url"])


def collect(messages: list) -> list:
    """Messages -> unique links, sheets first. Each message: {text, links?, space?, sender?, time?}.

    `links` carries the real hrefs read from the page, because page text drops them.
    """
    found: dict = {}
    for message in messages:
        if not isinstance(message, dict):
            continue
        blob = " ".join([str(message.get("text", ""))] + [str(u) for u in message.get("links", [])])
        source = {k: message[k] for k in ("space", "sender", "time") if message.get(k)}
        for raw in extract_urls(blob):
            info = classify(raw)
            entry = found.setdefault(_key(info), {**info, "sources": []})
            if source and source not in entry["sources"]:
                entry["sources"].append(source)
    return sorted(found.values(), key=lambda e: PRIORITY.get(e["kind"], 99))
