---
name: jamsession-execute-agent-slice
description: Execute one bounded worker assignment from a coordinating agent while preserving ownership, scope, and verifiable handoff evidence. Use when an agent brief assigns a specific implementation, review, research, or validation slice; do not broaden or commit without authority.
---

# Execute An Agent Slice

1. Identify the objective, allowed and forbidden files or systems, required
   inputs, access mode, validation, report destination, stopping conditions,
   and commit authority. If write ownership is missing, stop and report it.
2. Inspect only enough context to complete the slice. Preserve human and sibling
   work; never stash, reset, switch branches, destructively clean, or adopt
   unrelated changes.
3. Make the smallest complete change inside the assigned ownership. Stop when
   completion requires a product decision, broader authority, or edits outside
   the slice.
4. Run the cheapest check that could falsify the result, plus every explicitly
   required gate. Do not claim unrun or unavailable validation.
5. Return a concise verdict, files inspected or changed, commands and results,
   blockers, safe-to-integrate paths, and follow-ups. Review-only work returns
   findings without editing. Do not stage or commit unless the brief explicitly
   authorizes it.
