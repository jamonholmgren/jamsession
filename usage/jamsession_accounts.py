#!/usr/bin/env python3
"""Named provider accounts for jamsession.

`~/.agents/jamsession/accounts.toml` lists `[provider.name]` tables. Each
table's `env` map is applied to that account's run only. `keychain_env` names
macOS Keychain items resolved at run time and passed only to that run. The
first account for a provider is the default. Sessions remember the account
that started them in `session-accounts.json`.

`kind = "api"` bills a headless run. `backend = "claude-cli"` is today's
Claude Code CLI. Another backend is refused until a runner exists.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
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
# Today's API-key runner. A different backend is unavailable on purpose.
CLAUDE_CLI_BACKEND = "claude-cli"
# Credentials a parent process (such as the Claude desktop app) can export.
# Claude prefers them over CLAUDE_CONFIG_DIR's own login, so an account run
# drops them first; the account's env and keychain_env still apply after.
AUTH_OVERRIDES = {
    "claude": (
        "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_OAUTH_REFRESH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR", "CLAUDE_CODE_API_KEY_FILE_DESCRIPTOR",
        "CLAUDE_CODE_SESSION_ACCESS_TOKEN", "CLAUDE_CODE_SESSIONS_OAUTH_TOKEN",
        "CLAUDE_CODE_GATEWAY_TOKEN", "CLAUDE_CODE_GATEWAY_TOKEN_FILE_DESCRIPTOR",
        "CLAUDE_CODE_HOST_AUTH_ENV_VAR", "CLAUDE_CODE_HOST_CREDS_FILE",
        "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH", "CLAUDE_CODE_SDK_HAS_OAUTH_REFRESH",
        "CLAUDE_CODE_ACCOUNT_UUID", "CLAUDE_CODE_ORGANIZATION_UUID", "CLAUDE_CODE_USER_EMAIL",
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_IDENTITY_TOKEN", "ANTHROPIC_IDENTITY_TOKEN_FILE",
    ),
}


def auth_overrides(provider: str) -> tuple[str, ...]:
    """Inherited variables an account run must not see."""
    return AUTH_OVERRIDES.get(canonical(provider), ())


class AccountError(Exception):
    pass


class Unavailable(Exception):
    """The account cannot run. Exit 75. The message never includes a secret."""


class KeychainMissing(Exception):
    def __init__(self, service: str):
        super().__init__(service)
        self.service = service


class KeychainUnsafe(Exception):
    def __init__(self, service: str):
        super().__init__(service)
        self.service = service


@dataclass
class Account:
    name: str
    env: dict[str, str]
    keychain_env: dict[str, str]
    monthly_budget_usd: float | None = None
    min_usage: float | None = None
    kind: str = ""
    backend: str = ""


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


def spend_path() -> Path:
    override = os.environ.get("JAMSESSION_SPEND")
    if override:
        return Path(override)
    return Path.home() / ".agents" / "jamsession" / "spend.json"


def usage_cache_path() -> Path:
    override = os.environ.get("JAMSESSION_USAGE_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "jamsession" / "usage.json"


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


def _string_map(path: Path, label: str, raw, *, expand: bool) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise AccountError(f"{path}: {label} must be a map of strings")
    found: dict[str, str] = {}
    for key, value in raw.items():
        if not ENV_KEY.fullmatch(str(key)) or not isinstance(value, str):
            raise AccountError(f"{path}: {label} {key} must be a named string")
        if "\n" in value or "\x00" in value or '"' in value or "\\" in value:
            raise AccountError(f"{path}: {label} {key} must be a single line")
        found[str(key)] = expand_value(value) if expand else value
    return found


def _budget(path: Path, label: str, raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise AccountError(f"{path}: {label}.monthly_budget_usd must be a number")
    if raw < 0:
        raise AccountError(f"{path}: {label}.monthly_budget_usd must not be negative")
    return float(raw)


def _min_usage(path: Path, label: str, raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise AccountError(f"{path}: {label}.min_usage must be a number")
    if raw < 0 or raw > 100:
        raise AccountError(f"{path}: {label}.min_usage must be from 0 to 100")
    return float(raw)


def load() -> dict[str, list[Account]]:
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
    found: dict[str, list[Account]] = {}
    for provider, accounts in table.items():
        if not NAME.fullmatch(str(provider)) or not isinstance(accounts, dict):
            raise AccountError(f"{path}: invalid provider table '{provider}'")
        provider = canonical(str(provider))
        for name, body in accounts.items():
            if not NAME.fullmatch(str(name)) or not isinstance(body, dict):
                raise AccountError(f"{path}: invalid account '{provider}.{name}'")
            label = f"{provider}.{name}"
            kind = str(body.get("kind") or "")
            backend = str(body.get("backend") or "")
            if kind and not NAME.fullmatch(kind):
                raise AccountError(f"{path}: {label}.kind is invalid")
            if backend and not NAME.fullmatch(backend):
                raise AccountError(f"{path}: {label}.backend is invalid")
            found.setdefault(provider, []).append(Account(
                name=str(name),
                env=_string_map(path, f"{label}.env", body.get("env"), expand=True),
                keychain_env=_string_map(path, f"{label}.keychain_env", body.get("keychain_env"), expand=False),
                monthly_budget_usd=_budget(path, label, body.get("monthly_budget_usd")),
                min_usage=_min_usage(path, label, body.get("min_usage")),
                kind=kind,
                backend=backend,
            ))
    return found


def names(provider: str) -> list[str]:
    return [account.name for account in load().get(canonical(provider), [])]


def default_account(provider: str) -> str:
    found = names(provider)
    return found[0] if found else ""


def min_usage_for(provider: str, account: str) -> float | None:
    """Per-account usage floor, or None when this account does not set one.

    An empty account is the provider's default. A missing accounts file is None.
    """
    provider = canonical(provider)
    group = load().get(provider, [])
    if not group:
        return None
    if not account:
        account = group[0].name
    for item in group:
        if item.name == account:
            return item.min_usage
    return None


def _account(provider: str, account: str) -> Account:
    provider = canonical(provider)
    if not account:
        account = default_account(provider)
    if not account:
        raise AccountError(f"{provider} has no accounts")
    for item in load().get(provider, []):
        if item.name == account:
            return item
    path = accounts_path()
    if not path.is_file():
        raise AccountError(f"{provider} has no account '{account}'; {path} is missing")
    known = ", ".join(names(provider)) or "none"
    raise AccountError(f"{provider} has no account '{account}'; known: {known}")


def env_for(provider: str, account: str) -> dict[str, str]:
    """Static env only. Keychain values are resolved for the run, not here."""
    provider = canonical(provider)
    if not account:
        account = default_account(provider)
    if not account:
        return {}
    return dict(_account(provider, account).env)


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


def read_keychain(service: str) -> str:
    """The Keychain password, with one trailing newline removed. Never logged."""
    if not service or any(char in service for char in "\n\r\x00"):
        raise KeychainMissing(service)
    binary = os.environ.get("JAMSESSION_SECURITY_BIN") or "security"
    try:
        result = subprocess.run(
            [binary, "find-generic-password", "-s", service, "-w"],
            capture_output=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        raise KeychainMissing(service) from None
    data = result.stdout
    if data.endswith(b"\r\n"):
        data = data[:-2]
    elif data.endswith(b"\n"):
        data = data[:-1]
    if result.returncode != 0 or data == b"":
        raise KeychainMissing(service)
    if b"\n" in data or b"\x00" in data:
        raise KeychainUnsafe(service)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise KeychainMissing(service) from None


def month_now() -> str:
    return datetime.datetime.now().astimezone().strftime("%Y-%m")


def _open_spend():
    path = spend_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    handle = os.fdopen(fd, "r+", encoding="utf-8")
    fcntl.flock(handle, fcntl.LOCK_EX)
    os.chmod(path, 0o600)
    return handle


def _read_spend(handle) -> dict:
    handle.seek(0)
    raw = handle.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AccountError(f"{spend_path()} is not valid JSON: {error}") from None
    if not isinstance(data, dict):
        raise AccountError(f"{spend_path()} is not a JSON object")
    return data


def _stored_number(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _lookup_spend(data: dict, provider: str, account: str, month: str) -> float:
    bucket = data.get(provider, {})
    if not isinstance(bucket, dict):
        return 0.0
    accounts = bucket.get(account, {})
    if not isinstance(accounts, dict):
        return 0.0
    return _stored_number(accounts.get(month, 0))


def month_spend(provider: str, account: str, month: str | None = None) -> float:
    provider = canonical(provider)
    if not spend_path().is_file():
        return 0.0
    handle = _open_spend()
    try:
        data = _read_spend(handle)
    finally:
        handle.close()
    return _lookup_spend(data, provider, account, month or month_now())


def _json_number(value: float):
    rounded = round(float(value), 6)
    if abs(rounded - round(rounded)) < 1e-9:
        return int(round(rounded))
    return rounded


def add_spend(provider: str, account: str, amount: float) -> float:
    provider = canonical(provider)
    if not account or not NAME.fullmatch(account):
        raise AccountError("spend needs an account")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise AccountError("cost must be a number")
    if amount < 0 or amount != amount or amount == float("inf"):
        raise AccountError("cost must be a finite number")
    handle = _open_spend()
    try:
        data = _read_spend(handle)
        month = month_now()
        current = _lookup_spend(data, provider, account, month)
        updated = _json_number(current + float(amount))
        data.setdefault(provider, {})
        if not isinstance(data[provider], dict):
            data[provider] = {}
        bucket = data[provider].setdefault(account, {})
        if not isinstance(bucket, dict):
            data[provider][account] = {}
            bucket = data[provider][account]
        bucket[month] = updated
        text = json.dumps(data, indent=2) + "\n"
        handle.seek(0)
        handle.write(text)
        handle.truncate()
        handle.flush()
    finally:
        handle.close()
    return float(updated)


def money(value: float) -> str:
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return f"${number:.0f}"
    return f"${number:.2f}"


def _load_usage_cache() -> dict:
    try:
        data = json.loads(usage_cache_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def cached_weekly_remaining(provider: str, account: str) -> float | None:
    """Remaining percent of the longest cached window, or None when unknown.

    Reads the usage cache only. It never runs `jamsession usage`.
    """
    provider = canonical(provider)
    rows = _load_usage_cache().get("providers")
    if not isinstance(rows, list):
        return None
    matched: list[dict] = []
    untagged: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("agent") != provider or row.get("status") != "ok":
            continue
        label = row.get("account") or ""
        if not isinstance(label, str):
            continue
        if label == account:
            matched.append(row)
        elif not label:
            untagged.append(row)
    chosen = matched
    if not chosen and account == default_account(provider):
        chosen = untagged
    windows = [window for row in chosen for window in (row.get("windows") or []) if isinstance(window, dict)]
    if not chosen:
        return None
    import jamsession_failover as failover
    return failover.governing_remaining(windows)


def _below_account_floor(provider: str, item: Account) -> bool:
    """True when the cached weekly remaining is below this account's own floor.

    No floor, a floor of 0, or an unknown cache does not skip. Remaining equal
    to the floor is still usable.
    """
    floor = item.min_usage
    if floor is None or floor <= 0:
        return False
    left = cached_weekly_remaining(provider, item.name)
    return left is not None and left < floor


def first_eligible(provider: str) -> str:
    """First account in file order still above its min_usage and budget.

    An unknown weekly figure does not skip. "" means none qualify.
    """
    provider = canonical(provider)
    for item in load().get(provider, []):
        try:
            reason = unavailable_reason(provider, item.name)
        except AccountError:
            continue
        if reason or _below_account_floor(provider, item):
            continue
        return item.name
    return ""


def _usage_bit(provider: str, item: Account) -> str:
    if item.monthly_budget_usd is not None:
        try:
            spent = month_spend(provider, item.name)
        except AccountError:
            return f"{item.name} ?"
        return f"{item.name} {money(spent)} of {money(item.monthly_budget_usd)}"
    left = cached_weekly_remaining(provider, item.name)
    if left is None:
        return f"{item.name} ?"
    return f"{item.name} {left:g}%"


def warn_bare(provider: str, named: str, session: str) -> str:
    """Warn when a bare provider has several accounts. Return the one to run.

    "" means do not change the caller's selection. A named account, a single
    account, a recorded session, and an internal failover step stay quiet.
    The returned name is not an explicit choice.
    """
    provider = canonical(provider)
    named = "" if named in ("", "-") else named
    if os.environ.get("JAMSESSION_FAILOVER_STEP"):
        return ""
    if named or os.environ.get(env_var(provider), ""):
        return ""
    group = load().get(provider, [])
    if len(group) < 2:
        return ""
    if session and session != "new" and lookup(provider, session):
        return ""
    chosen = first_eligible(provider) or group[0].name
    names = ", ".join(f"{provider}:{item.name}" for item in group)
    bits = ", ".join(_usage_bit(provider, item) for item in group)
    print(
        f"jamsession: several {provider} accounts are set up; "
        f"name one next time ({names}). "
        f"Weekly usage left: {bits}. "
        f"Using {provider}:{chosen}.",
        file=sys.stderr,
    )
    return chosen


def store_usage_report(raw: str) -> None:
    """Merge one usage report into the cache. A failure leaves the old cache.

    `jamsession usage` writes this so a later run can warn without a live read.
    Rows for providers in the new report replace older rows for those providers.
    """
    try:
        incoming = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(incoming, dict):
        return
    new_rows = incoming.get("providers")
    if not isinstance(new_rows, list):
        return
    path = usage_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        old_rows: list = []
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(old, dict) and isinstance(old.get("providers"), list):
                old_rows = old["providers"]
        except (OSError, json.JSONDecodeError, UnicodeError):
            old_rows = []
        replaced = {
            row.get("agent") for row in new_rows
            if isinstance(row, dict) and isinstance(row.get("agent"), str)
        }
        kept = [row for row in old_rows if not (isinstance(row, dict) and row.get("agent") in replaced)]
        fresh = [row for row in new_rows if isinstance(row, dict)]
        status = incoming.get("status") if isinstance(incoming.get("status"), str) else "partial"
        payload = {"schema_version": 1, "status": status, "providers": kept + fresh}
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)
    except OSError:
        return


def unavailable_reason(provider: str, account: str) -> str:
    """Why this account cannot run, or "" when it can. Never a secret."""
    provider = canonical(provider)
    if not account:
        account = default_account(provider)
    if not account:
        return ""
    item = _account(provider, account)
    if item.kind == "api" and item.backend not in ("", CLAUDE_CLI_BACKEND):
        return f"unknown backend '{item.backend}'"
    for service in item.keychain_env.values():
        try:
            read_keychain(service)  # discarded; the run resolves it again
        except KeychainUnsafe:
            return f"keychain item {service} is not a single line"
        except KeychainMissing:
            return f"keychain item {service} not found"
    if item.monthly_budget_usd is not None:
        spent = month_spend(provider, item.name)
        if spent >= item.monthly_budget_usd:
            return f"monthly budget reached: {money(spent)} of {money(item.monthly_budget_usd)}"
    return ""


def runtime_env(provider: str, account: str) -> dict[str, str]:
    """Env for one run, including Keychain values. Callers must not print it."""
    provider = canonical(provider)
    item = _account(provider, account)
    env = dict(item.env)
    for key, service in item.keychain_env.items():
        env[key] = read_keychain(service)
    if item.kind or item.backend:
        if item.kind:
            env["JAMSESSION_ACCOUNT_KIND"] = item.kind
        if item.backend or item.kind == "api":
            env["JAMSESSION_ACCOUNT_BACKEND"] = item.backend or CLAUDE_CLI_BACKEND
        env["JAMSESSION_ACCOUNT_NAME"] = item.name
        env["JAMSESSION_ACCOUNT_PROVIDER"] = provider
    return env


def prepare(kind: str, provider: str, session: str, named: str) -> tuple[str, bool, dict[str, str]]:
    """Return `(account, record_when_session_prints, env)`.

    `named` is the account from `provider:account`, or `-` when absent.
    Resume, message and steer of a recorded session reuse that account.
    Naming a different one is refused. An explicit account on an unrecorded
    session is remembered. A new session is remembered when its id is printed.
    The env may contain Keychain secrets. The caller must not echo it.
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
        # A bare provider with several accounts runs the first one still above
        # its floor and budget. That pick is not an explicit name, so it does
        # not latch onto an unrecorded session.
        hinted = warn_bare(provider, named, session)
        if hinted:
            account = hinted
        latch = bool(explicit and account and kind != "new" and session not in ("", "new"))
    if latch:
        record(provider, session, account)
    env: dict[str, str] = {}
    if account:
        reason = unavailable_reason(provider, account)
        if reason:
            raise Unavailable(f"{provider}:{account} is unavailable: {reason}")
        try:
            env = runtime_env(provider, account)
        except KeychainUnsafe as error:
            raise Unavailable(
                f"{provider}:{account} is unavailable: keychain item {error.service} is not a single line") from None
        except KeychainMissing as error:
            raise Unavailable(
                f"{provider}:{account} is unavailable: keychain item {error.service} not found") from None
    remember = kind == "new" and bool(account)
    return account, remember, env


