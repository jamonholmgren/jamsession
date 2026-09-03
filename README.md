# Jam Session

`jamsession` is one small command for running non-interactive coding-agent CLIs and
resuming their native sessions. It keeps provider quirks in separate Bash
adapters so agents can use one explicit positional interface.

## Install

```sh
curl -fsSL https://jamsession.jamon.dev/install.sh | sh
```

The installer needs `curl` and POSIX `sh`. The installed command and bundled
adapters need Bash 3.2 or newer. Jam Session does not require Python, Node, jq, a
package manager, API keys of its own, or a background service.

Bash is the runtime because macOS includes Bash 3.2, Linux and WSL normally
include it, and Git Bash supplies it on Windows. Zsh is excellent interactively
but is not a normal Linux or WSL baseline. The installer itself remains POSIX
`sh` so the first command does not depend on either user's login shell.

It installs under `~/.agents/jamsession/`, installs the direct-use skill under
`~/.agents/skills/`, and links the executable at `~/.local/bin/jamsession`. It
never edits shell startup files.

## Run an agent

```sh
jamsession run codex new gpt-5.6-sol high read "Review the current diff."
jamsession run claude new claude-opus-5 high edit "Implement the requested change."
jamsession run codex 019abc gpt-5.6-sol high read "Check the revised diff."
```

Every choice is required:

```text
jamsession run <provider> <new|session> <model> <effort> <read|edit> <prompt>
```

Pass `-` as the prompt to read stdin. Agent output is stdout. Jam Session writes
the provider-native session ID, warnings, and diagnostics to stderr.

`read` is strict: an adapter must reject it unless the provider can
mechanically prevent writes. `edit` selects the provider's unattended coding
mode and may have broader permissions on providers without a workspace-only
sandbox. Run `jamsession help <provider>` before relying on unfamiliar behavior.

`read` means the agent cannot change your workspace. It does not mean nothing
is written anywhere: the provider still records its own session metadata under
its own directories, and an adapter may write Jam Session temporary output under
`$TMPDIR` to separate the final response from streamed events. Those paths are
outside the workspace and are not agent-controlled.

Model and effort are never coerced. When a provider cannot represent the effort
you asked for, the adapter fails with an explanation instead of substituting a
different one.

## Inspect providers

```sh
jamsession adapters
jamsession doctor
jamsession models cursor
jamsession list grok 5
```

Every adapter accepts the same operations. When its native CLI cannot provide
one, it explains that limitation and exits nonzero. Jam Session does not scrape
private provider state or maintain its own session database.

## Configure

```sh
jamsession init
jamsession help configure
```

Configuration lives at `~/.agents/jamsession/jamsession.conf`. It is sourced as Bash,
so keep it user-owned and do not copy untrusted code into it. `init` discovers
provider executables and adds missing paths without replacing existing values.

## Add an adapter

```sh
jamsession make-adapter antigravity
```

This creates `~/.agents/jamsession/adapters/jamsession_antigravity`. It refuses to
replace an existing adapter unless `--force` is explicit. The generated file
documents the positional adapter contract and defaults unimplemented operations
to a standard unsupported result.

## Optional agent skills

```sh
jamsession skills
jamsession skills install jamsession-orchestrate-agent-work
jamsession skills install all
```

Jam Session includes small reusable skills for direct dispatch, model selection,
ping-pong planning, contrarian review, agent panels, orchestration, bounded
worker slices, scoped SSH work, and running remote agents over SSH. They contain
no project-specific paths or policies.

## Recommendation packs

```sh
jamsession packs
jamsession recommend jamon
jamsession recommend jamon independent-review
jamsession recommend jamon discovery grok
```

A pack is a tab-separated file of dated advice with the columns `role`,
`provider`, `model`, `effort`, `rank`, and `note`. Comment lines carry the
schema, author, update date, and the evidence and limitations behind the rows.
Packs live in `~/.agents/jamsession/packs/`.

`recommend` requires the pack name. It reads only that one file, prints its
metadata and the rows matching the optional role and provider filters, and exits
nonzero when the pack is missing or nothing matches. It never runs an agent,
never assumes a default pack, never merges packs, and never picks a fallback for
you. You still pass the model and effort to `jamsession run` yourself.

Write your own pack by putting an ordinary `.tsv` file beside `jamon.tsv`. There
is no registry, no download, no precedence between packs, and no scoring. The
installer updates `jamon.tsv` only and leaves every other pack alone.

## Update

```sh
jamsession update
```

Update runs the same installer against the moving `main` branch. It replaces
Jam Session's core files, recognized bundled adapters, and the bundled `jamon`
pack, refreshes installed Jam Session skills, preserves configuration, and leaves
unknown adapters and packs alone.

See [DESIGN.md](DESIGN.md) for the deliberately small product boundary.

## Development

```sh
bash tests/test_jamsession.sh
```

The test suite uses fake provider commands and requires no authenticated agent
account. Live provider smoke tests are intentionally separate because they can
consume quota.

## License

[MIT](LICENSE)
