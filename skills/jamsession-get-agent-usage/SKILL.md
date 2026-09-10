---
name: jamsession-get-agent-usage
description: Report current usage, remaining quota, rate-limit windows, and reset times for one or all Jam Session coding-agent providers. Use when the user asks for agent usage, limits, remaining capacity, quota, or reset times. Do not use for a general installation or authentication check unless usage is also requested.
---

# Get Agent Usage

1. Run `jamsession usage --json` for all providers, or `jamsession usage
   <provider> --json` when the user names one provider. Use `usage`, not `status`,
   because this task needs structured quota data rather than readiness diagnostics.
2. Treat exit status 2 as a valid partial result and format every provider returned.
   If the command produces no valid JSON, report the command failure plainly.
3. Omit session windows and Codex Spark primary/secondary windows. Present the
   remaining useful quota windows in command provider order:

   | Provider | Window | Remaining | Resets |
   | --- | --- | ---: | --- |

4. Use title-case provider names, concise window labels, and percentage signs on
   `remaining_percent`. Do not show `used_percent`. Keep `gpt-reserve`; it is the
   Codex `base_model_inference` weekly bucket, although Codex does not expose which
   exact models or fallback path consume it. Label Claude's useful windows
   `All Models (weekly)` and `Fable (weekly)`. Show a provider name only on its
   first row when it has multiple windows.
5. Normalize every reset to Pacific time. Format dates as `Sept 14 (in 7 days)`.
   For today or tomorrow only, add the compact reset time, such as
   `Sept 8 (tomorrow @ 9:12pm)`. Use calendar-day differences, not elapsed
   24-hour periods. Cursor's monthly plan resets on the 21st; when its CLI does
   not expose a reset, use the next applicable 21st and calculate the day count.
6. For a provider whose usage is unavailable, include one row with
   `Usage unavailable` in the Window column and em dashes elsewhere. Do not imply
   that the provider itself is unavailable or unauthenticated. Grok collection
   opens its supported interactive `/usage` modal through a local Python PTY; do
   not substitute model-reported usage, session-token counts, or a private API.
7. After the table, state how many providers returned usage out of the total.
   Mention unavailable providers in one concise sentence. If diagnostics show
   why collection failed, state that briefly; distinguish an unreadable usage
   screen from an authentication failure. Do not dump raw JSON unless asked.
