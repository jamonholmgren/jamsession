---
name: jamsession-work-over-ssh
description: Perform a scoped task on an explicitly authorized remote computer through SSH while keeping all required repository operations on that host. Use when the user assigns work to a named SSH host and checkout; do not discover hosts, infer paths, or copy the repository locally.
---

# Work Over SSH

1. Require the authorized SSH alias, remote checkout path, task scope, and
   expected handoff. Do not scan hosts or home directories to discover them.
2. Verify host identity, user, checkout path, branch, HEAD, working-tree state,
   and relevant tool availability with read-only commands before editing.
3. Run every scoped repository read, edit, Git operation, build, and test on the
   remote host. Do not substitute local results for remote-platform evidence or
   copy the checkout locally unless the user explicitly requests that workflow.
4. Preserve unknown dirty work. Never stash, reset, clean, switch branches, or
   delete files merely to obtain a convenient baseline.
5. Quote remote paths and arguments defensively. Avoid interpolating untrusted
   text into a remote shell command; prefer stdin for large prompts or scripts.
6. Report the remote host, user, checkout, branch and HEAD, changed paths,
   commands and results, blockers, and handoff state. Never report credentials,
   tokens, keys, or credential-bearing remote URLs.
