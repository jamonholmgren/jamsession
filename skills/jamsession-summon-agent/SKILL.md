---
name: jamsession-summon-agent
description: Summon or resume one coding agent through Jam Session with an explicit provider, model, effort, access level, and provider-native session. Use for non-interactive agent work through Jam Session; do not use for built-in collaboration agents or interactive CLI sessions.
---

# Summon an Agent

1. Run `jamsession help` for the current command contract and `jamsession doctor` to
   see which installed adapters are usable.
2. Choose the provider, model, effort, and `read` or `edit` access explicitly.
   Never request `edit` unless the task authorizes changes. An adapter must
   reject `read` when its provider cannot enforce it.
3. Start work with:

   ```text
   jamsession run <provider> new <model> <effort> <read|edit> <prompt>
   ```

4. Retain the `session: <id>` line from stderr when continuity could help.
   Resume only that provider's exact session:

   ```text
   jamsession run <provider> <session> <model> <effort> <read|edit> <prompt>
   ```

5. Start a new session when prior context is irrelevant, noisy, or contains a
   wrong direction. Resume when the session's own findings or unfinished work
   are the main asset.
6. Treat adapter warnings and nonzero exits as results, not permission to
   weaken access or silently choose another provider.

Jam Session normalizes transport, not task ownership, authorization, review policy,
or validation. Put those requirements in the worker brief.
