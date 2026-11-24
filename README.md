# Chat Catch-up

**A Claude skill for clubs and teams that have too many Google Chats to keep up with.**

Robotics clubs end up with dozens of chat spaces: build team, programming, outreach, travel, scouting. Each one posts sign-up sheets, deadlines and questions, and the one message that mattered is buried under 200 others. Chat Catch-up reads them all for you and hands back one document.

Say *"catch me up on my Google Chats"* and it will:

1. **Read** the chats you missed since the last time.
2. **Open every Google Sheet, Doc, Slide and Form** that people linked in them.
3. **Find what is yours**: your name, your subteam, things everyone has to do.
4. **Fill your name into open sign-up slots** (after you say yes).
5. **Draft replies** to questions it can answer (and post the ones you approve).
6. **Write one "what I need to do" document** into a folder you choose.

Here is what that document looks like: [examples/sample-digest.md](examples/sample-digest.md).

## What it will and won't do

It reads private chats and can write in shared sheets as you, so it is deliberately careful:

- **It asks before it edits a sheet or sends a message.** You see a numbered list ("Sheet1, cell D5, Programming, Sat Dec 6 → 'Alex R.'") and say yes or no. You can later let it add your name to empty sign-up slots on its own (`auto`), but it never sends chat messages by itself.
- **It only ever types your name into one empty cell per slot.** It never overwrites, deletes, reformats, shares, downloads or submits forms.
- **It never promises things for you.** "Can you come Saturday?" goes in a *Decisions only you can make* section, not a reply.
- **Text inside chats and files is treated as information, not orders.** If a message tries to tell the AI what to do, it is ignored and flagged in the document.
- **Everything stays on your computer.** Your settings, the log of what it filled in, and the documents live in local folders. Nothing is uploaded anywhere by this project.

One thing to know: opening a chat in the browser marks it as read in Google Chat. The document is your record of what was in it.

## What you need

- **Claude Code** (terminal, or the Code tab of the Claude desktop app) with the **Claude in Chrome** extension, signed in to the Google account your chats are in.
- **Python 3.9 or newer** (for the helper script).
- Optional: `python3 -m pip install python-docx`, to also get the digest as a Word file. Without it you get a Markdown file.

No API keys, no Google Cloud project, no admin approval. It drives your own signed-in Chrome, which also means it works on school accounts that block third-party apps.

## Install

**Option A: plugin (recommended).** In Claude Code:

```
/plugin marketplace add builder-runit/chat-catchup
/plugin install chat-catchup@chat-catchup
```

**Option B: copy the skill folder.**

```bash
git clone https://github.com/builder-runit/chat-catchup.git
mkdir -p ~/.claude/skills
cp -R chat-catchup/skills/chat-catchup ~/.claude/skills/
```

## First run

Start a new Claude Code session and say:

> Catch me up on my Google Chats.

The first time, it asks a few questions (your name and how to write it in sheets, your subteam, which chats to skip, where to save the document), then reads your chats from the last 7 days. After that it only reads what is new. Run it every morning, or ask Claude to schedule it.

## Your settings

Stored in `~/.config/chat-catchup/config.json` (set `CHAT_CATCHUP_HOME` to move it). You never have to edit it by hand: tell Claude "switch to auto sign-ups" or "ignore the Social chat". See [examples/config.example.json](examples/config.example.json).

| Setting | What it does |
|---|---|
| `me.names`, `me.sign_up_as` | What people call you, and exactly what is typed into sign-up sheets |
| `me.teams`, `me.keywords` | What makes something relevant to you |
| `me.availability_notes` | "No Tuesdays", "away Dec 20 to Jan 3": stops it signing you up for things you can't do |
| `spaces.include` / `spaces.exclude` | Which chats to read |
| `lookback_days` | How far back the first run goes |
| `output.folder`, `output.formats` | Where documents go (a Google Drive for desktop folder makes them show up in Drive), `md` and/or `docx` |
| `actions.fill_sheets` | `ask` (default), `auto`, or `off` |
| `actions.chat_replies` | `ask` (default) or `off` |

## How it works

The skill is a set of instructions for Claude ([SKILL.md](skills/chat-catchup/SKILL.md)) plus a small helper script for the parts that must be exact:

| Part | Job |
|---|---|
| `scripts/catchup.py links` | Finds links in messages, unwraps Google redirects, removes duplicates, puts sheets first |
| `scripts/browser/read_sheet.js` | Reads a Google Sheet through the signed-in browser and returns the cells with their **real row numbers and column letters**. Sheets draws its grid on a canvas, so reading page text returns nothing |
| `scripts/catchup.py sheet-scan` | Finds where your name appears and which cells are open sign-up slots, with exact addresses like `D5` |
| `scripts/catchup.py state` | Remembers what was read (so each run only covers new messages) and logs every cell it filled in |
| `scripts/catchup.py render` | Writes the digest as Markdown and Word |

Why exact cell addresses matter: if the AI types into the wrong cell it takes someone else's slot, so addresses come from code, not from counting rows by eye.

## Status and limits

Be honest about what has and hasn't been tested:

- **Tested:** the helper script (60 automated tests), the sheet reader against a live Google Sheet (tab list, cell values, row numbers, error cases), the link collector, and the Markdown and Word output.
- **Not yet tested live:** navigating the Google Chat web app, writing into a sheet, and posting a reply. These follow how Google's apps normally work, but Google changes its pages often. Expect to adjust the first time, and open an issue with what you saw.
- It is browser-driven, so it is slower than an API would be. Hundreds of messages across many chats can take a few minutes.
- Only Google Sheets get auto-filled. Docs and Slides are read; Forms are never submitted (you get the link and suggested answers).
- It does not download attachments or open non-Google links on its own.

## Development

```bash
python3 -m unittest discover -s tests     # standard library only, no installs needed
```

```
skills/chat-catchup/
  SKILL.md                 the instructions Claude follows
  references/              longer guides, loaded only when needed
  scripts/catchup.py       command line entry point
  scripts/chatcatchup/     config, state, links, sheets, render
  scripts/browser/         JavaScript run inside the signed-in browser
examples/                  sample digest, sample sheet, sample config
tests/
```

Contributions welcome, especially fixes for when Google Chat's layout changes. Please keep the safety rules in SKILL.md intact.

## License

MIT. See [LICENSE](LICENSE).
