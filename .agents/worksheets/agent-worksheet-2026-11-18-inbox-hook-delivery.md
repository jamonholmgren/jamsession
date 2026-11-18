# Inbox hook delivery for message

Request (Jamon via Performance Team Lead): make the post-tool inbox hook the default way `message` reaches providers without native delivery, check the hook before sending, ship the hook with jamsession.

## Findings
- Codex 0.169 and Muse keep native delivery. Codex also has Claude-style PostToolUse hooks (`.codex/hooks.json`) but project hooks need project trust and per-hook hash trust, so jamsession does not install them.
- Claude, Devin read PostToolUse hooks from `.claude/settings.json`; both verified live through `jamsession run` (note sent mid-run reached the model).
- Grok reads `.claude/settings.json` too, but headless `grok -p` skips untrusted project hooks; a user-level `~/.grok/hooks/*.json` hook fires. Verified live.
- `claude -p --input-format stream-json` accepts user messages on stdin mid-run (verified), but would change output parsing, cost capture and process lifetime of every Claude run (the test process stayed alive after the result and stdin close). Not built; the hook gives the same between-tool-call delivery. Timing (2026-11-18, Claude Code 2.1.327): a stdin message sent during a 20 s tool call is taken mid-turn, attached as a queued command right after that tool result and before the next tool call, within the same turn; it does not interrupt the running tool.

## Shipped
- `usage/jamsession_hooks.py`: `run` (hook), `install`, `check`, `deliver`. Hook command guards the installed file and always exits 0 (~50 ms when idle).
- `jamsession hooks <install|check> [project]`; claude/grok/devin `message` without `--resume-with` writes the note in the recipient's project (from its transcript/session record) only when wired, else exits 3.
- Existing in-repo `jamsession_inbox.py` wiring (jambot, GunshipOrigins) counts as wired for Claude only: it reads CLAUDE_PROJECT_DIR. `install` adds the shipped entry beside it.
- Subagent tool calls (payload `agent_id`) leave notes for the parent session.
