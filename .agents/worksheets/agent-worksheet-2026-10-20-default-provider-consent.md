# Default workflow provider consent

Status: COMPLETE
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
Upstream source published as c7895bc7cf8631fdc1cf4f71fa9798c7a19e9012.

## Gunship integration and handoff

Supervisor assigned clean detached Agent2 at
332d51bed592c8345f177a7498468a04b4f58f70 under the exact
hold:default-provider-consent-refresh-20261020, only after the previous owner
published and released it. Imported only the canonical summon package through
the local supported installer. Gunship's older copy also gained already-published
Codex sandbox/discovery guidance contained in that same canonical package.
No other package, catalog, engineering skill, setting or gameplay path changed.

Gunship checks: sync --check PASS; 77 skill packages valid; system validator,
byte comparisons and diff check PASS; normal skill/docs-only commit hook PASS.
No game runtime/import/build/display/tests launched. Worktree/index clean at
efd08bd108794499ee04babcdee43e8358813360, seventeen stashes preserved, no actors
left. Supervisor performed the sole main push and exact terminal ACK/release.

After accepted publication, separately authorized human installed-copy refresh:
confirmed no foreign package changes, installed only summon, verified source
bytes and accepted Git blob d63e64ccbd03d963a3a439d445efe543e524796a. Campaign
content hash unchanged before/after; no human merge/stage/commit/push. That
checkout now shows the installed skill change relative to its older HEAD plus
the original campaign work, with an empty index. No duplicate commit needed.
Agent2 had no further writes after handback. Final record baseline: c7895bc above.
