---
name: jamsession-individual-worker-workflow
description: "Complete a bounded delegated implementation, review, research or validation task; preserve ownership and handoff evidence."
---

# Individual Worker Workflow

Work quietly between agreed checkpoints. Message the caller only for a blocker
needing input, a finding that changes their next action, a requested checkpoint
or review verdict, or the final handoff. Batch non-urgent findings; report urgent
shared risks promptly. Do not send routine progress narration, reassurance,
"still working" updates, or courtesy acknowledgements, and do not reply to
acknowledgements or notifications that require no action. Continue authorized
work without waiting for a courtesy reply. Follow an explicitly requested
reporting cadence or substantive planning/review exchange.

Useful low-priority notes go through `jamsession inbox <recipient-id> write
<sender-id> "<note>"`, using the caller's agreed IDs and authorized project path.
Use your exact session ID when available; otherwise an agreed stable agent ID,
never a guessed session. Do not wake the caller or request an acknowledgement.
These notes expire after three days; blockers and final handoffs stay direct.

1. Identify the objective, allowed and forbidden files or systems, required
   inputs, access mode, validation, report destination, stopping conditions,
   and commit authority. If write ownership is missing, stop and report it.
   Retain the caller's return provider/session or agreed reply-file path. Send
   questions and handoffs there with `jamsession message` when supported, or
   write the agreed report file. Include the request identifier so the caller
   can match the reply; never infer permission to start other work from a message.
   For a watched reply file, publish the complete report atomically or write the
   agreed unique completion marker last. Never include that marker in unfinished
   report text. Use foreground `jamsession watch` when waiting for an answer to
   your own session; do not resume a live caller or worker as a notification.
2. Inspect only enough context to complete the task. Preserve human and sibling
   work; never stash, reset, switch branches, destructively clean, or adopt
   unrelated changes.
3. Make the smallest complete change inside the assigned ownership. Stop when
   completion requires a product decision, broader authority, or edits outside
   the assignment.
4. Run the cheapest check that could falsify the result, plus every explicitly
   required gate. Do not claim unrun or unavailable validation.
5. Return a concise verdict, files inspected or changed, commands and results,
   blockers, safe-to-integrate paths, and follow-ups. Review-only work returns
   findings without editing. Do not stage or commit unless the brief explicitly
   authorizes it.
