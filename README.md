# Jam Session

_An open-source project by [Jamon Holmgren](https://jamon.dev)._

A tiny CLI your favorite coding agent uses to summon other coding agents, and some useful skills and workflows that this enables.

Spin up any of the agents below and resume their sessions, view usage data, and more.

All in a few small bash scripts.

<img width="800" alt="Example of using Jam Session" src="https://github.com/user-attachments/assets/7cff32a2-f2f4-469c-9b25-b9e5ea8e5900" />

### Supported Agent Providers

* Codex
* Claude Code
* Cursor Agent
* Grok
* Copilot
* Devin
* Muse
* _any other agent CLI -- just have your agent build an adapter for it!_

**Star this repo if you find it interesting!** I appreciate the support.

**No dependencies.**

## Install

The easiest way is to just tell your agent to install it with this prompt:

```
Install Jam Session by following https://jamsession.jamon.dev/install.md, then onboard me and teach me to use it effectively.
```

[Manual install steps below.](#install-manually)

## How to use Jam Session as a human

I like to have my _agent_ use Jam Session to manage other CLI-based agents.

Currently, we support the providers [listed above](#supported-agent-providers). But here's how I use it.

When I have a task and want agents to talk to each other, I'll use the proper skills associated with that:

* **Agent Panel:** I'll have my agent ask two or more different agents to form a panel to answer a question. They make separate plans and then your agent will combine them into a single response.
* **Ping-pong Planning:** Similar to Agent Panel, but more for robust planning. First, uses an agent panel to make separate plans, then my agent combines them, kicks them back to first one, then the other for comment, similarly down the line, and integrates valid feedback as it goes. Super good for getting much stronger agent plans or doing deeper research.
* **Contrarian Review:** Can be combined with the panel or ping-ponging. Introduce a contrarian (adverse) reviewer. I like to use Grok for this, and Fable / Astra as main "adults talking", while this annoying kid Grok tries hard to poke holes in it.
* **Orchestrator:** This is essentially what runs my well-known [Night Shift](https://jamon.dev/night-shift) autonomous work system. Your agent runs workers (or sometimes even managers, who then manage workers) to do autonomous loop work. It can keep checked-in task state with **Agent Worksheet**, and uses the **Individual Worker Workflow**, **Work Over SSH**, and **Use Remote Agent Over SSH** skills, which aren't necessarily intended for you to use directly.
* **Model Recommendations:** If you're using the same providers that I do, this is useful for knowing what I (Jamon) prefer to use for what types of work. Loading it up means you can focus on your work, and the agent will decide what other agents work best for what situations.
* Your agent will already know to use the **Summon agent** skill to load up and resume the other agent sessions, so it underlies all the others.

## How to use Jam Session as an agent

These instructions are for agents using Jam Session.

### Install manually

Here's the install script:

```sh
curl -fsSL https://jamsession.jamon.dev/install.sh | sh
```

Installs to `~/.agents/jamsession/` and links `~/.local/bin/jamsession`. Never touches your shell startup files.

### Run an agent

```sh
jamsession run <provider> <new|session> <model> <effort> <read|edit> <prompt>

jamsession run codex new gpt-5.6-sol high read "Review the current diff."
jamsession run claude new claude-opus-5 high edit "Implement the requested change."
jamsession run codex 019abc gpt-5.6-sol high read "Check the revised diff."
```

Every part is required. Pass a session ID instead of `new` to resume, and `-` as the prompt to read stdin. The reply goes to stdout; session IDs, the session's current token size, and diagnostics go to stderr. Past 250K tokens it suggests handing off to a fresh session.

`read` means the agent is called with the best settings to avoid changing your workspace. `edit` uses the provider's unattended coding mode. Model and effort are passed through or mapped to provider-supported variants.

### Get Providers, Models, Sessions

To contact an existing session (including one already running):

```sh
jamsession message codex SESSION_ID "Which checkout can I use? Reply to ..."
```

Codex and Muse support asynchronous messages. Include your return provider and
session ID so the other agent can message back, or agree on a reply-file path.
Other bundled providers can resume once if you append
`--resume-with <model> <effort> <read|edit>` and the session's owning process has
exited. Native send errors never fall back to resume. See `jamsession help message`.

Waiting for a file reply doesn't need another agent call:

```sh
jamsession watch /absolute/reply.txt "REQUEST-42-DONE" --timeout 300
jamsession watch /absolute/reply.txt "REQUEST-42-DONE" codex SESSION_ID
```

The first waits and prints the reply; the second also messages that session on
match or timeout. Use a unique marker written last. Already-arrived replies
count. Default wait is five minutes. For your own live session, use foreground
waiting or native messaging—not resume fallback. Native messaging is not a
guaranteed wake-up; Muse may reject a closed session. `jamsession help watch`
explains backgrounding and cancellation without a daemon.

```sh
jamsession providers
jamsession status
jamsession models cursor # lists models available on cursor agent
jamsession list grok 5 # lists the last 5 grok sessions in this code base (if available)
jamsession which devin SESSION_ID # locates the transcript store and explains read-only access
jamsession init # installs jam session in the current project
```

Bundled: `claude`, `codex`, `copilot`, `cursor`, `grok`, `devin`, `muse`. `jamsession adapters` is an exact alias for `jamsession providers`. `init` finds the provider executables and writes `~/.agents/jamsession/jamsession.conf`. `status` combines provider readiness with available subscription usage; use `doctor` for focused diagnostics. `which <provider> [session]` reports the provider's local transcript store and safe access instructions. Devin supports `edit` but not guaranteed `read` access. Muse supports both; its `models` and `list` commands read Muse's local model cache and session logs. Codex `models` reads `codex debug models`.

### Skills

```sh
jamsession skills
jamsession skills install jamsession-orchestrate-agent-work
jamsession skills install all
jamsession skills uninstall jamsession-orchestrate-agent-work
jamsession skills uninstall all
```

`jamsession-summon-agent` and `jamsession-get-agent-usage` are installed by default. Ask your agent for current usage and it will turn `jamsession usage --json` into a readable table. The rest are opt-in: model recommendations, ping-pong planning, contrarian review, agent panels, orchestration, agent worksheets, worker tasks, and SSH.

Usage reports include Devin and Muse. Devin reads its startup quota screen;
Muse reads its CLI's last-observed subscription windows, with an observation
timestamp. Missing or expired Muse data stays unavailable. Neither reader
spends a model prompt or uses a reset; both use system Python 3.

Uninstalling `all` removes every `jamsession-*` skill directory, including custom ones. It leaves unrelated skills and `~/.agents/skills/` alone.

### Add an adapter

```sh
jamsession make-adapter antigravity
```

Scaffolds `~/.agents/jamsession/adapters/jamsession_antigravity` with the contract documented inline. Won't overwrite without `--force`.

### Update

```sh
jamsession update
```

Refreshes core files, bundled adapters, and installed skills. Leaves your config and custom adapters alone.

### Uninstall

```sh
jamsession uninstall
```

Removes the command, installation tree, and every `jamsession-*` skill. It leaves unrelated files alone and is safe to run twice. Custom adapters and config inside `~/.agents/jamsession/` are removed too.

### Development

```sh
bash tests/test_jamsession.sh
```

Uses fake providers, so no accounts or quota.

## License

[MIT licensed](https://opensource.org/license/mit).
