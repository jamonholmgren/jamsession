#!/usr/bin/env python3
"""Tier-based failover, routes and the tiers table for jamsession.

Only a provider refusal (adapter exit 75: a spend, usage or rate limit, a quota,
or an auth failure) moves a run to the next candidate. Candidates are the same
model through its other harnesses, then the rest of its tier; a later (cheaper)
tier only with --allow-lower, and never an earlier one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, replace

# Accounts live beside this file when installed (bin/) and in the repo (usage/).
_ACCOUNTS_DIR = str(Path(__file__).resolve().parent)
if _ACCOUNTS_DIR not in sys.path:
    sys.path.insert(0, _ACCOUNTS_DIR)
import jamsession_accounts as accounts  # noqa: E402

REFUSAL = 75
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
# Adapters that refuse read access outright; failover skips them for read runs.
EDIT_ONLY = {"devin", "copilot", "antigravity"}
DEFAULT_MIN_USAGE = 25.0
# A 5-hour Claude session is 300 minutes. Anything up to 6 hours is that short
# window. Weekly is 7 days; a monthly window is longer than that.
SHORT_WINDOW_MINUTES = 360
WEEKLY_WINDOW_MINUTES = 10080

try:
    import tomllib
except ImportError:  # Python before 3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


class Failure(Exception):
    pass


class Unresolved(Failure):
    """`<family>@latest` has no ID on this harness, or its listing failed with nothing cached."""


# `<family>@latest` resolves per harness to the newest ID its `models` listing
# shows. An ID must be exactly the family pattern plus an optional effort
# suffix, so fast, lightning, mini, thinking, 1m and "default" never qualify.
_VERSION = r"(\d+(?:[.-]\d+)*)"
_EFFORT = r"(?:-(?:none|minimal|low|medium|high|xhigh|max|ultra))?"
FAMILIES = {name: re.compile(pattern.replace("V", _VERSION) + _EFFORT) for name, pattern in {
    "fable": "claude-fable-V", "opus": "claude-opus-V", "sonnet": "claude-sonnet-V", "haiku": "claude-haiku-V",
    "astra": "gpt-V-astra", "sol": "gpt-V-sol", "terra": "gpt-V-terra", "luna": "gpt-V-luna",
    "grok": "grok-V", "wonder": "muse-wonder-V", "spark": "muse-spark-V",
    "swe-2": "swe-V", "swe-2-flash": "swe-V-flash",
}.items()}
FAMILY_ALIASES = {"swe": "swe-2", "swe-flash": "swe-2-flash"}
LATEST_TTL = 3600.0


def family_name(model: str) -> str:
    """The family of `<family>@latest`, or "" for a concrete ID."""
    if "@" not in model:
        return ""
    family, tag = model.split("@", 1)
    family = FAMILY_ALIASES.get(family.lower(), family.lower())
    if tag != "latest" or family not in FAMILIES:
        raise Failure(f"unknown model '{model}'; use <family>@latest with one of: {', '.join(FAMILIES)}")
    return family


def family_of_id(model: str) -> str:
    key = model.strip().lower()
    return next((name for name, pattern in FAMILIES.items() if pattern.fullmatch(key)), "")


def newest(listing: str, family: str) -> str:
    """The newest ID in a harness's model listing for `family`, without its effort suffix."""
    pattern, best, best_version = FAMILIES[family], "", ()
    for token in re.findall(r"[a-z0-9][a-z0-9._-]*", listing.lower()):
        match = pattern.fullmatch(token)
        if not match:
            continue
        version = tuple(int(part) for part in re.split(r"[.-]", match.group(1)))
        if version > best_version:
            best, best_version = re.sub(r"-(none|minimal|low|medium|high|xhigh|max|ultra)$", "", token), version
    return best


