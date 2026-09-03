# Jam Session contributor instructions

Use concise plain English. Keep Jam Session small: Bash transport and optional
Markdown skills, not an orchestration daemon, session database, or framework.

When delegating repository work to an external coding agent, dogfood
`./jamsession` with an explicit provider, new or resumed session, model, effort,
access level, and prompt. Keep one write-capable agent per checkout. The primary
agent owns scope, integration, and final verification.

Preserve the positional run contract and strict workspace access semantics.
Never silently choose, downgrade, or substitute a model or effort. Model packs
are dated advice only and must not become execution defaults.

Before handoff, run:

```sh
/bin/bash -n jamsession adapters/* tests/test_jamsession.sh
/bin/sh -n install.sh
/bin/bash tests/test_jamsession.sh
```

Live provider checks consume quota and stay outside CI. Do not commit or push
unless the user explicitly authorizes it.
