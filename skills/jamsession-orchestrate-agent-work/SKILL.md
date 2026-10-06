---
name: jamsession-orchestrate-agent-work
description: "Coordinate explicitly requested delegation, parallel agents or task queues with supervisors, managers and workers; not single-agent work."
---

# Orchestrate Agent Work

## Supervisor: own the queue

The current session interacting with the user is always the supervisor. It owns
the ticket queue, task interpretation, dependency order, and communication with
the user. It keeps managers supplied with ready tickets, relays their questions
and results, and makes sure work continues.

Protect the supervisor's context. Track concise state and outcomes instead of
following every implementation detail or raw log. Do not micromanage managers.
Accept a ticket back only when its work is fully committed according to the
repository's convention, or when the manager is genuinely blocked with a clear
question or required external change. Use low or light effort when the model is
capable enough; raise it for lower-intelligence models or difficult queue
decisions.

Keep short investigations and direct answers with the supervisor when delegation
would cost more context than it saves. For long-running work, delegate a bounded
implementation batch, agree on its checkpoint artifacts and stopping conditions,
then leave the worker running. Inspect at those checkpoints or when the worker
reports a blocker; do not repeatedly poll or mirror its implementation context.

Before staffing managers or workers, run `jamsession status` and choose from the
available providers. Choose every provider, model, effort, and access level
explicitly.

If `jamsession-use-agent-worksheet` is available, use it for each managed ticket.
The manager owns that ticket's worksheet; workers report evidence to the manager
rather than editing the shared record concurrently.

## Manager: own one ticket end to end

A manager executes one current ticket from interpretation through validated
completion. It stays close to the work: commissions planning or review panels
when useful, assigns implementation slices, checks worker evidence and diffs,
integrates the result, runs the required validation, and commits or opens a pull
request when that is authorized and is the repository's convention. Managers
normally need medium or higher effort.

Prefer one sustained implementation worker for a coherent batch over repeatedly
restarting workers. That worker may obtain an independent read-only review at a
declared checkpoint, but the reviewer must diagnose concrete defects and propose
the simplest sufficient correction. A reviewer does not expand scope, add
speculative abstractions, or become a second manager. The manager accepts or
rejects review findings against the ticket's contracts before integration.

One manager handles only one ticket at a time. Spawn multiple managers only for
independent parallel tickets, with separate write ownership or workspaces. Once
a manager exists, let it autocompact and keep resuming that same session for
later tickets rather than replacing it with a fresh manager.

## Worker: own one bounded slice

A worker handles a specific planning, research, review, implementation, or
validation slice assigned by its manager. It does not own full ticket
completion. Give it the objective, boundaries, inputs, access level, required
validation, handoff shape, stopping conditions, and commit authority.

Start a fresh worker session for each new slice. Resume that session throughout
the slice, including focused corrections and follow-up questions. Start over
only when fresh context is specifically useful. Keep one write-capable worker
per checkout; parallel writers need separate authorized workspaces and disjoint
ownership.

Use `jamsession-summon-agent` to start or resume managers and workers. Use
`jamsession-use-remote-agent-over-ssh` when they must run on an authorized remote host.

## Wait without hovering

Supervisors, managers, and babysitters should give their children time to work.
Prefer a harness completion notification or yielding wait that can wake on a
result, blocker, or user input. Otherwise, for shell-managed jobs, use `sleep n`
before checking again: choose n seconds from the expected time to completion or
the next meaningful checkpoint, not a tight polling interval. Do useful
independent work instead when available.

After waiting, inspect the owned process/job handle or agreed log/report; elapsed
time alone is not completion. If nothing material changed, wait another realistic
interval rather than messaging or resuming the child for status. Use yielding,
background, or segmented waits for long delays so user communication and
cancellation stay responsive, and honor existing deadlines.

## Keep the hierarchy working

Workers report evidence to managers. Managers inspect and integrate that
evidence, then return completed tickets or precise blockers to the supervisor.
The supervisor communicates decisions and questions with the user and feeds the
next ready ticket to an available manager.

Send inter-agent messages only at material events: assignments or scope changes,
findings that change another agent's next action, blockers needing input, agreed
checkpoints, review verdicts, and final handoffs. Work quietly between those events. Do not
send routine progress narration, reassurance, acknowledgements, or "still working"
messages, and do not reply to such messages unless they require action. A result
or notification does not need a courtesy reply. Relay actionable questions and
outcomes up the hierarchy, not every worker update.

Put this communication contract in delegated briefs. Batch non-urgent findings
into the next checkpoint or handoff; report blockers and urgent shared risks
promptly. Use process completion, logs, or an agreed file watch for waiting, not
model turns or messages asking whether work is still running. Explicitly
requested reporting cadence and planning/review exchanges remain valid; keep
each exchange substantive rather than adding status chatter around it.

Contact existing managers and workers with `jamsession message <provider>
<session> "<text>"` when their adapter supports it, including when they are
already running. Give each request an identifier and an explicit return
provider/session or agreed reply-file path. Recipients send questions and
results through that return route. Confirm the answer at a checkpoint;
provider acceptance alone does not mean the work finished. Use the messaging
and fallback guidance in `jamsession-summon-agent` when delivery is unsupported.
For agreed file replies, use `jamsession watch` with a unique final completion
marker instead of repeated agent check-ins. Foreground waiting prints the reply;
an explicit target receives a match or timeout notification. Never resume a live
manager or your own session to deliver it. Background watches need an owned PID,
log, and cancellation plan; `jamsession help watch` gives the shell pattern.

Keep queue work lean by default:

- Reuse current repository discovery while its inputs remain unchanged.
- Give each ticket a small evidence budget: changed contracts, decisive focused
  checks, and any broader gates required by risk or repository policy.
- Validate from narrow checks toward broader required gates. Do not rerun green
  evidence unless its code, tests, fixtures, configuration, toolchain, or
  integration prerequisites changed.
- Preserve the first useful failure and retry only affected or inconclusive work.
- Use idle capacity for read-only preparation of the next independent ticket.
- Parallelize only independent work with isolated write ownership. Keep writers
  and stateful tests sequential within a shared checkout.
- Integrate completed tickets atomically rather than combining unrelated work.

Repository instructions, acceptance criteria, required proof, and approvals
always take precedence over throughput.

Do not create extra agents merely to apply a fixed process. Stop delegating
when coordination costs more than completing the remaining work directly.
