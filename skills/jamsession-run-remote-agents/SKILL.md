---
name: jamsession-run-remote-agents
description: Launch or resume Jam Session coding-agent sessions on an explicitly authorized SSH host, using that host's agent authentication and checkout. Use for remote agent execution; do not forward credentials, discover hosts, or silently fall back to a local agent.
---

# Run Remote Agents With Jam Session

1. Require the authorized SSH alias, remote checkout path, provider, model,
   effort, access, and worker brief. Verify the remote `jamsession status
   <provider>` result before relying on the worker.
2. Keep inference, repository access, edits, and validation on the remote host.
   Use its existing provider authentication; never forward local credentials.
3. Send the brief over stdin so arbitrary prompt text is not interpolated into
   the remote command. Quote the fixed host path and positional values. The
   remote shape is:

   ```text
   cd <authorized-checkout> && jamsession run <provider> <new|session> <model> <effort> <read|edit> -
   ```

4. Retain the remote provider's `session: <id>` stderr line and resume it only
   on the same host, OS user, provider, and checkout when its context remains
   useful.
5. Treat disconnects as uncertain outcomes. Inspect the remote process,
   checkout, and requested report before retrying; never launch a duplicate
   write worker merely because SSH stopped displaying output.
6. Give the remote worker a bounded brief in the prompt itself: the exact task,
   the paths it may change, the validation it must run, what it must not touch,
   and the report you expect back. A remote worker cannot ask a follow-up
   question, so an ambiguous brief returns unusable work.
7. Keep any direct recovery or inspection inside the same authorized alias and
   checkout. Run read-only commands first, quote every path, and never widen
   the connection, user, or host set to diagnose a failure.
8. Report remote evidence without exposing credentials or private connection
   details.
