#!/usr/bin/env python3
"""Unit tests for the pure logic in claude-usage.py. Run: python3 test_claude_usage.py

Covers response parsing, limit selection, credential-shape handling, error mapping,
the cache round-trip, and CLI-version detection. Network and Keychain I/O are not
exercised here (they're integration paths); these lock down the parsing/branching.
"""

import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
import urllib.error
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("claude_usage", os.path.join(_HERE, "claude-usage.py"))
cu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cu)


def usage_fixture():
    return {
        "limits": [
            {"kind": "session", "percent": 42, "severity": "normal",
             "resets_at": "2026-07-04T23:50:00+00:00"},
            {"kind": "weekly_all", "percent": 41, "severity": "normal",
             "resets_at": "2026-07-06T22:00:00+00:00"},
            {"kind": "weekly_scoped", "percent": 30, "severity": "warning",
             "resets_at": "2026-07-06T22:00:00+00:00",
             "scope": {"model": {"display_name": "Fable"}}},
        ]
    }


class TestParse(unittest.TestCase):
    def test_extracts_three_limits(self):
        out = cu.parse(usage_fixture())
        self.assertEqual(out["session"]["pct"], 42)
        self.assertEqual(out["weekly"]["pct"], 41)
        self.assertEqual(out["fable"]["pct"], 30)
        self.assertEqual(out["fable"]["severity"], "warning")
        self.assertEqual(out["fable_label"], "Fable")

    def test_fable_absent_when_no_scoped_fable(self):
        u = usage_fixture()
        u["limits"] = [l for l in u["limits"] if l["kind"] != "weekly_scoped"]
        out = cu.parse(u)
        self.assertIsNone(out["fable"])
        self.assertIsNone(out["fable_label"])

    def test_scoped_non_fable_is_ignored(self):
        u = usage_fixture()
        u["limits"][2]["scope"]["model"]["display_name"] = "Sonnet"
        self.assertIsNone(cu.parse(u)["fable"])

    def test_empty_or_missing_limits(self):
        self.assertIsNone(cu.parse({})["session"])
        self.assertIsNone(cu.parse({"limits": None})["weekly"])


class TestPick(unittest.TestCase):
    def test_rounds_percent(self):
        row = cu.pick([{"kind": "session", "percent": 41.6}], lambda l: True)
        self.assertEqual(row["pct"], 42)

    def test_defaults_missing_percent_to_zero(self):
        row = cu.pick([{"kind": "session"}], lambda l: True)
        self.assertEqual(row["pct"], 0)
        self.assertEqual(row["severity"], "normal")

    def test_returns_none_when_no_match(self):
        self.assertIsNone(cu.pick([{"kind": "x"}], lambda l: l["kind"] == "y"))


class TestOAuthNode(unittest.TestCase):
    def test_wrapped(self):
        inner = {"accessToken": "a"}
        self.assertIs(cu.oauth_node({"claudeAiOauth": inner}), inner)

    def test_flat(self):
        flat = {"accessToken": "a"}
        self.assertIs(cu.oauth_node(flat), flat)


class TestErrorLabel(unittest.TestCase):
    def test_token_expired(self):
        self.assertEqual(cu.error_label(cu.TokenExpired()), "expired")

    def test_no_credential(self):
        self.assertEqual(cu.error_label(subprocess.CalledProcessError(1, "security")), "no-credential")

    def test_http_code(self):
        err = urllib.error.HTTPError("u", 429, "Too Many Requests", None, io.BytesIO(b""))
        try:
            self.assertEqual(cu.error_label(err), "http-429")
        finally:
            err.close()

    def test_generic(self):
        self.assertEqual(cu.error_label(ValueError("boom")), "boom")


class TestCache(unittest.TestCase):
    def test_roundtrip_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cache.json")
            with mock.patch.object(cu, "CACHE_PATH", path):
                self.assertIsNone(cu.read_cache())  # absent
                cu.write_cache({"ok": True, "session": {"pct": 7}})
                self.assertEqual(cu.read_cache()["session"]["pct"], 7)

    def test_read_corrupt_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cache.json")
            open(path, "w").write("{not json")
            with mock.patch.object(cu, "CACHE_PATH", path):
                self.assertIsNone(cu.read_cache())


class TestCliVersion(unittest.TestCase):
    def test_picks_highest_numeric_version(self):
        with mock.patch.object(cu.os, "listdir", return_value=["2.1.9", "2.1.201", "1.0.0", "notes"]):
            self.assertEqual(cu._cli_version(), "2.1.201")

    def test_none_when_dir_missing(self):
        with mock.patch.object(cu.os, "listdir", side_effect=OSError):
            self.assertIsNone(cu._cli_version())


if __name__ == "__main__":
    unittest.main(verbosity=2)