class Latest:
    """Resolves `<family>@latest` per harness, caching results for LATEST_TTL seconds.
    A failed listing falls back to the last resolved value, however old."""

    def __init__(self, path: Path | None = None, ttl: float | None = None, lister=None):
        self.path = path or Path(os.environ.get("JAMSESSION_LATEST_CACHE")
                                 or os.path.expanduser("~/.cache/jamsession/latest-models.json"))
        self.ttl = float(os.environ.get("JAMSESSION_LATEST_TTL", LATEST_TTL)) if ttl is None else ttl
        self.lister = lister or list_models
        self.listings: dict[str, str | None] = {}

    def load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self, cache: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            pass  # a resolution that cannot be cached is still right for this run

    def resolve(self, harness: str, model: str) -> str:
        family = family_name(model)
        if not family:
            return model
        key = f"{harness}/{family}"
        cache = self.load()
        entry = cache.get(key)
        if entry and time.time() - float(entry.get("at", 0)) < self.ttl:
            return entry["id"]
        if harness not in self.listings:
            try:
                self.listings[harness] = self.lister(harness)
            except (OSError, subprocess.SubprocessError, Failure):
                self.listings[harness] = None
        listing = self.listings[harness]
        if listing is None:
            if entry:
                print(f"note: could not list {harness} models; using last resolved {family}@latest = {entry['id']}",
                      file=sys.stderr)
                return entry["id"]
            raise Unresolved(f"could not list {harness} models to resolve {model}, and none is cached")
        found = newest(listing, family)
        if not found:
            raise Unresolved(f"{harness} does not serve {family}")
        cache[key] = {"id": found, "at": time.time()}
        self.save(cache)
        return found


def list_models(harness: str) -> str:
    adapter_dir = os.environ.get("JAMSESSION_ADAPTER_DIR") or str(Path(__file__).resolve().parent.parent / "adapters")
    adapter = Path(adapter_dir) / f"jamsession_{harness}"
    command = [str(adapter), "models"] if adapter.is_file() else [os.environ.get("JAMSESSION_CLI", "jamsession"), "models", harness]
    # Adapters find their helpers through JAMSESSION_HOME, which the CLI normally exports.
    env = dict(os.environ, JAMSESSION_HOME=os.environ.get("JAMSESSION_HOME") or str(Path(adapter_dir).parent))
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0 or not result.stdout.strip():
        raise Failure(f"{harness} model listing failed")
    return result.stdout


@dataclass
class Candidate:
    provider: str
    model: str
    effort: str
    meter: bool = True
    name: str = ""  # tiers-table model name, when known
    tier: str = ""
    account: str = ""  # empty means the provider's default account, if it has one

    def provider_arg(self) -> str:
        return f"{self.provider}:{self.account}" if self.account else self.provider

    def label(self) -> str:
        return f"{self.provider_arg()} {self.model} {self.effort}"


def load_toml(path: Path) -> dict:
    if tomllib is None:
        raise Failure("reading TOML needs Python 3.11 or newer (or the tomli package)")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise Failure(f"cannot read {path}: {error.strerror}") from None
    except tomllib.TOMLDecodeError as error:
        raise Failure(f"{path}: {error}") from None


def tiers_path() -> Path:
    if os.environ.get("JAMSESSION_TIERS"):
        return Path(os.environ["JAMSESSION_TIERS"])
    here = Path(__file__).resolve().parent
    for candidate in (Path(os.environ.get("JAMSESSION_HOME", "")) / "tiers.toml", here.parent / "tiers.toml"):
        if candidate.is_file():
            return candidate
    raise Failure("tiers table not found; reinstall Jam Session or set JAMSESSION_TIERS")


