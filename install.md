# Install Jam Session

Jam Session is a small Bash CLI and a set of optional agent skills. It lets a
coding agent start and resume sessions through Codex, Claude, Cursor Agent,
Grok, and GitHub Copilot using one explicit positional interface.

## Install

Run:

```sh
curl -fsSL https://jamsession.jamon.dev/install.sh | sh
```

The installer requires `curl` and POSIX `sh`. The installed command requires
Bash 3.2 or newer. It installs under `~/.agents/jamsession/`, installs the
direct-use skill under `~/.agents/skills/`, and links the command at
`~/.local/bin/jamsession`. It does not edit shell startup files.

If `~/.local/bin` is not already on `PATH`, follow the installer message for
your shell, then open a new shell or reload its configuration.

## Find providers

Run:

```sh
jamsession init
jamsession status
```

`init` records provider CLIs already available on `PATH` without replacing
existing configuration. If a provider is missing, install and authenticate its
native CLI first, then run `jamsession init` again. `status` shows readiness and
available subscription usage; use `doctor` for focused diagnostics. Run `jamsession help
configure` for manual path overrides.

## Run an agent

Every execution choice is explicit:

```text
jamsession run <provider> <new|session> <model> <effort> <read|edit> <prompt>
```

For example:

```sh
jamsession run codex new gpt-5.6-sol high read "Review the current diff."
```

Agent output goes to stdout. The provider-native session ID, hints, warnings,
and diagnostics go to stderr. Retain the printed session ID to continue:

```sh
jamsession run codex <session-id> gpt-5.6-sol high read "Check the revision."
```

Use `read` for work that must not modify the workspace. An adapter hard-errors
when its provider cannot mechanically enforce that restriction. Provider-native
session metadata and Jam Session temporary output may still be written outside
the workspace. Use `edit` only when the task authorizes unattended changes.

## Install workflow skills

List the available skills:

```sh
jamsession skills
```

Install one or all optional skills:

```sh
jamsession skills install jamsession-ping-pong-planning
jamsession skills install jamsession-contrarian-review
jamsession skills install jamsession-ask-agent-panel
jamsession skills install all
```

Remove skills you no longer want:

```sh
jamsession skills uninstall jamsession-ask-agent-panel
jamsession skills uninstall all
```

Only directories named `jamsession-*` are removed, and `all` includes prefixed
skills you wrote yourself. Unrelated skills and `~/.agents/skills/` itself stay.
A `jamsession-*` directory is removed whole, so your own notes inside one go
with it and the command says so.

Run `jamsession help` for the complete CLI contract and `jamsession help
<provider>` for provider-specific behavior.

## Uninstall

Run:

```sh
jamsession uninstall
```

This removes the `~/.local/bin/jamsession` symlink, the `~/.agents/jamsession`
installation tree, and every `jamsession-*` skill directory under
`~/.agents/skills/`. The installation tree includes `jamsession.conf` and any
custom adapters kept inside it.

It leaves `~/.agents` itself, skills outside the `jamsession-` namespace, and a
`~/.local/bin/jamsession` that is not a symlink to this installation. Whatever
it leaves is named on stderr and the command exits 1. Running it again is safe.

Run `jamsession help uninstall` for the exact paths on your machine.
