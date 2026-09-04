---
name: jamsession-orchestrate-agent-work
description: Coordinate explicitly requested multi-agent work through supervisor, manager, and worker roles with specific ownership. Use only when the user asks to delegate, orchestrate, fan out, or run parallel agent work; do not use for an ordinary single-agent task.
---

# Orchestrate Agent Work

## Own the whole result

The supervisor owns task interpretation, dependency order, shared files,
integration, and final validation. Delegation does not transfer these duties.
Split work only where independent execution saves time or preserves useful
context.

## Assign managers and workers

- A manager owns one execution environment: its capacity, checkout, active
  processes, worker session, and handoff evidence. It does not reinterpret the
  product request or integrate shared changes.
- A worker owns one bounded slice. Give it an objective, allowed and forbidden
  files or systems, required inputs, access level, validation, report shape,
  stopping conditions, and commit authority.
- Keep one write-capable worker per checkout. Parallel work needs separate,
  explicitly authorized workspaces with disjoint ownership.
- Use `jamsession-summon-agent` for provider CLI workers. For remote workers,
  use `jamsession-run-remote-agents` and the exact authorized host and path.

## Integrate from evidence

Treat every worker report as advisory. Inspect its actual diff or artifact,
reject scope drift, run the cheapest checks that prove each slice, then run the
aggregate check that proves their interaction. Resume a worker session for a
focused correction; start fresh when its prior direction would contaminate the
retry.

Do not create extra agents merely to apply a fixed process. Stop delegating
when coordination costs more than completing the remaining work directly.
