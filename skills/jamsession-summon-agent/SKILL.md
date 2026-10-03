---
name: jamsession-summon-agent
description: Start, resume, or message one coding agent session through the `jamsession` CLI. Use for subagent tasks and contacting existing sessions.
---

# Summon an Agent

1. Run `jamsession help` for the current command contract and `jamsession status` to
   see which installed adapters are usable.
2. Choose the provider, model, effort, and `read` or `edit` access explicitly.
   Never request `edit` unless the task authorizes changes. Grok is the only
   exception: its CLI cannot enforce read-only access. When the user explicitly
   authorizes Grok for a read-only task, use `edit` transport and begin the prompt
   with: `Do not modify, create, delete, rename, format, stage, or commit files;
   do not run state-changing commands.`
3. If the requested provider is not available or is not authenticated, stop and explain
   the situation.
4. If resuming work and the session ID is unknown, try `jamsession list <provider>`.
   Some providers cannot list sessions; do not guess an ID when listing is unavailable.
5. Start work with:

   ```text
   jamsession run <provider> new <model> <effort> <read|edit> <prompt>
   ```

6. Retain the `session: <id>` line from stderr when continuity could help.
   Resume only that provider's exact session:

   ```text
   jamsession run <provider> <session> <model> <effort> <read|edit> <prompt>
   ```

   To contact an existing session, especially one already running, use
   `jamsession message <provider> <session> "<text>"`. Codex and Muse support
   native asynchronous messaging. Other providers report unavailable; do not
   silently resume a busy session. A delivery acknowledgement is not an answer.

   Include your exact return provider and session ID, a request identifier,
   and instructions to reply with `jamsession message <return-provider>
   <return-session> "<request-id>: <answer>"`. Do not guess your own ID. If your
   session cannot receive messages, agree on an exact absolute reply-file path
   before sending, include it in the message, and check it at agreed checkpoints.
   The recipient must have permission to write that path. Messaging uses the
   recipient's existing model, permissions, and workspace; it does not grant
   new authority. An idle session's delivery behavior depends on its provider.

   If messaging is unavailable, or the session only needs inspection, run
   `jamsession which <provider> <session>` and follow its read-only transcript
   guidance. Do not remove provider locks or edit transcript stores.

7. Start a new session when prior context is irrelevant, noisy, or contains a
   wrong direction. Resume when the session's own findings or unfinished work
   are the main asset.
8. Treat adapter warnings and nonzero exits as results, not permission to
   weaken access or silently choose another provider.
