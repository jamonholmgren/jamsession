---
name: jamsession-summon-agent
description: Start or resume one coding agent session through the `jamsession` CLI with one of the available providers, model, effort, access level, and provider-native session ID. Use for subagent tasks.
---

# Summon an Agent

1. Run `jamsession help` for the current command contract and `jamsession status` to
   see which installed adapters are usable.
2. Choose the provider, model, effort, and `read` or `edit` access explicitly.
   Never request `edit` unless the task authorizes changes.
3. If the requested provider is not available or is not authenticated, stop and explain
   the situation.
4. If resuming work and the session ID is unknown, use `jamsession list <provider>`
   to get a list of recent sessions.
5. Start work with:

   ```text
   jamsession run <provider> new <model> <effort> <read|edit> <prompt>
   ```

6. Retain the `session: <id>` line from stderr when continuity could help.
   Resume only that provider's exact session:

   ```text
   jamsession run <provider> <session> <model> <effort> <read|edit> <prompt>
   ```

7. Start a new session when prior context is irrelevant, noisy, or contains a
   wrong direction. Resume when the session's own findings or unfinished work
   are the main asset.
8. Treat adapter warnings and nonzero exits as results, not permission to
   weaken access or silently choose another provider.
