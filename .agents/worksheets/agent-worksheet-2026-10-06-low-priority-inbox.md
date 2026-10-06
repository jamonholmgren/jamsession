# Low-Priority Agent Inbox

Status: COMPLETE
Starting HEAD: fafa9e5d30e4ca20b5af1b07da3775bd229705f8

## Request and plan

Jamon authorized concise skill guidance and a Bash helper for asynchronous,
low-priority notes. Use one immutable file per note, print before moving to an
archive on drain, and carefully delete recognized buffer files older than three
days from inbox and archive. Urgent/blocking/terminal messages remain direct.

Jamon refined the interface to `jamsession inbox <recipient-id> read` and
`write <sender-id> <note>`, requiring sender identity in every note. He requested
commit and push, and explicitly chose the project-local `.agents/jamsession/inbox/`.
Implement it in the existing CLI; the installer already ships it. Use immutable
`agent-note-<recipient-id>-<timestamp>-<unique>.txt` files and `archive/`.
One coordinator serializes reads; producers publish unique
notes atomically. Read prints each note before archiving, then sweeps recognized
notes older than three days from both folders. Resolve the current project, never
the home-directory global `.agents` tree. Refuse symlink roots/archives and
leave unrelated files untouched. Test real filesystem operations, failed reads,
file age, exact ID selection, symlinks, concurrent writes and installation.

No changes to Gunship's active checkout. Preserve the pending Muse changes and
unrelated Antigravity adapter; do not include them in this task's publication.

## Outcome and evidence

The CLI now implements project-local, attributed low-priority inbox notes.
Posting publishes a complete uniquely named file. Read selects the exact ID,
prints before archiving, refuses collisions, then expires only recognized regular
note files older than three days by mtime. No recursion, symlink traversal,
provider call, wake-up, model turn, or deletion of unrelated files is involved.
One coordinator serializes reads; writers may post concurrently. Sender IDs
are explicit caller-supplied attribution, not authentication or new authority.

The three skills, README, install guidance, main help and inbox help describe
the command and distinguish disposable notes from urgent/direct handoffs.
The source checkout ignores `.agents/jamsession/inbox/`; other projects must
keep that path ignored as well. No new runtime dependency or service was added.

All 481 tests pass on the exact staged snapshot, excluding the pending Muse fix.
The working tree including that fix passes all 487 tests. The isolated snapshot
was placed in a directory named `jamsession` to match the existing uninstall
test's checkout-name precondition; a differently named fixture returned a safe
refusal but not the asserted marker diagnostic. Bash syntax, all three skill
validators, and staged diff checks pass. Evidence:
`/tmp/jamsession-inbox-bundle.3sQnN1/tests.log`.

Tests cover attribution, exact ID/prefix isolation, concurrent publication,
notes arriving during drain, repeated reads, failed cat, archive collisions,
age boundaries on inbox/archive, unrelated files, symlink refusal, unsafe IDs,
global-home rejection, and the installed CLI. Cleanup deleted only disposable
test-fixture notes; no real project inbox was swept during this task.

Publication scope: `jamsession`, `.gitignore`, `README.md`, `install.md`, the
three coordination skills, `tests/test_jamsession.sh`, and this worksheet only.
