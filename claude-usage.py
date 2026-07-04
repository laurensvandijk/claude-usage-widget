#!/usr/bin/env python3
"""Fetch Claude Code usage limits (session / weekly / Fable) for the Übersicht widget.

Reads the Claude Code OAuth credential from the macOS login Keychain, refreshes the
access token if it has expired, calls the same endpoint the `claude /usage` command uses,
and prints a compact JSON blob to stdout for the widget to render.

No claude.ai cookie, no third-party server. Talks only to api.anthropic.com and
platform.claude.com (the official Claude Code OAuth endpoints).
"""

import getpass
import json
import subprocess
import time
import urllib.request
import urllib.error

KEYCHAIN_SERVICE = "Claude Code-credentials"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"  # Claude Code public OAuth client
OAUTH_BETA = "oauth-2025-04-20"
USER_AGENT = "claude-cli/2.1.201 (external, cli)"  # required: platform.claude.com blocks bare urllib
REFRESH_BUFFER_MS = 120_000  # refresh if within 2 min of expiry


def _read_account(account):
    cmd = ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE]
    if account:
        cmd += ["-a", account]
    cmd += ["-w"]
    raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
    return json.loads(raw)


def _default_account_name():
    """Resolve the account of the default-matching item (so we can write back to it)."""
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE],
            capture_output=True, text=True,
        ).stdout
    except Exception:  # noqa: BLE001
        return None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('"acct"') and '="' in line:
            return line.split('="', 1)[1].rstrip('"')
    return None


def read_keychain():
    """Return (account, blob) for the credential with the furthest-future expiry.

    Claude Code stores its OAuth login under the macOS short username on most machines;
    some also have a stale "unknown" entry. We scan a few candidates and pick the freshest,
    resolving the real account name so refreshes can be written back to the right item.
    """
    candidates = []
    try:
        candidates.append(getpass.getuser())
    except Exception:  # noqa: BLE001
        pass
    candidates += [None, "unknown"]

    best = None  # (expiresAt, account, blob)
    for acct in candidates:
        try:
            blob = _read_account(acct)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        real = acct if acct is not None else _default_account_name()
        exp = oauth_node(blob).get("expiresAt", 0) or 0
        if best is None or exp > best[0]:
            best = (exp, real, blob)
    if best is None:
        raise subprocess.CalledProcessError(1, "security")
    account = best[1] or getpass.getuser()
    return account, best[2]


def write_keychain(account, blob):
    payload = json.dumps(blob, separators=(",", ":"))
    subprocess.run(
        ["security", "add-generic-password", "-U",
         "-a", account, "-s", KEYCHAIN_SERVICE, "-w", payload],
        check=True, stderr=subprocess.DEVNULL,
    )


def oauth_node(blob):
    """Credentials may be nested under claudeAiOauth; return the container we mutate in place."""
    if isinstance(blob, dict) and "claudeAiOauth" in blob:
        return blob["claudeAiOauth"]
    return blob


def refresh_token(account, blob):
    node = oauth_node(blob)
    body = json.dumps({
        "grant_type": "refresh_token",
        "refresh_token": node["refreshToken"],
        "client_id": CLIENT_ID,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)
    node["accessToken"] = data["access_token"]
    if data.get("refresh_token"):
        node["refreshToken"] = data["refresh_token"]
    if data.get("expires_in"):
        node["expiresAt"] = int(time.time() * 1000) + int(data["expires_in"]) * 1000
    write_keychain(account, blob)
    return node["accessToken"]


def ensure_token(account, blob):
    node = oauth_node(blob)
    now_ms = int(time.time() * 1000)
    exp = node.get("expiresAt", 0)
    if exp and exp - now_ms > REFRESH_BUFFER_MS:
        return node["accessToken"]
    return refresh_token(account, blob)


def fetch_usage(access_token):
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "anthropic-beta": OAUTH_BETA,
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def pick(limits, predicate):
    for lim in limits:
        if predicate(lim):
            return {
                "pct": round(lim.get("percent", 0)),
                "resets_at": lim.get("resets_at"),
                "severity": lim.get("severity", "normal"),
            }
    return None


def parse(usage):
    limits = usage.get("limits") or []

    def scoped_model_name(lim):
        scope = lim.get("scope") or {}
        model = scope.get("model") or {}
        return model.get("display_name")

    fable = pick(limits, lambda l: l.get("kind") == "weekly_scoped"
                 and scoped_model_name(l) == "Fable")
    return {
        "session": pick(limits, lambda l: l.get("kind") == "session"),
        "weekly": pick(limits, lambda l: l.get("kind") == "weekly_all"),
        "fable": fable,
        "fable_label": "Fable" if fable else None,
    }


def main():
    try:
        account, blob = read_keychain()
        token = ensure_token(account, blob)
        usage = fetch_usage(token)
        out = {"ok": True, "fetched_at": int(time.time())}
        out.update(parse(usage))
    except subprocess.CalledProcessError:
        out = {"ok": False, "error": "no-credential"}
    except urllib.error.HTTPError as e:
        out = {"ok": False, "error": f"http-{e.code}"}
    except Exception as e:  # noqa: BLE001 - surface anything to the widget
        out = {"ok": False, "error": str(e)[:120]}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
