---
name: jamsession-orchestrate-agent-work
description: Run explicitly requested multi-agent work through a context-protecting supervisor, ticket-owning managers, and bounded workers. Use when the user asks to orchestrate, delegate, fan out, or work through a task queue; do not use for an ordinary single-agent task.
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

Before staffing managers or workers, run `jamsession status` and choose from the
available providers. Choose every provider, model, effort, and access level
explicitly.

## Manager: own one ticket end to end

A manager executes one current ticket from interpretation through validated
completion. It stays close to the work: commissions planning or review panels
when useful, assigns implementation slices, checks worker evidence and diffs,
integrates the result, runs the required validation, and commits or opens a pull
request when that is authorized and is the repository's convention. Managers
normally need medium or higher effort.

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

## Keep the hierarchy working

Workers report evidence to managers. Managers inspect and integrate that
evidence, then return completed tickets or precise blockers to the supervisor.
The supervisor communicates decisions and questions with the user and feeds the
next ready ticket to an available manager.

Do not create extra agents merely to apply a fixed process. Stop delegating
when coordination costs more than completing the remaining work directly.
