# Message, Start and Steer Existing Sessions

Status: COMPLETE
Starting HEAD: 4a964a9ec47bc638003d3eeec230a0400a083425

## Request

Jamon approved automatic wake/start behavior inside adapters, not a `--wake`
option. Default messages queue behind active work; steer redirects active work.
Both start idle or unloaded existing sessions through their owner. Resume must
not accidentally start a competing process. Preserve permissions, execution
settings, genuine consent, unrelated WIP and exact-once delivery. Providers that
cannot safely perform the requested intent must report that limitation.

## Plan and findings

Codex currently forwards messages to `codex queue`, which accepted this chat's
assignment at 06:51 but did not start it until the desktop opened it at 07:38.
The official app-server API exposes status, thread/resume, turn/start and
turn/steer. Installed CLI 0.160.1 has app-server proxy; daemon reports 0.162.0
and a local control socket. An earlier read-only proxy probe timed out. Verify
the actual owning-server transport before implementation; do not infer that an
available socket owns a desktop chat or bypass authority to make it appear so.

Source: https://learn.chatgpt.com/docs/app-server . Keep current `run` positional
grammar and add only necessary dispatch/help and native-adapter behavior. Test
working/idle/unloaded delivery, no duplicate execution, errors after acceptance,
and settings preservation, including a disposable chat not open in the UI.

## Implementation and evidence

Added native local Codex control, using system Python's standard library and a
same-user Unix WebSocket. `message` uses native queue/add; the provider starts
idle work and drains queued work after active turns. `steer` uses turn/start,
which redirects an active turn or starts an idle one. No explicit queue/start:
queue/add already starts idle work, and an extra start raced with its consumption.
The adapter starts only Codex's own daemon if needed, never a Jam Session service.

Cold thread/resume initially loaded daemon-default permissions, not the saved
read-only policy. Fixed by restoring the provider's latest rollout settings
before posting input. Canonical read-only, workspace-write and disabled policies
are supported; unrepresentable custom profiles fail before sending. Managed
policy, approval/reviewer, disabled plugins and native writer locks remain intact.
Loaded messages do not call resume or override execution settings. Control run
rejoins the owning server, applies explicit run settings and waits for its result.

A different process's writer lock prevents takeover. Only this exact pre-send
error allows native `codex queue` fallback for message; steer reports unavailable.
An accepted queue is not proof of execution or an answer. Native errors or lost
acknowledgements never cause a retry. Desktop chats owned by a separate process
still depend on that owner's queue consumer; the daemon cannot steal their lock.

Real fixtures (no repository data or tools requested) used `gpt-6-luna`/xhigh:
- `01a121ad-6af6-73f1-afb7-4b3cd8ad6d57`: unloaded read-only message started and
  produced COLD_WAKE_OK without opening the UI; model, effort, cwd, approval,
  reviewer and sandbox matched the original producer's settings.
- `01a121ad-905f-7502-b385-1732f107f539`: same check for workspace-write.
- Both returned LOADED_RESUME_OK through the public run command afterward.
- Earlier owned fixtures verified active queue auto-drain, steering the same
  turn, and foreign-owner rejection. All disposable sessions were archived;
  only their owned producer processes were stopped, never the shared daemon.

Changed: Codex adapter/helper, steer dispatch and unsupported-provider cases,
installer packaging, summon skill, README/install guidance, protocol regression
tests and the owning shell suite. Unrelated Muse usage and Antigravity WIP remains
outside this task. Protocol fixtures cover idle/active/unloaded ownership,
permission restoration, malformed policy, denial, lost acknowledgement, literal
input, daemon startup, self-resume deadlock and explicit run settings.

Validation: clean staged package exported to
`/tmp/jamsession-message-validation.b419KF/jamsession` passed
`/bin/bash tests/test_jamsession.sh`: 484 passed, 0 failed, including all 20
protocol tests. Bash/sh syntax, Python compilation and all 11 skills passed
the skill creator validator. Real cold-start/read-only and workspace-write
tests passed. Reviewed staged consent wording, settings and failure paths;
no authorization is fabricated, approval policy disabled or native denial retried.

Handoff: default queue/start and separate steer are implemented for native
Codex control. Foreign desktop owners and unrepresentable saved permission
profiles remain explicit limitations, not claimed wake-ups. Only task-owned
changes are staged for publication; Muse usage and Antigravity WIP stays local.
