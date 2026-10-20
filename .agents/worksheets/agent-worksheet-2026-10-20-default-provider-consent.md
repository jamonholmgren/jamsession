# Default workflow provider consent

Status: ACTIVE
Starting HEAD: 60cf65fbde07d97ca23cd004dc4f9889bcaf717d

## Source and scope

Jamon's request relayed by Codex session 01a15b03-fd07-7ee2-9467-fcb3db6abf5f:
"That skill should have an exception for well-known defaults covered in
[$jamsession-model-recommendations] … please tell the Jam Session agent (codex)
to make that change and commit and push up and update gunship with it".

Change the summon skill only: user-requested workflows cover their documented
provider/model defaults without requiring enumeration. Preserve explicit provider
restrictions, task-relevant scope, secret exclusions and actual approval gates.
An installed skill alone is not authorization. Attribute defaults to the user's
workflow request plus the recommendation, not fabricated explicit provider names.
No CLI policy mechanism, model-list edits or engineering-skill edits.

## Plan and evidence

Edit the existing consent decision, independently check realistic default,
restriction, scope-expansion and denial cases, validate/install the package,
commit/push upstream, then refresh only the matching Gunship package through
the supported installer in an assigned workfolder. Gunship allocation requested
from its Supervisor; no human-checkout writes or runner claims made here.

Source package and all callers inspected: other workflows already route consent
to summon, so no duplicated exception is needed. Multiplayer/gameplay unaffected.
Session: Codex 01a0687d-fa9f-7840-9242-b37d74de00d1 (implementation).
Changed: skills/jamsession-summon-agent/SKILL.md.

Independent review: internal Codex agent `/root/default_consent_review` checked
requested PPP defaults, forbidden Anthropic, installation without delegation,
unrelated private repos, actual Auto-review denial and truthful launch attribution.
It flagged fallback ambiguity; clarified that listed alternatives alone do not
authorize materially different providers outside the workflow default set. Final
review found no remaining contradiction. No provider/model catalog duplicated.

System skill validator, diff check and supported local `skills install` pass;
installed SKILL.md and UI metadata match source byte-for-byte. Existing package
suite: 612 passed, zero failed. No new permanent wording assertions or runtime
changes added. Pre-commit baseline remains the starting HEAD above.
Gunship Supervisor reports Agent2 still occupied, with assignment to follow its
serialized acceptance/release. No checkout claimed or modified prematurely.
