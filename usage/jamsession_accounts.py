#!/usr/bin/env python3
"""Named provider accounts for jamsession.

`~/.agents/jamsession/accounts.toml` lists `[provider.name]` tables. Each
table's `env` map is applied to that account's run only. The first account
for a provider is the default. Sessions remember the account that started
them in `session-accounts.json`.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import sys

try:
    import tomllib
except ImportError:  # Python before 3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

NAME = re.compile(r"^[A-Za-z0-9_-]+$")
ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALIASES = {"agy": "antigravity", "gemini": "antigravity"}


class AccountError(Exception):
    pass


def accounts_path() -> Path:
    override = os.environ.get("JAMSESSION_ACCOUNTS")
    if override:
        return Path(override)
    return Path.home() / ".agents" / "jamsession" / "accounts.toml"


def sessions_path() -> Path:
    override = os.environ.get("JAMSESSION_SESSION_ACCOUNTS")
    if override:
        return Path(override)
    return Path.home() / ".agents" / "jamsession" / "session-accounts.json"


def env_var(provider: str) -> str:
    return f"JAMSESSION_{provider.upper()}_ACCOUNT"


def canonical(provider: str) -> str:
    if not NAME.fullmatch(provider or ""):
        raise AccountError(f"invalid provider '{provider}'")
    return ALIASES.get(provider, provider)


def split_spec(spec: str) -> tuple[str, str]:
    """`provider` or `provider:account`."""
    if spec.count(":") > 1 or spec.endswith(":"):
        raise AccountError(f"invalid provider account '{spec}'")
    if ":" in spec:
        provider, account = spec.split(":", 1)
        if not NAME.fullmatch(account):
            raise AccountError(f"invalid account '{account}'")
        return canonical(provider), account
    return canonical(spec), ""


def expand_value(value: str) -> str:
    if "\n" in value or "\x00" in value:
        raise AccountError("account env values must be a single line")
    return os.path.expanduser(value) if value.startswith("~") else value


def load() -> dict[str, list[tuple[str, dict[str, str]]]]:
    """Accounts in file order. A missing file is no accounts."""
    path = accounts_path()
    if not path.is_file():
        return {}
    if tomllib is None:
        raise AccountError("reading accounts.toml needs Python 3.11 or newer (or the tomli package)")
    try:
        table = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise AccountError(f"cannot read {path}: {error.strerror}") from None
    except tomllib.TOMLDecodeError as error:
        raise AccountError(f"{path}: {error}") from None
    if not isinstance(table, dict):
        raise AccountError(f"{path}: expected provider tables")
    found: dict[str, list[tuple[str, dict[str, str]]]] = {}
    for provider, accounts in table.items():
        if not NAME.fullmatch(str(provider)) or not isinstance(accounts, dict):
            raise AccountError(f"{path}: invalid provider table '{provider}'")
        provider = canonical(str(provider))
        for name, body in accounts.items():
            if not NAME.fullmatch(str(name)) or not isinstance(body, dict):
                raise AccountError(f"{path}: invalid account '{provider}.{name}'")
            raw = body.get("env", {})
            if not isinstance(raw, dict):
                raise AccountError(f"{path}: {provider}.{name}.env must be a map of strings")
            env: dict[str, str] = {}
            for key, value in raw.items():
                if not ENV_KEY.fullmatch(str(key)) or not isinstance(value, str):
                    raise AccountError(f"{path}: {provider}.{name}.env {key} must be a named string")
                env[str(key)] = expand_value(value)
            found.setdefault(provider, []).append((str(name), env))
    return found


def names(provider: str) -> list[str]:
    return [name for name, _env in load().get(canonical(provider), [])]


def default_account(provider: str) -> str:
    found = names(provider)
    return found[0] if found else ""


def env_for(provider: str, account: str) -> dict[str, str]:
    provider = canonical(provider)
    if not account:
        account = default_account(provider)
    if not account:
        return {}
    for name, env in load().get(provider, []):
        if name == account:
            return env
    path = accounts_path()
    if not path.is_file():
        raise AccountError(f"{provider} has no account '{account}'; {path} is missing")
    known = ", ".join(names(provider)) or "none"
    raise AccountError(f"{provider} has no account '{account}'; known: {known}")


def resolve(provider: str, named: str) -> str:
    """The account the user named, or '' to mean the default pool.

    A CLI `provider:account` and `JAMSESSION_<PROVIDER>_ACCOUNT` that disagree
    are refused. An empty result does not mean the name failed to resolve.
    """
    provider = canonical(provider)
    selected = os.environ.get(env_var(provider), "")
    if named and selected and named != selected:
        raise AccountError(f"{env_var(provider)}={selected} does not match {provider}:{named}")
    chosen = named or selected
    if not chosen:
        return ""
    if not NAME.fullmatch(chosen):
        raise AccountError(f"invalid account '{chosen}'")
    if chosen not in names(provider):
        path = accounts_path()
        if not path.is_file():
            raise AccountError(f"{provider} has no account '{chosen}'; {path} is missing")
        known = ", ".join(names(provider)) or "none"
        raise AccountError(f"{provider} has no account '{chosen}'; known: {known}")
    return chosen


def pools_match(left: str, right: str, provider: str) -> bool:
    """True when two labels are one usage pool.

    An empty label is the default account when the provider has accounts,
    and the single unscoped pool when it does not.
    """
    left, right = left or "", right or ""
    if left == right:
        return True
    default = default_account(provider)
    if not default:
        return False
    return (left or default) == (right or default)


def _open_sessions():
    path = sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Not O_APPEND: a rewrite must replace the object, not append a second one.
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    handle = os.fdopen(fd, "r+", encoding="utf-8")
    fcntl.flock(handle, fcntl.LOCK_EX)
    os.chmod(path, 0o600)
    raw = handle.read()
    if not raw.strip():
        return handle, {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        handle.close()
        raise AccountError(f"{path} is not valid JSON: {error}") from None
    if not isinstance(data, dict):
        handle.close()
        raise AccountError(f"{path} is not a JSON object")
    return handle, data


def lookup(provider: str, session: str) -> str:
    if not session or session == "new" or not sessions_path().is_file():
        return ""
    try:
        data = json.loads(sessions_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    bucket = data.get(canonical(provider), {}) if isinstance(data, dict) else {}
    account = bucket.get(session, "") if isinstance(bucket, dict) else ""
    return account if isinstance(account, str) else ""


def record(provider: str, session: str, account: str) -> None:
    provider = canonical(provider)
    if not session or session == "new" or not account:
        raise AccountError("a session account needs a provider, session and account")
    if account not in names(provider):
        raise AccountError(f"{provider} has no account '{account}'")
    handle, data = _open_sessions()
    try:
        bucket = data.setdefault(provider, {})
        if not isinstance(bucket, dict):
            raise AccountError(f"session accounts for {provider} are not an object")
        current = bucket.get(session, "")
        if current and current != account:
            raise AccountError(
                f"session {session} is on the {provider} account {current}; refusing account {account}")
        if current == account:
            return
        bucket[session] = account
        text = json.dumps(data, indent=2) + "\n"
        handle.seek(0)
        handle.write(text)
        handle.truncate()
        handle.flush()
    finally:
        handle.close()


def prepare(kind: str, provider: str, session: str, named: str) -> tuple[str, bool, dict[str, str]]:
    """Return `(account, record_when_session_prints, env)`.

    `named` is the account from `provider:account`, or `-` when absent.
    Resume, message and steer of a recorded session reuse that account.
    Naming a different one is refused. An explicit account on an unrecorded
    session is remembered. A new session is remembered when its id is printed.
    """
    provider = canonical(provider)
    named = "" if named in ("", "-") else named
    chosen = resolve(provider, named)
    explicit = bool(named or os.environ.get(env_var(provider), ""))
    recorded = "" if kind == "new" or session == "new" else lookup(provider, session)
    if recorded:
        if explicit and chosen != recorded:
            raise AccountError(
                f"session {session} is on the {provider} account {recorded}; refusing account {chosen}")
        account = recorded
        latch = False
    else:
        account = chosen or default_account(provider)
        latch = bool(explicit and account and kind != "new" and session not in ("", "new"))
    if latch:
        record(provider, session, account)
    env = env_for(provider, account) if account else {}
    remember = kind == "new" and bool(account)
    return account, remember, env


def overlays(provider: str, session: str = "") -> list[dict[str, str]]:
    """Env for every account, recorded account first. At least one entry."""
    found = load().get(canonical(provider), [])
    if not found:
        return [{}]
    recorded = lookup(provider, session)
    ordered = sorted(found, key=lambda item: item[0] != recorded) if recorded else found
    return [env for _name, env in ordered]


def main(argv: list[str]) -> int:
    if not argv:
        raise AccountError("usage: jamsession_accounts.py <prepare|record|list|env>")
    command, args = argv[0], argv[1:]
    if command == "prepare":
        if len(args) != 4:
            raise AccountError("prepare needs <new|resume|message|steer> <provider> <session> <account|->")
        account, remember, env = prepare(*args)
        print(f"account {account}")
        print(f"record {1 if remember else 0}")
        for key, value in env.items():
            print(f"env {key}={value}")
        return 0
    if command == "record":
        if len(args) != 3:
            raise AccountError("record needs <provider> <session> <account>")
        record(*args)
        return 0
    if command == "list":
        if len(args) != 1:
            raise AccountError("list needs <provider>")
        for name in names(args[0]):
            print(name)
        return 0
    if command == "env":
        if len(args) != 2:
            raise AccountError("env needs <provider> <account>")
        for key, value in env_for(*args).items():
            print(f"{key}={value}")
        return 0
    raise AccountError(f"unknown accounts command '{command}'")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except AccountError as error:
        print(f"jamsession: {error}", file=sys.stderr)
        sys.exit(2)