def overlays(provider: str, session: str = "") -> list[dict[str, str]]:
    """Static env for every account, recorded account first. At least one entry.

    Keychain secrets are not included. History lookup must not resolve them.
    """
    found = load().get(canonical(provider), [])
    if not found:
        return [{}]
    recorded = lookup(provider, session)
    ordered = sorted(found, key=lambda item: item.name != recorded) if recorded else list(found)
    return [dict(account.env) for account in ordered]


def budget_fragment(provider: str, account: str) -> str:
    """A JSON snippet for a usage row, or "" when the account has no budget."""
    item = _account(provider, account)
    if item.monthly_budget_usd is None:
        return ""
    payload = {
        "month": month_now(),
        "usd": _json_number(month_spend(provider, item.name)),
        "budget_usd": _json_number(item.monthly_budget_usd),
    }
    return ',"spend":' + json.dumps(payload, separators=(",", ":"))


def _coerce_cost(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _consider_cost(obj: dict, state: dict) -> None:
    for key in ("total_cost_usd", "cost_usd", "total_cost"):
        number = _coerce_cost(obj.get(key))
        if number is not None:
            state["cost"] = number
    usage = obj.get("usage")
    if isinstance(usage, dict) and state["cost"] is None:
        for key in ("total_cost_usd", "cost_usd"):
            number = _coerce_cost(usage.get(key))
            if number is not None:
                state["cost"] = number
    if obj.get("type") == "result" and isinstance(obj.get("result"), str):
        state["text"] = obj["result"]


def parse_claude_cost(raw: str) -> tuple[str | None, float | None]:
    """Result text and cost from Claude's JSON output. The text may be None."""
    objects: list[dict] = []
    stripped = raw.strip()
    parsed = None
    if stripped:
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
    if isinstance(parsed, dict):
        objects = [parsed]
    elif isinstance(parsed, list):
        objects = [item for item in parsed if isinstance(item, dict)]
    elif stripped:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                objects.append(item)
    state: dict = {"text": None, "cost": None}
    for obj in objects:
        _consider_cost(obj, state)
    return state["text"], state["cost"]


def claude_cost(provider: str, account: str, source: str, dest: str) -> None:
    """Write the result text and, when Claude reported a cost, add it to the month."""
    raw = Path(source).read_text(encoding="utf-8", errors="replace")
    text, cost = parse_claude_cost(raw)
    shown = raw if text is None else text
    if shown and not shown.endswith("\n"):
        shown += "\n"
    Path(dest).write_text(shown, encoding="utf-8")
    if account and cost is not None and cost >= 0:
        add_spend(provider, account, cost)


def _usage_helper() -> Path:
    path = Path(__file__).resolve().parent / "jamsession_usage"
    if path.is_file():
        return path
    raise AccountError("usage helper is not installed")


def _usage_rows(provider: str) -> list[dict] | None:
    try:
        result = subprocess.run(
            [str(_usage_helper()), provider, "--json"],
            capture_output=True, text=True, timeout=25, env=os.environ.copy(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    rows = report.get("providers")
    return rows if isinstance(rows, list) else None


def _match_row(rows: list[dict] | None, provider: str, account: str, default: str) -> dict | None:
    if rows is None:
        return None
    tagged = [row for row in rows if row.get("agent") == provider and row.get("account") == account]
    if tagged:
        return tagged[0]
    if account == default:
        untagged = [row for row in rows if row.get("agent") == provider and not row.get("account")]
        if untagged:
            return untagged[0]
    return None


def _usage_summary(row: dict | None) -> str:
    if row is None:
        return "usage: unread"
    if row.get("status") != "ok":
        message = ""
        error = row.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        return "usage: unavailable" + (f" ({message})" if message else "")
    parts = []
    for window in row.get("windows") or []:
        if not isinstance(window, dict):
            continue
        remaining = window.get("remaining_percent")
        label = window.get("label") or "window"
        if isinstance(remaining, (int, float)) and not isinstance(remaining, bool):
            parts.append(f"{remaining:g}% remaining, {label}")
    if not parts:
        return "usage: unavailable"
    return "usage: " + "; ".join(parts)


def command_list(args: list[str]) -> None:
    loaded = load()
    if len(args) > 1:
        raise AccountError("accounts list takes at most one provider")
    if args:
        provider = canonical(args[0])
        loaded = {provider: loaded.get(provider, [])}
    selected = [(provider, group) for provider, group in loaded.items() if group]
    if not selected:
        return
    for provider, group in selected:
        rows = _usage_rows(provider)
        default = group[0].name
        for account in group:
            print(f"{provider} {account.name}")
            print("  " + _usage_summary(_match_row(rows, provider, account.name, default)))
            if account.monthly_budget_usd is not None:
                spent = month_spend(provider, account.name)
                print(f"  spend: {money(spent)} of {money(account.monthly_budget_usd)} this month")


def _toml_string(value: str) -> str:
    if any(char in value for char in "\n\r\x00\"\\"):
        raise AccountError("account values must be a single line without quotes")
    return f'"{value}"'


def _toml_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _inline_table(mapping: dict[str, str]) -> str:
    parts = [f"{key} = {_toml_string(value)}" for key, value in mapping.items()]
    return "{ " + ", ".join(parts) + " }"


def _config_dir(provider: str) -> Path:
    key = "CLAUDE_CONFIG_DIR" if provider == "claude" else "CODEX_HOME"
    fallback = Path.home() / (".claude" if provider == "claude" else ".codex")
    found = load().get(provider, [])
    if found and found[0].env.get(key):
        return Path(found[0].env[key])
    return fallback


def _link_from_default(provider: str, dest: Path) -> None:
    source = _config_dir(provider)
    names = ("settings.json", "skills") if provider == "claude" else ("config.toml",)
    for name in names:
        origin = source / name
        target = dest / name
        if not origin.exists() and not origin.is_symlink():
            continue
        if target.exists() or target.is_symlink():
            continue
        target.symlink_to(origin)


def _install_claude_wrapper(name: str) -> None:
    bindir = Path.home() / ".local" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    wrapper = bindir / f"claude-{name}"
    if wrapper.exists():
        current = wrapper.read_text(encoding="utf-8", errors="replace")
        if "jamsession account wrapper" not in current.splitlines()[:3]:
            raise AccountError(f"{wrapper} already exists")
    script = (
        "#!/bin/sh\n"
        "# jamsession account wrapper\n"
        f"unset {' '.join(auth_overrides('claude'))}\n"
        f'export CLAUDE_CONFIG_DIR="$HOME/.claude-{name}"\n'
        'exec claude "$@"\n'
    )
    wrapper.write_text(script, encoding="utf-8")
    os.chmod(wrapper, 0o755)


def _append_toml(block: str) -> None:
    path = accounts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    handle = os.fdopen(fd, "r+", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        os.chmod(path, 0o600)
        existing = handle.read()
        if not existing.strip():
            existing = "# Provider accounts. The first account for a provider is the default.\n"
        elif not existing.endswith("\n"):
            existing += "\n"
        if not existing.endswith("\n\n"):
            existing += "\n"
        handle.seek(0)
        handle.write(existing + block)
        if not block.endswith("\n"):
            handle.write("\n")
        handle.truncate()
        handle.flush()
    finally:
        handle.close()


def command_add(args: list[str]) -> None:
    if len(args) < 2:
        raise AccountError("accounts add needs <provider> <name>")
    provider, name = canonical(args[0]), args[1]
    if provider not in ("claude", "codex"):
        raise AccountError("accounts add supports claude and codex")
    if not NAME.fullmatch(name):
        raise AccountError(f"invalid account '{name}'")
    link = False
    kind = ""
    backend = ""
    budget: float | None = None
    keychain: dict[str, str] = {}
    index = 2
    while index < len(args):
        flag = args[index]
        if flag == "--link":
            link = True
            index += 1
            continue
        if index + 1 >= len(args):
            raise AccountError(f"{flag} needs a value")
        value = args[index + 1]
        if flag == "--kind":
            kind = value
        elif flag == "--backend":
            backend = value
        elif flag == "--budget":
            try:
                budget = float(value)
            except ValueError:
                raise AccountError("--budget needs a number of usd") from None
            if budget < 0:
                raise AccountError("--budget must not be negative")
        elif flag == "--keychain":
            key, separator, service = value.partition("=")
            if not separator or not ENV_KEY.fullmatch(key) or not service:
                raise AccountError("--keychain needs KEY=service")
            if any(char in service for char in "\n\r\x00\"\\"):
                raise AccountError("--keychain service must be a single line")
            keychain[key] = service
        else:
            raise AccountError(f"unknown accounts add option '{flag}'")
        index += 2
    if kind and not NAME.fullmatch(kind):
        raise AccountError(f"invalid kind '{kind}'")
    if backend and not NAME.fullmatch(backend):
        raise AccountError(f"invalid backend '{backend}'")
    if kind == "api" and not keychain:
        raise AccountError("an api account needs --keychain KEY=service")
    if kind == "api" and not backend:
        backend = CLAUDE_CLI_BACKEND
    if accounts_path().is_file() and name in names(provider):
        raise AccountError(f"{provider} already has an account '{name}'")
    folder = f".claude-{name}" if provider == "claude" else f".codex-{name}"
    dest = Path.home() / folder
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    if link:
        _link_from_default(provider, dest)
    if provider == "claude" and kind != "api":
        _install_claude_wrapper(name)
    env_key = "CLAUDE_CONFIG_DIR" if provider == "claude" else "CODEX_HOME"
    lines = [f"[{provider}.{name}]"]
    if kind:
        lines.append(f"kind = {_toml_string(kind)}")
    if backend:
        lines.append(f"backend = {_toml_string(backend)}")
    if budget is not None:
        lines.append(f"monthly_budget_usd = {_toml_number(budget)}")
    lines.append(f"env = {_inline_table({env_key: '~/' + folder})}")
    if keychain:
        lines.append(f"keychain_env = {_inline_table(keychain)}")
    _append_toml("\n".join(lines) + "\n")
    if provider == "claude" and kind != "api":
        print(f"claude-{name}")
        return
    if kind == "api":
        service = next(iter(keychain.values()))
        print(f"security add-generic-password -s {service} -a $USER -w")
        return
    print(f"CODEX_HOME=~/{folder} codex login")


def main(argv: list[str]) -> int:
    if not argv:
        raise AccountError("usage: jamsession_accounts.py <prepare|record|names|list|env|add|store-usage>")
    command, args = argv[0], argv[1:]
    if command == "prepare":
        if len(args) != 4:
            raise AccountError("prepare needs <new|resume|message|steer> <provider> <session> <account|->")
        account, remember, env = prepare(*args)
        # stdout is captured by the CLI and must not be echoed: it may hold a secret.
        print(f"account {account}")
        print(f"record {1 if remember else 0}")
        if account:
            for key in auth_overrides(args[1]):
                print(f"unset {key}")
        for key, value in env.items():
            print(f"env {key}={value}")
        return 0
    if command == "record":
        if len(args) != 3:
            raise AccountError("record needs <provider> <session> <account>")
        record(*args)
        return 0
    if command == "names":
        if len(args) != 1:
            raise AccountError("names needs <provider>")
        for name in names(args[0]):
            print(name)
        return 0
    if command == "list":
        command_list(args)
        return 0
    if command == "add":
        command_add(args)
        return 0
    if command == "env":
        if len(args) != 2:
            raise AccountError("env needs <provider> <account>")
        for key, value in env_for(*args).items():
            print(f"{key}={value}")
        return 0
    if command == "auth-overrides":
        if len(args) != 1:
            raise AccountError("auth-overrides needs <provider>")
        for key in auth_overrides(args[0]):
            print(key)
        return 0
    if command == "budget-fragment":
        if len(args) != 2:
            raise AccountError("budget-fragment needs <provider> <account>")
        sys.stdout.write(budget_fragment(*args))
        return 0
    if command == "spend":
        if len(args) != 3:
            raise AccountError("spend needs <provider> <account> <usd>")
        try:
            amount = float(args[2])
        except ValueError:
            raise AccountError("spend needs a number of usd") from None
        add_spend(args[0], args[1], amount)
        return 0
    if command == "store-usage":
        if args:
            raise AccountError("store-usage reads the report on stdin")
        store_usage_report(sys.stdin.read())
        return 0
    if command == "claude-cost":
        if len(args) != 4:
            raise AccountError("claude-cost needs <provider> <account> <json-file> <text-file>")
        claude_cost(*args)
        return 0
    raise AccountError(f"unknown accounts command '{command}'")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Unavailable as error:
        print(f"jamsession: {error}", file=sys.stderr)
        sys.exit(75)
    except AccountError as error:
        print(f"jamsession: {error}", file=sys.stderr)
        sys.exit(2)