def load_tiers(path: Path | None = None) -> dict:
    path = path or tiers_path()
    table = load_toml(path)
    tiers = table.get("tiers")
    models = table.get("model", {})
    if not isinstance(tiers, list) or not tiers:
        raise Failure(f"{path}: needs a tiers list")
    seen: set[str] = set()
    for tier in tiers:
        for name in tier.get("models", []):
            if name in seen:
                raise Failure(f"{path}: model '{name}' is in more than one tier")
            vias = models.get(name, {}).get("via")
            if not vias:
                raise Failure(f"{path}: model '{name}' has no [model.{name}] via list")
            for via in vias:
                account = via.get("account", "")
                if account and (not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", account)):
                    raise Failure(f"{path}: model '{name}' has an invalid via account '{account}'")
            seen.add(name)
    extra = set(models) - seen
    if extra:
        raise Failure(f"{path}: models not in any tier: {', '.join(sorted(extra))}")
    return table


def normalize(model: str) -> tuple[str, str]:
    """A comparable model key and any effort folded into the ID (Cursor, Devin)."""
    text = model.strip().lower()
    picker = re.fullmatch(r"(opus|sonnet|haiku|fable)[ -](\d+(?:\.\d+)?)", text)
    if picker:
        text = f"claude-{picker.group(1)}-{picker.group(2)}"
    text = re.sub(r"[._ ]", "-", text)
    text = re.sub(r"-fast$", "", text)
    effort = ""
    for suffix in EFFORTS:
        if text.endswith("-" + suffix):
            text, effort = text[: -len(suffix) - 1], suffix
            break
    return text, effort


def tier_of(table: dict) -> dict[str, tuple[int, str]]:
    return {name: (index, tier["name"]) for index, tier in enumerate(table["tiers"]) for name in tier["models"]}


def find_model(table: dict, provider: str, model: str) -> str:
    family = family_name(model) or family_of_id(model)
    if family in table["model"]:
        return family
    key, _ = normalize(model)
    matches = [name for name, entry in table["model"].items()
               for via in entry["via"] if normalize(via["id"])[0] == key]
    preferred = [name for name in matches
                 if any(via["harness"] == provider for via in table["model"][name]["via"])]
    return (preferred or matches or [""])[0]


def via_candidates(table: dict, name: str, effort: str) -> list[Candidate]:
    _, tier = tier_of(table)[name]
    return [Candidate(via["harness"], via["id"], via.get("efforts", {}).get(effort, effort),
                      via.get("meter", True), name, tier, str(via.get("account") or ""))
            for via in table["model"][name]["via"]]


def tier_models(table: dict, start: str, allow_lower: bool, lowest_tier: str = "") -> list[str]:
    """`start`, the rest of its tier in order, then later tiers when allowed, down to
    `lowest_tier` (which alone also allows them). Never earlier tiers."""
    index, _ = tier_of(table)[start]
    names = [start] + [name for name in table["tiers"][index]["models"] if name != start]
    if lowest_tier and lowest_tier not in [tier["name"] for tier in table["tiers"]]:
        raise Failure(f"unknown lowest tier '{lowest_tier}'")
    if allow_lower or lowest_tier:
        for tier in table["tiers"][index + 1:]:
            if lowest_tier and [t["name"] for t in table["tiers"]].index(lowest_tier) <= index:
                break
            names.extend(tier["models"])
            if tier["name"] == lowest_tier:
                break
    return names


def expand_accounts(candidates: list[Candidate], *, requested_first: bool) -> list[Candidate]:
    """Walk a provider's accounts in file order when the tiers file does not name one.

    Zero or one account leaves the provider argument unchanged. A via that
    names an account keeps that order instead of expanding.
    """
    if not candidates:
        return candidates
    try:
        loaded = accounts.load()
    except accounts.AccountError:
        return candidates
    source = candidates[1:] if requested_first else candidates
    via_explicit = {item.provider for item in source if item.account}
    result: list[Candidate] = []
    seen: set[tuple] = set()
    for candidate in candidates:
        group = loaded.get(candidate.provider, [])
        if not candidate.account and candidate.provider not in via_explicit and len(group) >= 2:
            clones = [replace(candidate, account=item.name) for item in group]
        else:
            clones = [candidate]
        for clone in clones:
            pool = clone.account or accounts.default_account(clone.provider)
            key = (clone.provider, pool, clone.model, clone.effort)
            if key in seen:
                continue
            seen.add(key)
            result.append(clone)
    return result


def ladder(table: dict, provider: str, model: str, effort: str, allow_lower: bool = False,
           lowest_tier: str = "", account: str = "") -> list[Candidate]:
    """The requested run first, then same model elsewhere, then the same tier.

    Two vias are the same pool when their harness and account match. An empty
    account is the provider's default account, so a plain `claude` request is
    not tried again as an explicit default-account via. With two or more
    accounts and no via naming one, each unlabeled candidate becomes one
    candidate per account, in file order.
    """
    first = Candidate(provider, model, effort, account=account)
    name = find_model(table, provider, model)
    if not name:
        return [first]
    _, folded = normalize(model)
    if effort == "default" and folded:
        effort = folded
    first.name, first.tier = name, tier_of(table)[name][1]
    for via in table["model"][name]["via"]:
        if via["harness"] == provider and accounts.pools_match(account, str(via.get("account") or ""), provider):
            first.meter = via.get("meter", True)
            break
    rest = [candidate for other in tier_models(table, name, allow_lower, lowest_tier)
            for candidate in via_candidates(table, other, effort)
            if not (other == name and candidate.provider == provider
                    and accounts.pools_match(account, candidate.account, provider))]
    return expand_accounts([first] + rest, requested_first=True)


def tier_ladder(table: dict, tier: str, effort: str, prefer: str = "", allow_lower: bool = False,
                lowest_tier: str = "") -> list[Candidate]:
    names = next((t["models"] for t in table["tiers"] if t["name"] == tier), None)
    if names is None:
        raise Failure(f"unknown tier '{tier}'")
    start = prefer or names[0]
    if start not in names:
        raise Failure(f"model '{start}' is not in tier {tier}")
    return expand_accounts(
        [candidate for name in tier_models(table, start, allow_lower, lowest_tier)
         for candidate in via_candidates(table, name, effort)],
        requested_first=False)


# --- routes ----------------------------------------------------------------

def load_route(name: str) -> tuple[dict, dict]:
    path = os.environ.get("JAMSESSION_ROUTES")
    if not path:
        raise Failure("set JAMSESSION_ROUTES to a routes.toml file")
    routes = load_toml(Path(path))
    route = routes.get("route", {}).get(name)
    if route is None:
        raise Failure(f"route '{name}' is not in {path}; known: {', '.join(routes.get('route', {}))}")
    return route, routes.get("defaults", {})


def rung(entry: dict) -> Candidate:
    """One ladder step. `provider` may be `provider:account` (for example `claude:personal`)."""
    provider = str(entry["provider"])
    account = str(entry.get("account") or "")
    if ":" in provider:
        if account:
            raise Failure("route rung names an account twice")
        try:
            provider, account = accounts.split_spec(provider)
        except accounts.AccountError as error:
            raise Failure(str(error)) from None
    return Candidate(provider, entry["model"], entry.get("effort", "default"), entry.get("meter", True), account=account)


def expand_route(name: str, table: dict | None = None) -> dict:
    route, defaults = load_route(name)
    result = {"name": name, "skip_below_usage": float(route.get("skip_below_usage", defaults.get("skip_below_usage", DEFAULT_MIN_USAGE)))}
    if "from" in route:
        result.update(kind="panel", size=int(route.get("size", len(route["from"]))),
                      candidates=[rung(entry) for entry in route["from"]])
    elif "rungs" in route:
        result.update(kind="ladder", candidates=expand_accounts(
            [rung(entry) for entry in route["rungs"]], requested_first=False))
    elif "tier" in route:
        table = table or load_tiers()
        result.update(kind="ladder", candidates=tier_ladder(
            table, str(route["tier"]), str(route.get("effort", "default")),
            str(route.get("prefer", "")), bool(route.get("allow_lower", False)),
            str(route.get("lowest_tier", ""))))
    else:
        raise Failure(f"route '{name}' needs rungs, from, or tier")
    return result


# --- usage windows ---------------------------------------------------------

def window_minutes(window: dict) -> int | None:
    """Duration in minutes when the window names one, else a known class."""
    raw = window.get("window_minutes")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
        return int(raw)
    blob = f"{window.get('bucket_id') or ''} {window.get('label') or ''}".lower()
    if "current_session" in blob or "current session" in blob:
        return 300
    if "week" in blob:
        return WEEKLY_WINDOW_MINUTES
    if "month" in blob:
        return 43200
    return None


def is_short_window(window: dict) -> bool:
    """A 5-hour session window. It never makes an account unavailable."""
    minutes = window_minutes(window)
    if minutes is not None and minutes <= SHORT_WINDOW_MINUTES:
        return True
    return str(window.get("bucket_id") or "") == "current_session"


def governing_remaining(windows) -> float | None:
    """Remaining percent of the longest window, ignoring a short session window.

    When several windows share that longest duration, the lowest of them counts.
    A report that has only a short window does not skip the account.
    """
    known: list[tuple[int, float]] = []
    unknown: list[float] = []
    for window in windows:
        if not isinstance(window, dict):
            continue
        remaining = window.get("remaining_percent")
        if isinstance(remaining, bool) or not isinstance(remaining, (int, float)):
            continue
        if is_short_window(window):
            continue
        minutes = window_minutes(window)
        if minutes is None:
            unknown.append(float(remaining))
        else:
            known.append((minutes, float(remaining)))
    if known:
        longest = max(item[0] for item in known)
        return min(item[1] for item in known if item[0] == longest)
    if unknown:
        return min(unknown)
    return None


def _window_rank(window) -> int:
    """0 weekly, 1 other long windows, 2 a short session window."""
    if not isinstance(window, dict):
        return 1
    minutes = window_minutes(window)
    blob = f"{window.get('bucket_id') or ''} {window.get('label') or ''}".lower()
    if "week" in blob or (minutes is not None and 1440 < minutes <= 20160):
        return 0
    if is_short_window(window):
        return 2
    return 1


def order_windows(windows: list) -> list:
    """Weekly windows first, then other long windows, then a short session window."""
    indexed = list(enumerate(windows))
    indexed.sort(key=lambda item: (_window_rank(item[1]), item[0]))
    return [window for _, window in indexed]


def order_window_text(raw: str) -> str:
    """Reorder a comma-separated JSON object list without rewriting numbers.

    `json.dumps` would turn `0.000001` into `1e-06`.
    """
    parts = _split_json_objects(raw)
    if len(parts) < 2:
        return raw.strip()
    try:
        parsed = [json.loads(part) for part in parts]
    except json.JSONDecodeError:
        return raw.strip()
    order = sorted(range(len(parts)), key=lambda index: (_window_rank(parsed[index]), index))
    return ",".join(parts[index] for index in order)


def _split_json_objects(raw: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quoted = False
    escaped = False
    start = None
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quoted:
            escaped = True
            continue
        if char == '"':
            quoted = not quoted
            continue
        if quoted:
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                parts.append(raw[start:index + 1])
                start = None
    return parts


# --- usage -----------------------------------------------------------------

class Usage:
    """`jamsession usage --json`, read once and only if a fallback needs it."""

    def __init__(self, cli: str):
        self.cli, self.report = cli, None

    def load(self) -> dict:
        if self.report is None:
            self.report = {}
            try:
                if os.environ.get("JAMSESSION_USAGE_JSON"):
                    text = Path(os.environ["JAMSESSION_USAGE_JSON"]).read_text(encoding="utf-8")
                else:
                    print("failover: reading usage to skip low pools", file=sys.stderr)
                    text = subprocess.run([self.cli, "usage", "--json"], capture_output=True, text=True,
                                          timeout=120).stdout
                self.report = json.loads(text)
            except (OSError, ValueError, subprocess.SubprocessError):
                print("failover: usage unreadable; treating every pool as available", file=sys.stderr)
        return self.report

    def lowest(self, provider: str, account: str = "") -> float | None:
        """Remaining percent of the longest window; None when unread or only short.

        An empty account is the default account when usage rows are tagged,
        and the untagged provider row when they are not. A 5-hour session
        window does not count when a weekly or monthly window is present.
        """
        rows = [row for row in self.load().get("providers", [])
                if row.get("agent") == provider and row.get("status") == "ok"]
        if account:
            chosen = [row for row in rows if (row.get("account") or "") == account]
        else:
            default = accounts.default_account(provider)
            tagged = [row for row in rows if default and (row.get("account") or "") == default]
            chosen = tagged or [row for row in rows if not (row.get("account") or "")]
        windows = [window for row in chosen for window in row.get("windows", [])]
        return governing_remaining(windows)


# --- run -------------------------------------------------------------------

def attempt(cli: str, worksheet: str, candidate: Candidate, session: str, access: str, prompt: bytes) -> tuple[int, bytes]:
    command = [cli, "run"] + (["--worksheet", worksheet] if worksheet else []) + [
        candidate.provider_arg(), session, candidate.model, candidate.effort, access, "-"]
    # The selector that chose the first account must not veto a later account.
    env = os.environ.copy()
    env.pop(accounts.env_var(candidate.provider), None)
    # This child is the ladder, not the caller's choice. A bare default pool
    # must not warn again or switch to a later account.
    env["JAMSESSION_FAILOVER_STEP"] = "1"
    with tempfile.TemporaryFile() as reply:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=reply, stderr=subprocess.PIPE, env=env)

        def feed() -> None:
            try:
                process.stdin.write(prompt)
                process.stdin.close()
            except BrokenPipeError:
                pass

        writer = threading.Thread(target=feed, daemon=True)
        writer.start()
        for line in process.stderr:
            sys.stderr.buffer.write(line)
            sys.stderr.buffer.flush()
        status = process.wait()
        writer.join()
        reply.seek(0)
        return status, reply.read()


def skip_reason(candidate: Candidate, access: str, usage: Usage, min_usage: float) -> str:
    if access == "read" and candidate.provider in EDIT_ONLY:
        return "read access unsupported"
    # --min-usage 0 tries every pool. A per-account floor replaces any other value.
    floor = min_usage
    if min_usage > 0:
        try:
            override = accounts.min_usage_for(candidate.provider, candidate.account)
        except accounts.AccountError:
            override = None
        if override is not None:
            floor = override
    if candidate.meter and floor > 0:
        left = usage.lowest(candidate.provider, candidate.account)
        if left is not None and left < floor:
            return f"usage {left:g}% left, below {floor:g}%"
    return ""


def run(candidates: list[Candidate], session: str, access: str, prompt: bytes, *, cli: str, worksheet: str,
        min_usage: float, latest: "Latest | None" = None) -> int:
    usage = Usage(cli)
    latest = latest or Latest()
    requested = candidates[0]
    if len(candidates) == 1:
        print(f"failover: {requested.model} is not in the tiers table; no fallbacks", file=sys.stderr)
    tried, noted = 0, False
    for index, candidate in enumerate(candidates):
        try:
            candidate.model = latest.resolve(candidate.provider, candidate.model)
        except Unresolved as error:
            print(f"failover: skipping {candidate.label()} ({error})", file=sys.stderr)
            continue
        try:
            blocked = accounts.unavailable_reason(candidate.provider, candidate.account)
        except accounts.AccountError as error:
            blocked = str(error)
        if blocked:
            print(f"failover: skipping {candidate.label()} ({blocked})", file=sys.stderr)
            continue
        reason = skip_reason(candidate, access, usage, min_usage)
        if reason:
            print(f"failover: skipping {candidate.label()} ({reason})", file=sys.stderr)
            continue
        this_session = session if index == 0 else "new"
        if tried > 0:
            print(f"failover: trying {candidate.label()}", file=sys.stderr)
        if index > 0 and session != "new" and not noted:
            noted = True
            print(f"failover: session {session} cannot move across providers; starting new with only this prompt",
                  file=sys.stderr)
        tried += 1
        status, reply = attempt(cli, worksheet, candidate, this_session, access, prompt)
        if status == REFUSAL:
            print(f"failover: {candidate.label()} refused", file=sys.stderr)
            continue
        sys.stdout.buffer.write(reply)
        sys.stdout.buffer.flush()
        moved = candidate is not requested
        print(f"ran: provider={candidate.provider_arg()} model={candidate.model} effort={candidate.effort} "
              f"session={'resumed' if this_session != 'new' else 'new'}"
              + (f" requested={requested.provider_arg()}/{requested.model}/{requested.effort}" if moved else ""),
              file=sys.stderr)
        return status
    print("failover: all routes refused or were skipped; there is no answer", file=sys.stderr)
    return REFUSAL


def read_prompt(prompt: str) -> bytes:
    return sys.stdin.buffer.read() if prompt == "-" else prompt.encode()


def parse_options(args: list[str]) -> tuple[dict, list[str]]:
    options = {"allow_lower": False, "lowest_tier": "", "min_usage": None, "worksheet": "", "route": "", "json": False}
    rest: list[str] = []
    iterator = iter(args)
    for arg in iterator:
        if arg == "--allow-lower":
            options["allow_lower"] = True
        elif arg == "--json":
            options["json"] = True
        elif arg in ("--min-usage", "--worksheet", "--route", "--lowest-tier"):
            value = next(iterator, None)
            if value is None:
                raise Failure(f"{arg} needs a value")
            options[arg[2:].replace("-", "_")] = value
        elif arg == "--failover":
            pass
        else:
            rest.append(arg)
    if options["min_usage"] is not None:
        try:
            options["min_usage"] = float(options["min_usage"])
        except ValueError:
            raise Failure("--min-usage needs a number") from None
    return options, rest


def candidate_json(candidate: Candidate) -> dict:
    return {key: value for key, value in vars(candidate).items() if value != ""}


def main(argv: list[str]) -> int:
    if not argv:
        raise Failure("usage: jamsession_failover.py <run|route|tiers> ...")
    command, args = argv[0], argv[1:]
    options, rest = parse_options(args)
    cli = os.environ.get("JAMSESSION_CLI", "jamsession")
    if command == "resolve":
        if len(rest) != 2:
            raise Failure("resolve needs <harness> <model>")
        print(Latest().resolve(*rest))
        return 0
    if command == "route":
        if len(rest) != 1:
            raise Failure("route needs <name> [--json]")
        route = expand_route(rest[0])
        if options["json"]:
            print(json.dumps({**route, "candidates": [candidate_json(c) for c in route["candidates"]]}))
        else:
            if route["kind"] == "panel":
                print(f"panel: {route['size']} of these")
            for candidate in route["candidates"]:
                print(candidate.label() + ("" if candidate.meter else " meter=false"))
        return 0
    if command == "tiers":
        table = load_tiers()
        if not rest:
            for tier in table["tiers"]:
                for name in tier["models"]:
                    vias = ", ".join(
                        f"{v['harness']}:{v['id']}" + (f" account={v['account']}" if v.get("account") else "")
                        for v in table["model"][name]["via"])
                    print(f"{tier['name']}  {name:<12} {vias}")
            return 0
        if len(rest) != 3:
            raise Failure("tiers takes [<provider> <model> <effort>] [--allow-lower] [--json]")
        candidates = ladder(table, *rest, allow_lower=options["allow_lower"], lowest_tier=options["lowest_tier"])
        if options["json"]:
            print(json.dumps([candidate_json(c) for c in candidates]))
        else:
            for candidate in candidates:
                print(f"{candidate.tier or '-'}  {candidate.label()}" + ("" if candidate.meter else " meter=false"))
        return 0
    if command == "run":
        if options["route"]:
            if len(rest) != 3:
                raise Failure("run --route needs <name> <new|session> <read|edit> <prompt>")
            session, access, prompt = rest
            route = expand_route(options["route"])
            if route["kind"] == "panel":
                raise Failure(f"route '{options['route']}' is a panel; run its members with `jamsession route`")
            candidates = route["candidates"]
            min_usage = route["skip_below_usage"] if options["min_usage"] is None else options["min_usage"]
        else:
            if len(rest) != 6:
                raise Failure("run --failover needs <provider> <new|session> <model> <effort> <read|edit> <prompt>")
            provider, session, model, effort, access, prompt = rest
            try:
                provider, named = accounts.split_spec(provider)
                account = accounts.resolve(provider, named)
                # Warn once for the caller's bare provider. Do not pin the
                # argument; the ladder still walks every account.
                accounts.warn_bare(provider, named, session)
            except accounts.AccountError as error:
                raise Failure(str(error)) from None
            candidates = ladder(load_tiers(), provider, model, effort, options["allow_lower"],
                                options["lowest_tier"], account)
            min_usage = DEFAULT_MIN_USAGE if options["min_usage"] is None else options["min_usage"]
        if access not in ("read", "edit"):
            raise Failure("access must be read or edit")
        return run(candidates, session, access, read_prompt(prompt), cli=cli, worksheet=options["worksheet"],
                   min_usage=min_usage)
    raise Failure(f"unknown command '{command}'")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Failure as error:
        print(f"jamsession: {error}", file=sys.stderr)
        sys.exit(2)
