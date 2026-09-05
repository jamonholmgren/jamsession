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
3. Present one Markdown table row per usage window, in the command's provider order:

   | Provider | Window | Used | Remaining | Resets |
   | --- | --- | ---: | ---: | --- |

4. Use the provider name in title case, the window `label`, percentage signs on
   `used_percent` and `remaining_percent`, and `reset_display` as reported.
5. For a provider whose usage is unavailable, include one row with
   `Usage unavailable` in the Window column and em dashes elsewhere. Do not imply
   that the provider itself is unavailable or unauthenticated.
6. After the table, state how many providers returned usage out of the total.
   Mention unavailable providers in one concise sentence. Do not dump raw JSON
   unless the user asks for it.
