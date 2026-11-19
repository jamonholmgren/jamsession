# Inbox addressed by session ID in one place

Request (Jamon via JamBot, 2026-11-19): "Agents inboxes should use a session ID and a deterministic location in ~/.agents so we never have this problem."

## What failed
- Notes to the label `perf-team-lead` sat in a project inbox no session drains.
- The resend went to 935ecc03, which is a Claude Desktop fork ("Vehicle & Heli Turret Unification") of ad60b177 ("⚡️ Performance"). The hook did deliver by ID: the fork's own lines drained it, the parent never saw it. The sender picked the fork's ID because a fork's transcript begins with a copy of the parent's lines, parent titles and all.

## Findings
- A Desktop fork has its own session ID and transcript file `<id>.jsonl`; its first ~23k lines are copied from the parent and still stamped with the parent's `sessionId`. Its own `custom-title.json` holds its own title. The first stamped line names the parent.
- Devin session IDs are words (`aback-ridge`), Grok and Codex use UUIDv7, so recipients are checked by existence, not shape.
- Every live install (jambot, GunshipOrigins and its Agent slots) used the in-repo `jamsession_inbox.py`, which only looks in the project inbox.

## Shipped
- Inbox root is `~/.agents/jamsession/inbox/` for every project and checkout.
- `inbox <id> write` refuses a recipient no provider has recorded (Claude in every `~/.claude*` home, Codex, Grok, Devin); nothing is queued.
- The hook drains only the payload's `session_id`, skips subagent calls, and skips a payload whose `transcript_path` belongs to another session.
- `message` delivery names the recipient's own title and, for a fork, its parent and the ID to use for the original.
- `hooks install` replaces the legacy `jamsession_inbox` entry; legacy wiring no longer counts as wired.
