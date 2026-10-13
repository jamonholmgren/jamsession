# Antigravity adapter

Status: COMPLETE
Starting commit: 2414874f5e35acf0108c84844efa1ba8413d27fa

Jamon requested a bundled agy/Antigravity/Gemini adapter: new/resume, live model
catalog and Gemini 3.8 Flash effort variants, xhigh-to-high warning, usage and
aggregate status integration. Finish and publish task-owned work only.

## Findings and decisions

- Existing untracked adapter was incomplete and assumed JSONL storage.
- Installed agy auto-updated from 1.3.3 to 1.3.4 during native checks.
- Native `agy -p /usage` returns model-group quotas as TSV without a model turn.
  Gemini had 88% remaining; Claude/GPT 100% remaining. Preserve distinct buckets.
- Native conversations have SQLite stores with binary payloads. Recent runs
  also expose JSONL beneath `brain/<id>/.system_generated/logs`. `which` prefers
  that transcript, otherwise offers immutable schema inspection with an explicit
  export limitation. It never edits stores or removes locks.
- Plan mode is not enforced read-only. Keep `read` a hard error. `edit` remains
  explicit, unattended tool approval. Native messaging is unavailable; only
  explicit synchronous resume after the owner exits is supported.
- Models are validated against the live catalog; replace, never double effort
  suffixes. Generic/default Gemini selects 3.8 Flash. No quota/reset manipulation.
- Adapter authoring guidance lives in `make-adapter`'s generated script and
  bundled examples; changed README scaffold example to `myprovider`.

## Validation and publication

- Exact staged package exported to `/tmp/jamsession-agy-package.I6hOpP/jamsession`:
  `bash tests/test_jamsession.sh` passed 542 checks, zero failures. Includes ten
  quota-reader unit cases and existing Codex/session concurrency regressions.
- `bash -n`, `git diff --cached --check`, and skill-creator validation passed.
- Native Gemini new/resume succeeded in an empty temporary folder, with no
  tools or workspace writes. Conversation: `2df5c86e-3fa0-4ed2-9c91-320b49770945`.
  Native responses were `AGY_NEW_OK` and `AGY_RESUME_OK`; exact ID retained.
- Native usage/readiness and transcript lookup verified. Latest quota changed
  to Gemini 0% remaining, Claude/GPT 100% remaining. Gemini reset timestamp:
  `2026-10-20T06:59:20Z`. No further model turns or reset attempts.
- The quoted-workspace regression caught a Bash 3.2 escaping issue; SQL string
  escaping now uses sed, with literal substring matching rather than LIKE.
- Publish only this adapter, bundling/config, shared usage reader, docs/site,
  focused skills, regressions and worksheet. Preserve concurrent comparison
  work and the unfinished rankings; stage only the Antigravity catalog row.
