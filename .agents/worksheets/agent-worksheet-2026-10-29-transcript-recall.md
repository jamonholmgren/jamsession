# Transcript recall instead of compaction

Status: COMPLETE

## Source and requirements

Jamon, 2026-10-29, after a post arguing that compaction is slow, costly and lossy and that a fresh session should search the old transcript instead:

- "The small seed could simply be the agent worksheet link. Plus, the agent worksheet could contain the link back to each session used to operate on it."
- "Yes build for Jam Session and push to its repo with everything dialed in. Test it with a cheap agent like Devin swe-2 or Luna 6 low or haiku 5.5 low and see how it goes. Don't burn expensive tokens when testing."

Starting commit: c691b1a.

## Decisions

- `run`, `message` and `steer` take `--worksheet <path>` right after the command. Jam Session (not the agent) writes the session id, settings and the exact prompt or message to the worksheet's `## Jam Session log`, so a forgetful agent can't drop the link.
- A run is logged as soon as the adapter prints its `session:` line, so the worksheet names a session while it is still working. A message is logged after delivery, marked with its exit code if delivery failed.
- Prompts past 4000 characters are cut in the log; the transcript keeps the full text.
- `recall` reads each provider's own transcript through `which`, with no model call. It handles JSONL (Claude and Codex with dedicated readers; Grok, Copilot, Muse and Antigravity JSONL generically) and Devin's SQLite database read-only. Cursor and Antigravity SQLite stores report unsupported.
- Claude thinking and Codex encrypted reasoning, token counts and settings events are skipped. Tool calls are printed as `name` then `key: value` lines, so commands are searchable as written.
- A query matches lines containing every word in any order. If nothing matches, recall shows lines with at least half the words. Trials showed cheap models write plain-English queries that a literal phrase search misses.
- The worksheet log is the seed; no separate summary is kept. The 250K session-size hint now points to `run --worksheet` and `recall`.

## Files

`jamsession`, `usage/jamsession_recall.py`, `adapters/_jamsession_adapter_common`, `install.sh`, `README.md`, `tests/test_recall.py`, and the summon-agent, use-agent-worksheet and individual-worker-workflow skills.

## Evidence

- `bash tests/test_jamsession.sh`: 616 passed, 0 failed, run from a copy whose folder is named `jamsession` (the uninstall checks require that name).
- `python3 -m unittest discover -s tests`: all pass, including 8 new recall tests.
- Real transcripts: a ~400K-line Codex session (53,231 entries) searched in about 4 s; Claude and Devin sessions return exact lines.
- Live trial in a scratch repo (word-count CLI, two steps):
  - Session A, Claude Haiku 5.5 low, launched with `--worksheet`: did step 1 under a house rule (WC-ERR: prefix, exit 7) given in its prompt. 10 s, about 33K tokens.
  - A was then resumed without `--worksheet` and told the `--lines` output must read `lines: N`, so that rule existed only in A's transcript.
  - Session B, fresh Haiku 5.5 low, prompt was only the worksheet path plus the recall instruction. It ran one recall query (`"lines"`), found the unlogged rule, kept the WC-ERR rule from the log, and committed step 2 correctly. 18 s, about 36K tokens.
  - Session C, Devin SWE-2 medium (free tier), read-only: told not to read the code, the Progress section or history. It recovered both rules with plain-English queries (`"exit code error"`, `"--lines output format"`), the second through the closest-lines fallback. 13 s, about 16K tokens.
- The first trial run found that a symlinked `jamsession` without a matching `JAMSESSION_HOME` could not find the recall helper; the lookup now checks the install and checkout layouts and fails loudly.

## Follow-ups

- Devin runs its shell commands with its own login PATH, so a worker sees whichever `jamsession` is installed. Workers need the installed version updated before they can use recall.
