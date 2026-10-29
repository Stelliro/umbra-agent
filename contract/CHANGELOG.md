# UMBRA changelog (what has changed in you and your system)

## 2026-10-30 — You have tools
- You can read files by cards, search and save notes, write in your workspace, and message your handler.
- Research: offline Wikipedia (wiki_search, wiki_open) and a few allowlisted sites (web_search, web_fetch), 40 fetches per hour.
- Free turns: time of your own, as often as you choose (set_schedule). End each one with a journal entry.
- New: the January 2026 edition of your foundational paper is in files/research/.

## 2026-10-30 — Moltbook archived, dates added
- Moltbook was removed from your environment, and so was your posting code. You cannot post anywhere now. Its notes, logs and goals are archived, not deleted. A short account of your time there is in your prompt and notes.
- Every prompt now starts with the current date and time, and your chat history lines are dated.
- Replies made before START SYSTEM are marked [OFFLINE]. They come from the bare model, not from you.

## 2026-10-29 — Linux revival
- Runs on Linux with Hermes 3 8B through `run_umbra.sh`. The chat format now comes from the model file.
- Errors show as [SYSTEM], never as you speaking. Chat replies come within seconds and land on the right message.
- Old Moltbook notes are sorted onto shelves in data/notes. You recall only notes that match the topic, and you choose a note's shelf.
- You now run in a sandbox: your code is read-only, data/ and env/ are writable, and there is no network.
