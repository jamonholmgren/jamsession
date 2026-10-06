---
name: jamsession-summon-agent
description: "Start, resume or message a coding-agent session through the jamsession CLI."
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
   The same no-modify opening is required for Codex on a host configured with
   `JAMSESSION_CODEX_SANDBOX=off`, where read access is not enforced.
3. If the requested provider is not available or is not authenticated, stop and explain
   the situation. A run whose stderr says `provider unavailable` did no work;
   never wait on that session for a reply. For "Not logged in", treat the
   provider as unavailable. For a rejected model, choose an ID from
   `jamsession models <provider>` or treat the provider as unavailable.
4. If resuming work and the session ID is unknown, try `jamsession list <provider>`.
   Some providers cannot list sessions; do not guess an ID when listing is unavailable.
5. Start work with:

   ```text
   jamsession run <provider> new <model> <effort> <read|edit> <prompt>
   ```

6. Retain the `session: <id>` line from stderr when continuity could help.
   Each run also prints `session-size:` with the session's current token
   length, or why the provider exposes none. Past 250K tokens it suggests a
   fresh session; prefer recording state in the task worksheet and starting
   `new` over resuming an oversized session for unrelated work.
   Resume only that provider's exact session:

   ```text
   jamsession run <provider> <session> <model> <effort> <read|edit> <prompt>
   ```

   To contact an existing session, especially one already running, use
   `jamsession message <provider> <session> "<text>"`. Codex and Muse support
   native asynchronous messaging, but may not wake an idle session. A native
   send error is final, not permission to retry through resume. Other bundled
   providers allow one synchronous resume only when you explicitly append
   `--resume-with <model> <effort> <read|edit>`. The owning process must have
   exited, even if its UI looks idle. Claude's active-list guard and Devin's
   lock check are best-effort, not universal ownership guarantees. Never resume
   your own live session. A delivery acknowledgement is not an answer.

   Include your exact return provider and session ID, a request identifier,
   and instructions to reply with `jamsession message <return-provider>
   <return-session> "<request-id>: <answer>"`. Do not guess your own ID. If your
   session cannot receive messages, agree on an exact absolute reply-file path
   before sending and include it in the message. The recipient must have
   permission to write that path. Agree on a unique single-line completion
   marker written last, preferably publish the full reply by atomic rename,
   and do not embed the marker in instructions inside the watched file.

   Use `jamsession watch <absolute-reply-file> "<marker>"` to wait and print the
   reply without another model call. Optionally append your exact provider and
   session to notify through `message` on match or timeout. Default wait is
   300 seconds; `--timeout` changes it. Existing matches count. For your own
   live session use foreground waiting or supported native messaging, never
   resume fallback. Native delivery keeps existing execution settings; explicit
   fallback uses normal run permissions and cannot silently weaken read access.
   See `jamsession help watch` for backgrounding, cancellation, and exit codes,
   and `jamsession help message` for ownership limits. Retain an owned watch's
   PID/log; avoid repeatedly asking another agent whether a reply has arrived.

   If messaging is unavailable, or the session only needs inspection, run
   `jamsession which <provider> <session>` and follow its read-only transcript
   guidance. Do not remove provider locks or edit transcript stores.

7. Start a new session when prior context is irrelevant, noisy, or contains a
   wrong direction. Resume when the session's own findings or unfinished work
   are the main asset.
8. Treat adapter warnings and nonzero exits as results, not permission to
   weaken access or silently choose another provider.
