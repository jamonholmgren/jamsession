# Jam Session

A tiny CLI your coding agent uses to summon other coding agents. Codex, Claude
Code, Cursor, Grok, and Copilot all have different flags for models, effort,
sandboxing, and resuming sessions. `jamsession` gives them one consistent
interface, plus optional skills for multi-agent work.

**No dependencies.**

## Install

```sh
curl -fsSL https://jamsession.jamon.dev/install.sh | sh
```

Installs to `~/.agents/jamsession/` and links `~/.local/bin/jamsession`. Never
touches your shell startup files.

## Run an agent

```sh
jamsession run <provider> <new|session> <model> <effort> <read|edit> <prompt>

jamsession run codex new gpt-5.6-sol high read "Review the current diff."
jamsession run claude new claude-opus-5 high edit "Implement the requested change."
jamsession run codex 019abc gpt-5.6-sol high read "Check the revised diff."
```

Every part is required. Pass a session ID instead of `new` to resume, and `-`
as the prompt to read stdin. The reply goes to stdout; session IDs and
diagnostics go to stderr.

`read` means the agent cannot change your workspace. If a provider can't
guarantee that, the adapter refuses instead of pretending. `edit` uses the
provider's unattended coding mode. Model and effort are passed through exactly;
nothing is ever substituted.

## Providers

```sh
jamsession adapters
jamsession doctor
jamsession models cursor
jamsession list grok 5
jamsession init
```

Bundled: `claude`, `codex`, `copilot`, `cursor`, `grok`. `init` finds the
provider executables and writes `~/.agents/jamsession/jamsession.conf`.

## Skills

```sh
jamsession skills
jamsession skills install jamsession-orchestrate-agent-work
jamsession skills install all
```

`run-subagents-with-jamsession` is installed by default. The rest are opt-in:
model selection, ping-pong planning, contrarian review, agent panels,
orchestration, worker slices, and SSH.

## Recommendation packs

```sh
jamsession packs
jamsession recommend jamon
jamsession recommend jamon independent-review grok
```

Dated model and effort advice by role. It only prints; you still pass model and
effort to `run` yourself. Add your own `.tsv` beside `jamon.tsv` in
`~/.agents/jamsession/packs/`.

## Add an adapter

```sh
jamsession make-adapter antigravity
```

Scaffolds `~/.agents/jamsession/adapters/jamsession_antigravity` with the
contract documented inline. Won't overwrite without `--force`.

## Update

```sh
jamsession update
```

Refreshes core files, bundled adapters, the `jamon` pack, and installed skills.
Leaves your config, custom adapters, and custom packs alone.

## Development

```sh
bash tests/test_jamsession.sh
```

Uses fake providers, so no accounts or quota. See [DESIGN.md](DESIGN.md) for why
it stays small.

## License

[MIT](LICENSE)
