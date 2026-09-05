# Jam Session

A tiny CLI your coding agent uses to summon other coding agents.

Summon Codex, Claude Code, Cursor, Grok, and Copilot (more on the way) agents and resume their sessions, view usage data, and more.

All in a few small bash scripts.

**Star this repo if you find it interesting!** I appreciate the support.

<img width="615" height="192" alt="Codex with Jam Session" src="https://github.com/user-attachments/assets/892d5225-6c1b-42c2-a0ab-c002b2d6569d" />

An open-source project by [Jamon Holmgren](https://jamon.dev).

**No dependencies.**

## Install

```sh
curl -fsSL https://jamsession.jamon.dev/install.sh | sh
```

Installs to `~/.agents/jamsession/` and links `~/.local/bin/jamsession`. Never touches your shell startup files.

## Run an agent

```sh
jamsession run <provider> <new|session> <model> <effort> <read|edit> <prompt>

jamsession run codex new gpt-5.6-sol high read "Review the current diff."
jamsession run claude new claude-opus-5 high edit "Implement the requested change."
jamsession run codex 019abc gpt-5.6-sol high read "Check the revised diff."
```

Every part is required. Pass a session ID instead of `new` to resume, and `-` as the prompt to read stdin. The reply goes to stdout; session IDs and diagnostics go to stderr.

`read` means the agent is called with the best settings to avoid changing your workspace. `edit` uses the provider's unattended coding mode. Model and effort are passed through exactly.

## Get Providers, Models, Sessions

```sh
jamsession providers
jamsession doctor 
jamsession models cursor # lists models available on cursor agent
jamsession list grok 5 # lists the last 5 grok sessions in this code base (if available)
jamsession init # installs jam session in the current project
```

Bundled: `claude`, `codex`, `copilot`, `cursor`, `grok`. `jamsession adapters` is an exact alias for `jamsession providers`. `init` finds the provider executables and writes `~/.agents/jamsession/jamsession.conf`.

## Skills

```sh
jamsession skills
jamsession skills install jamsession-orchestrate-agent-work
jamsession skills install all
jamsession skills uninstall jamsession-orchestrate-agent-work
jamsession skills uninstall all
```

`jamsession-summon-agent` is installed by default. The rest are opt-in: model recommendations, ping-pong planning, contrarian review, agent panels, orchestration, worker tasks, and SSH.

Uninstalling `all` removes every `jamsession-*` skill directory, including custom ones. It leaves unrelated skills and `~/.agents/skills/` alone.

## Add an adapter

```sh
jamsession make-adapter antigravity
```

Scaffolds `~/.agents/jamsession/adapters/jamsession_antigravity` with the contract documented inline. Won't overwrite without `--force`.

## Update

```sh
jamsession update
```

Refreshes core files, bundled adapters, and installed skills. Leaves your config and custom adapters alone.

## Uninstall

```sh
jamsession uninstall
```

Removes the command, installation tree, and every `jamsession-*` skill. It leaves unrelated files alone and is safe to run twice. Custom adapters and config inside `~/.agents/jamsession/` are removed too.

## Development

```sh
bash tests/test_jamsession.sh
```

Uses fake providers, so no accounts or quota.

## License

[MIT licensed](https://opensource.org/license/mit).
