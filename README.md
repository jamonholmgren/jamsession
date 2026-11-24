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
* Antigravity (Google's `agy` CLI)
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
* **Ping-pong Planning (PPP):** Agents draft independently, then challenge and improve a combined plan. The premium Astra/Opus panel with native Grok as contrarian is nicknamed **Noble Court**. Same workflow; one round by default unless you ask for more.
* **Peasant Mob:** Eight parallel analysis lanes, a LOW-effort Sol or Opus synthesizer, and at least two feedback rounds after the initial drafts. Failed members are named and left behind, not replaced. The [skill](skills/jamsession-peasant-mob/SKILL.md) has the roster and limits. It's experimental—not a claim that more agents beat a premium model or cost the same at every effort.
* **Contrarian Review:** Can be combined with the panel or ping-ponging. Introduce a contrarian (adverse) reviewer. I like to use Grok for this, and Opus / Astra as main "adults talking", while this annoying kid Grok tries hard to poke holes in it.
* **Orchestrator:** This is essentially what runs my well-known [Night Shift](https://jamon.dev/night-shift) autonomous work system. Your agent runs workers (or sometimes even managers, who then manage workers) to do autonomous loop work. It can keep checked-in task state with **Agent Worksheet**, and uses the **Individual Worker Workflow**, **Work Over SSH**, and **Use Remote Agent Over SSH** skills, which aren't necessarily intended for you to use directly.
* **Model Recommendations:** If you're using the same providers that I do, this is useful for knowing what I (Jamon) prefer to use for what types of work. Loading it up means you can focus on your work, and the agent will decide what other agents work best for what situations.
* **Agent Comparison:** Use the [comparison kit](skills/jamsession-run-agent-comparison/SKILL.md) to design, run or evaluate controlled trials with reusable prompts, a manifest and blind scoring guidance. Keep quality, process, availability and cost separate. The caller or project chooses the results home; sharing results is a separate decision, and loading the skill does not authorize new runs.
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

jamsession run codex new sol@latest high read "Review the current diff."
jamsession run claude new opus@latest high edit "Implement the requested change."
jamsession run codex 019abc sol@latest high read "Check the revised diff."
```

Every part is required. Pass a session ID instead of `new` to resume, and `-` as the prompt to read stdin. The reply goes to stdout; session IDs, the session's current token size, and diagnostics go to stderr. Past 250K tokens it suggests handing off to a fresh session.

A provider refusal (spend, usage or rate limit, quota, or auth failure) exits 75. `run --failover` then retries the same model through its other harnesses, Devin first, then the rest of its tier in [`tiers.toml`](tiers.toml), skipping pools that `jamsession usage` shows below 25% before trying them, including the one named in the command (`--min-usage 0` tries every pool). That percentage is the longest window: a 5-hour session window does not skip a pool that also has a weekly or monthly window. An account's `min_usage` replaces 25% for that account. When that provider has two or more accounts, those accounts are tried in the order listed in `accounts.toml` before the run moves to another harness. `--allow-lower` permits cheaper tiers and `--lowest-tier C` only down to tier C, never costlier ones; if all refuse it exits 75 with no answer. `jamsession route <name>` and `run --route <name>` read a `routes.toml` named by `JAMSESSION_ROUTES`, where a route can name a tier and effort instead of a ladder. A routes file can also name `[archetype.<name>]` rung lists: a route sets `archetype` instead of `rungs` or `tier`, with an optional `effort` for every rung, and a panel can set `from_archetypes` to take each list's first available rung.

### Accounts

One provider can have several logins. `jamsession accounts add claude personal` creates `~/.claude-personal`, writes `~/.agents/jamsession/accounts.toml`, and prints the one login command (`claude-personal`, then `/login` inside it). Codex is the same with `CODEX_HOME`: `jamsession accounts add codex side` prints `CODEX_HOME=~/.codex-side codex login`. `--link` symlinks Claude `settings.json` and `skills`, or Codex `config.toml`, from the default account without replacing files that already exist. `jamsession accounts list` shows each account and its usage.

The first account listed for a provider is the default. Each `env` map applies to that one run only. Copy [`accounts.toml.example`](accounts.toml.example) if you would rather edit the file by hand. Jam Session does not overwrite an entry it did not just add.

```sh
jamsession run claude:personal new opus@latest high edit "Use the personal login."
JAMSESSION_CLAUDE_ACCOUNT=personal jamsession run claude new opus@latest high edit "Same selection."
```

A new session records its account in `~/.agents/jamsession/session-accounts.json`. Resume, message and steer use that account again. Naming a different account for a recorded session is refused. With two or more accounts, `jamsession usage claude` reports each one on its own rows. One account leaves the row untagged. `recall` searches every account's history directory. Codex accounts set `CODEX_HOME` and participate in run, resume, message, steer, usage, recall, and failover the same way.

With two or more accounts, and no `account` field in the tiers file, failover tries them in the order listed, then the other harnesses. A tiers via can still name an account; those vias set the order instead. No per-repo pin is required. One account, or no accounts file, leaves the provider argument unchanged. `min_usage = 5` keeps using that account until its longest window is below 5%. `jamsession usage` and `accounts list` lead with the weekly window. Adding another account is `jamsession accounts add` and, when a tiers file names accounts, one more via in that order.

Every new or resumed `run` prints one stderr line with the chosen account's remaining usage and reset time from that cache, for example `jamsession: usage: claude:personal Current week (all models): 72% left, resets Nov 25 at 11am [12m ago]`. When the cached row is older than 30 minutes (`JAMSESSION_USAGE_TTL`, in seconds) the launch starts `jamsession usage <provider>` in the background and does not wait for it, so a later launch shows the new numbers. `JAMSESSION_USAGE_REFRESH=0` turns the refresh off, and `JAMSESSION_USAGE_LINE=0` hides the line.

Naming a bare provider when several accounts exist prints a one-line warning with each account's weekly remaining usage from the last usage cache (`?` when that cache has none; a budgeted account shows spend against its budget) and runs the first account still above its `min_usage` and budget.

An account can take a secret from the macOS Keychain. The value is a service name, read at run time with `security find-generic-password -s <name> -w`, passed only to that run, and never logged or written. A missing item skips the account with one line.

`kind = "api"` with `backend = "claude-cli"` runs headless Claude Code on an API key, in its own `CLAUDE_CONFIG_DIR` (for example `~/.claude-api`), so it does not touch a login session. Each run's `total_cost_usd` is added to that calendar month in `~/.agents/jamsession/spend.json`. `monthly_budget_usd = 500` makes the account unavailable once the month's spend reaches it. `accounts list` and `usage` show the spend against the budget. The backend name is the seam for a later runner; anything other than `claude-cli` is skipped until that runner exists.

```toml
[claude.api]
kind = "api"
backend = "claude-cli"
monthly_budget_usd = 500
env = { CLAUDE_CONFIG_DIR = "~/.claude-api" }
keychain_env = { ANTHROPIC_API_KEY = "jamsession-claude-api" }
```

### Continue from a worksheet instead of compacting

```sh
jamsession run --worksheet .agents/worksheets/task.md claude new haiku@latest low edit "Continue the task in .agents/worksheets/task.md."
jamsession recall --worksheet .agents/worksheets/task.md "Parse Error"
jamsession recall claude SESSION_ID --entry 212 --around 2
```

`--worksheet` on `run`, `message` and `steer` appends the session, its settings and the exact prompt or message to the worksheet's `## Jam Session log`. When a session grows too large, start a fresh one pointed at the worksheet: it reads the worksheet and repo state, then uses `recall` to copy exact lines (an error, a path, an instruction) from every earlier session instead of trusting a summary. `recall` reads JSONL transcripts and Devin's database without changing them; see `jamsession help recall`.

`read` means the agent is called with the best settings to avoid changing your workspace. `edit` uses the provider's unattended coding mode. Model and effort are passed through or mapped to provider-supported variants.

### Get Providers, Models, Sessions

For Codex follow-ups, use `run`: it resumes first and waits for the answer.
Only a confirmed busy/ownership refusal falls back to native delivery, once.
Queued work keeps the owner's settings; `read` runs refuse queue fallback.
`message` also starts idle work directly and queues only if busy/owned;
`steer` explicitly redirects active work. Native control needs system Python 3.
Another process's writer lock stays protected. Its queue may wait until you focus
the desktop session. `delivery: queued; execution unconfirmed` is not an answer
or proof that work started. Do not resend an accepted message.
Unloaded custom permission policies fail safely if they cannot be restored.
Other providers report unsupported steering rather than pretending to interrupt.

Follow up on an existing Codex session:

```sh
jamsession run codex SESSION_ID MODEL EFFORT edit "Continue the assigned task."
```

To send an asynchronous note, or contact your own live session:

```sh
jamsession message codex SESSION_ID "Which checkout can I use? Reply to ..."
```

Codex and Muse support asynchronous messages. Claude, Grok and Devin get an inbox
note the running session reads after its next tool call; `jamsession hooks install
<project>` wires that hook once per project (it merges into `.claude/settings.json`
and adds `~/.grok/hooks/jamsession-inbox.json`), and `message` refuses when it is
missing. Include your return provider and
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

Bundled: `claude`, `codex`, `copilot`, `cursor`, `grok`, `devin`, `muse`, `antigravity`. `jamsession adapters` is an exact alias for `jamsession providers`. `init` finds the provider executables and writes `~/.agents/jamsession/jamsession.conf`. `status` combines provider readiness with available subscription usage; use `doctor` for focused diagnostics. `which <provider> [session]` reports the provider's local transcript store and safe access instructions. Devin supports `edit` but not guaranteed `read` access. Muse supports both; its `models` and `list` commands read Muse's local model cache and session logs. Codex `models` reads `codex debug models`.

`agy` and `gemini` are aliases for `antigravity`. For example:

```sh
jamsession run agy new gemini-3.8-flash xhigh edit "Implement the agreed change."
```

This selects the installed `gemini-3.8-flash-high` model, warning that `xhigh`
maps to `high` because the catalog has no `gemini-3.8-flash-xhigh`. Models with
an xhigh variant, such as `gemini-4-neon xhigh`, use it (`max` maps there too).
Low and medium select their matching variants; an effort-qualified ID such as
`gemini-4-neon-high` is replaced, never doubled, and exact IDs are checked
against `agy models`. Antigravity rejects `read` because its plan mode
does not enforce no writes. Usage reads native `/usage` without a model turn,
keeping Gemini and Claude/GPT quota separate. Messaging requires explicit
`--resume-with` settings and an exited owner; there is no native queue.

### Codex launch settings

Fresh Codex `edit` runs use the operator's native Codex configuration, not a
Jam Session workspace-write/never preset. CLI `read` always forces read-only/never,
including when the old `JAMSESSION_CODEX_SANDBOX=off` setting is present. Control
read resumes request read-only while retaining saved approval/reviewer policy.

Optional overrides in `jamsession.conf`:

```bash
JAMSESSION_CODEX_PROFILE=automation
JAMSESSION_CODEX_CONFIG=('sandbox_mode="danger-full-access"' 'approval_policy="never"')
```

`JAMSESSION_CODEX_PROFILE` names a readable `$CODEX_HOME/automation.config.toml`
(normally `~/.codex/automation.config.toml`). Missing profiles fail rather than
silently falling back. Native CLI launches use `--strict-config`; unsupported
configuration or a Codex version without that flag fails before work starts.

Explicit `JAMSESSION_CODEX_SANDBOX` beats that array; the array beats the selected
profile/native configuration. Approval policies use the native array. Read mode
wins last. Managed requirements always apply. Native Codex resolves trusted
project, selected profile, user and system configuration in its supported order;
invalid/unsupported configuration fails instead of trying different permissions.

Control resumes keep saved permissions and their cold-start validation. Explicit
launch overrides select native CLI resume up front, where Codex loads/validates
them; no failed policy check triggers this selection. A busy queue keeps the
owner's settings and reports that the requested settings were not applied.
Legacy sandbox `off` selects full-access/never for edit only; `on`/`inherit`
delegate to native defaults. Run `jamsession help configure` for details.

### Codex discovery and delivery

Codex `list [count]` lists recent sessions in the current directory through its
native control server, including headless runs. Output is ID and this controller's
runtime status, not proof of desktop availability. An absent listing does not
invalidate a known ID: use `jamsession which codex SESSION_ID` to locate it.
Listing does not resume work. Message output distinguishes accepted turns from
queued work; neither proves the recipient read or completed the assignment.
Verify a task-specific reply or transcript checkpoint before reporting that.

Cold Codex resumes require verified saved settings. Older ID-less settings do
not poison the history when newer verified settings exist, but cannot restore
permissions themselves or leave an older policy eligible. Foreign IDs,
conflicting headers and unsupported permissions still stop before input.

### Low-priority inbox

Low-priority notes can wait without waking another agent:

```sh
jamsession inbox MANAGER_SESSION_ID write worker-id "Slice A is ready for the next review."
jamsession inbox MY_SESSION_ID read
```

Notes live in one per-user inbox, `~/.agents/jamsession/inbox/`, whatever the
project. The recipient must be a real session ID (Claude, Codex, Grok or Devin);
roles and labels are refused. Read prints then archives notes, and expires
recognized notes older than three days. Use direct messages for blockers and
final handoffs.

### Skills

```sh
jamsession skills
jamsession skills install jamsession-orchestrate-agent-work
jamsession skills install all
jamsession skills uninstall jamsession-orchestrate-agent-work
jamsession skills uninstall all
```

`jamsession-summon-agent` and `jamsession-get-agent-usage` are installed by default. Ask your agent for current usage and it will turn `jamsession usage --json` into a readable table. The rest are opt-in: model recommendations, ping-pong planning (Noble Court), Peasant Mob, contrarian review, agent panels, orchestration, agent worksheets, worker tasks, and SSH.

Install the mob skill with `jamsession skills install jamsession-peasant-mob`,
then ask your agent to use it on a scoped question. It is a skill, not a new
`jamsession` subcommand; provider permissions and approvals still apply.

The optional `jamsession-run-agent-comparison` skill owns the comparison workflow;
the caller owns the results. Loading it does not authorize new runs.

Usage reports include Devin and Muse. Devin reads its startup quota screen;
Muse reads its CLI's last-observed subscription windows, falling back to its
local `/usage` screen when needed. Muse preserves the provider's as-of timestamp;
missing data stays unavailable. Neither reader spends a model prompt or uses a
reset; both use system Python 3.

Uninstalling `all` removes every `jamsession-*` skill directory, including custom ones. It leaves unrelated skills and `~/.agents/skills/` alone.

### Add an adapter

```sh
jamsession make-adapter myprovider
```

Scaffolds `~/.agents/jamsession/adapters/jamsession_myprovider` with the contract documented inline. Won't overwrite without `--force`. Run `jamsession help make-adapter` first and use bundled adapters as examples.

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
