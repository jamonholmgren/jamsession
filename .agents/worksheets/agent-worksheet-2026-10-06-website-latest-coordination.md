# Website: Latest Coordination Features

Status: IMPLEMENTED; publication verification follows the push
Starting HEAD: 28110f713825d721c2b55a4342996137bb28c618

## Request and scope

Jamon asked to update the website with the latest changes and push it.
Preserve the approved visual design, personal copy, installation-first flow,
and uncropped screenshot. Explain quiet supervisor/manager/worker coordination,
expected-duration waits and the attributed, project-local low-priority inbox.
Add update guidance and refresh featured usage/model descriptions. Do not claim
the pending, unpublished Muse screen fallback is deployed.

## Plan

Reuse existing sections, layout classes and copy buttons. Keep the landing page
human-facing and concise; detailed inbox syntax remains in CLI/install docs.
Check desktop/mobile rendering, copy controls, markup and local references.
Commit only the website and this record, push main, verify Pages deployment and
the live site. Preserve all pending Muse changes and the Antigravity adapter.

## Implementation and evidence

Added a compact coordination section covering material-event messages, quiet
waits and the attributed project-local inbox, including archival and three-day
expiry. Added an existing-user update disclosure. Refreshed summon, orchestrator,
usage and model copy; corrected the optional system-Python reader description.
Reused existing responsive styles and clipboard code without changing assets.

Inspected desktop and 600px narrow Safari previews: coordination columns stack,
skill names and descriptions fit, update terminal stacks, screenshot stays
uncropped. Inspected the desktop onboarding disclosure in Chrome. Static checks
passed for unique IDs, copy/ARIA targets, local assets and listed skill packages;
the update clipboard handler writes exactly `jamsession update`. `git diff
--check` passed. Existing-user refresh behavior matches the installer.

Pending Muse implementation, documentation, tests and Antigravity were excluded.
Publish this website-only change through the existing Pages workflow and verify
its new copy at the HTTPS domain before reporting deployment complete.
