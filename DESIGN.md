# Jam Session design

Jam Session is a small Bash dispatcher for non-interactive coding-agent CLIs. It
normalizes explicit provider selection, new or resumed sessions, model,
reasoning effort, and access intent without becoming an agent framework or
owning session history.

## Product contract

```text
jamsession run <provider> <new|session> <model> <effort> <read|edit> <prompt>
```

- Every execution choice is positional and required.
- `new` starts a provider-native session. Any other non-empty value is the
  provider-native session identifier to resume.
- `read` must be mechanically enforced by the provider CLI. An adapter that
  cannot guarantee it must reject the run. `read` bounds agent-controlled
  workspace changes; it is not a claim that the run writes nothing anywhere.
  Provider session metadata under the provider's own directories, and Jam Session
  temporary output under `$TMPDIR`, are still written. Both are outside the
  workspace and neither is agent-controlled.
- Explicit model and effort values are passed through or rejected, never
  coerced. An adapter that cannot represent the requested effort exits with an
  error naming the limitation rather than substituting a different effort.
- `edit` selects the provider's unattended coding mode. An adapter prints a
  concise first-run warning when that mode grants broader access than the name
  might suggest.
- Agent output goes to stdout. Session identifiers, hints, warnings, and
  diagnostics go to stderr.
- Jam Session does not store prompts, transcripts, or a cross-provider session
  index.

Jam Session also dispatches these provider operations:

```text
jamsession list <provider> [count]
jamsession models <provider>
jamsession usage <provider>
jamsession status <provider>
jamsession doctor [provider]
```

Every adapter accepts every operation. Unsupported native functionality emits
a standard explanation and a nonzero exit status.

## Adapter contract

Adapters are executable files named `jamsession_<provider>` in
`~/.agents/jamsession/adapters/`. They receive the same positional command as the
outer CLI with the provider removed:

```text
jamsession_<provider> run <new|session> <model> <effort> <read|edit> <prompt>
jamsession_<provider> list [count]
jamsession_<provider> models
jamsession_<provider> usage
jamsession_<provider> status
jamsession_<provider> doctor
jamsession_<provider> help
```

`jamsession make-adapter <provider>` creates a standalone template. It refuses to
replace an existing adapter unless `--force` is supplied. The installer updates
the bundled adapter filenames and leaves unknown adapters untouched.

## Installation and configuration

The POSIX `sh` installer downloads the moving `main` branch into:

```text
~/.agents/jamsession/
  bin/jamsession
  adapters/jamsession_*
  packs/*.tsv
  jamsession.conf
~/.agents/skills/<installed-jamsession-skill>/SKILL.md
```

It links `~/.local/bin/jamsession` to the installed command and never edits shell
startup files. `jamsession update` runs the same installer. `jamsession init`
idempotently discovers provider executables, preserves existing configuration,
and prints concise next steps for an agent. Configuration is shell-sourceable
and therefore must remain user-owned and non-writable by other users.

The installer includes `jamsession-summon-agent` by default. Other workflow
skills are optional and can be listed or installed through `jamsession skills`.
Skills own reusable agent procedure; the CLI remains only a transport adapter.
The installer updates `packs/jamon.tsv` and leaves every other pack file alone.

The runtime targets Bash 3.2 or newer. That covers the Bash shipped with macOS,
normal Linux and WSL installations, and best-effort Git Bash without requiring
Python, Node, jq, or a package manager.

## Recommendation packs

A pack is a tab-separated advice file with the columns `role`, `provider`,
`model`, `effort`, `rank`, and `note`. Lines beginning with `#` carry the
schema, author, update date, and the evidence and limitations behind the rows.

```text
jamsession packs
jamsession recommend <pack> [role] [provider]
```

- The pack name is always explicit. There is no default pack and no implicit
  pack for `run`.
- `recommend` reads exactly one file, prints its metadata comments and every
  matching row, and exits nonzero when the pack is missing or nothing matches.
- Packs are advice, not configuration. Nothing in Jam Session reads a pack while
  running an agent, and a recommendation never becomes a run default.
- A user pack is an ordinary `.tsv` file placed beside the bundled one. There is
  no registry, downloading, cross-pack precedence, scoring, freshness
  arithmetic, or `make-pack` command.

## Initial providers

- Codex
- Claude
- Cursor Agent
- Grok
- GitHub Copilot

Provider adapters prefer native plain-text output. A provider-specific parser
is permitted only when the native CLI cannot return the final response and
session identifier separately without it.

## Deliberate non-goals

- Agent orchestration, queues, or concurrency
- A session database or transcript store
- Review, consult, or other workflow-specific prompt contracts
- Silent access, model, or effort downgrades
- Automatic model selection, pack merging, or pack scoring
- A stable binary adapter ABI beyond the documented command contract
- Native PowerShell support in the first version
- Project-specific repository policy inside the reusable skills

## Validation

Shell tests use fake provider executables to verify dispatch, argument
validation, access enforcement, session handling, output-channel separation,
adapter scaffolding, initialization, effort rejection, pack reading, and
installer preservation rules for unknown adapters and unknown packs. Live
smoke tests are separate because they require installed authenticated provider
CLIs and may consume quota.
