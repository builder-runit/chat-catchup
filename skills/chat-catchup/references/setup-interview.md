# First-run setup interview

The first time (when `doctor` says there are no settings, or its hints say the profile is empty), set the user up with this short interview. Do it before reading any chat. The answers decide what gets signed up, what gets ignored and how the digest reads, so a few good questions here save a lot of noise later.

How to run it:
- **Ask in rounds, at most four questions per message.** Use the multiple-choice question tool when the session has one, plain text otherwise. Keep each question to one line plus a short "why".
- **Skip anything the user already told you**, and accept "skip" or "not sure" for any question. Nothing is required except a name.
- **Round 0 comes first and is always asked, even if the user is in a hurry.**
- After the last round, read the answers back in four or five lines ("You are Alex R., a 10th-grade student in Programming. You want outreach hours and drive team. Never food duty. Sign-ups: ask first. Right?") and fix anything wrong.
- Then save it in one command (see the end). Everything is stored only on this computer, in `~/.config/chat-catchup/`.

## Round 0: may it fill in sign-up sheets? (ask this first)

Say it in these words, so nothing is a surprise:

> **Do you want me to fill your name into sign-up slots?** When a chat links a sign-up sheet, I can add you to empty slots. I list each slot first (for example "Sheet1, cell D5, Programming, Sat Dec 6") and ask you. I type only your name, in one empty cell per slot, then re-read the sheet to check it. I keep a log of every cell I fill, so you can undo it.

| Choice | Setting | What it means |
|---|---|---|
| **Yes, ask me first** (recommended) | `--fill-sheets ask` | You see a numbered list of slots and say yes or no. |
| **Yes, automatically when it is clearly for me** | `--fill-sheets auto` | Only empty slots on clear sign-ups that match your team or interests, never anything you said to avoid. Everything is still logged and listed in the digest. |
| **No, just list them in the digest** | `--fill-sheets off` | I never edit a sheet. You do it yourself from the list. |

Then one more: **"Should I draft replies to questions I can answer?"** Yes, and ask before posting (`--chat-replies ask`, default), or never reply (`--chat-replies off`). Never offer a way to send replies without asking.

If they say yes to filling, tell them the first time you fill, you will check the sheet with them.

## Round 1: who you are

- What do people call you in chats and sheets? (name and nicknames) How exactly should your name be written in sign-up sheets, for example "Alex R."? → `--name` (repeat for nicknames), `--sign-up-as`
- Are you a student, a student leader, a mentor, or something else? → `--role`. Why: rules often differ by role (for example hour requirements for leaders), and some messages are only for students or only for mentors.
- What grade or year are you in? → `--grade`. Why: some deadlines, forms and trips depend on it.
- Which Google account are the club chats in? → `--account`. Why: if several accounts are signed in, I must read the right one.

## Round 2: what you do in robotics

- Which subteam or department are you in (build, programming, controls, design, drive, outreach, business/media, electrical, ...)? Any other teams you float between? → `--team` (repeat). Why: messages to those teams count as yours.
- Do you have a job or title (lead, outreach officer, drive coach)? → `--keyword "outreach officer"`. Why: people @mention titles, and tasks follow them.
- What can you do, or want to learn (CAD, Python, machining, scouting, public speaking, driving the robot)? → `--skill` (repeat). Why: lets me point out sign-ups and asks that fit you.
- Which kinds of sign-ups do you WANT? (outreach events, scouting shifts, build days, mentoring, competitions) → `--interest` (repeat). Why: matching slots are listed first and marked.
- Which kinds do you NEVER want, so I should not even offer them (food duty, teardown, early mornings)? → `--avoid` (repeat). Why: matching slots are blocked, never offered or filled.
- What do you want out of this season (for example "18 outreach hours", "make drive team", "learn CAD")? → `--goals`. Why: I check the digest against it and say how far along you are.

## Round 3: your schedule

- Which days or times can you never do (other activities, sports, a job)? Which dates are you away? → `config set me.availability_notes "..."`. Why: I will not sign you up for anything that clashes.
- Can you get yourself to events, or do you need a ride? Does it matter for weekends or off-site events? Add this to the same notes. Why: many sign-ups are off-site.
- How far ahead do you want to hear about things (a day, a week)? Why: sets what I put at the top of the digest as urgent.

## Round 4: chats and output

- Which chats do you always want read in full? Which can I skip (social chats, alumni, other teams)? → `config set spaces.exclude '["Social"]'`, and `spaces.include` only if they want a short list.
- Where should the document go? Default `~/Documents/Chat Catchup`. A folder inside Google Drive for desktop makes it appear in Drive. → `--folder`
- Do you want the full digest (every chat summarised) or the short one (your to-do list, decisions and dates, then one line per chat)? → `--digest-detail full|short`
- Do you also want a Word file, or is Markdown enough? → `config set output.formats '["md"]'`
- Should I run this every morning? If yes, offer to schedule it.

Also tell them: **opening a chat in the browser marks it as read in Google Chat**, so the digest is their record of what was in it.

## Save it

```
python3 scripts/catchup.py config init --name "Alex" --name "Al" --sign-up-as "Alex R." \
  --role student --grade "10th grade" --account you@school.org \
  --team Programming --team "Drive team" --keyword "outreach officer" \
  --skill CAD --skill Python --interest outreach --avoid "food duty" \
  --goals "18 outreach hours, make drive team" \
  --fill-sheets ask --chat-replies ask --digest-detail full --folder "~/Documents/Chat Catchup"
python3 scripts/catchup.py config set me.availability_notes "No Tuesdays. Away Dec 20 to Jan 3."
```

Leave out any flag the user skipped. To change a single answer later: `config set <setting> <value>` (for example `config set actions.fill_sheets auto`, `config set me.interests '["scouting"]'`), or run this interview again with `config init --force` when they say "redo my setup".

## After the first read: ask smart follow-ups

Once you have read the chats, the best questions come from what you actually found. Ask two or three, in the digest conversation, not before:

- "I found sign-ups for A, B and C. Which of these do you want?" Save the answer with `config set me.interests` or `me.avoid`.
- "You are not on the outreach hours list. Is someone supposed to add you?"
- "Chat X is busy and none of it was yours. Should I skip it from now on?" Save with `config set spaces.exclude`.
- "Two events overlap on Saturday. Which one should I plan around?"

Each answer makes the next run more accurate, so say what you saved.
