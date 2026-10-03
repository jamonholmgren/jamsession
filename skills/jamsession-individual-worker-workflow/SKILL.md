---
name: jamsession-individual-worker-workflow
description: Guide one worker through a bounded task assigned by a coordinating agent while preserving ownership, scope, and verifiable handoff evidence. Use when an agent brief assigns a specific implementation, review, research, or validation task; do not broaden or commit without authority.
---

# Individual Worker Workflow

1. Identify the objective, allowed and forbidden files or systems, required
   inputs, access mode, validation, report destination, stopping conditions,
   and commit authority. If write ownership is missing, stop and report it.
   Retain the caller's return provider/session or agreed reply-file path. Send
   questions and handoffs there with `jamsession message` when supported, or
   write the agreed report file. Include the request identifier so the caller
   can match the reply; never infer permission to start other work from a message.
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
