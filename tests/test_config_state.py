import json
import os
import stat
import unittest
from datetime import datetime, timedelta, timezone

import helpers
from chatcatchup import config, state


class ConfigTests(helpers.IsolatedHome):
    def test_load_without_setup_explains_what_to_do(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.load()
        self.assertIn("config init", str(ctx.exception))

    def test_init_applies_sensible_defaults(self):
        cfg = config.init(["Alex", "Al"], teams=["Programming"])
        self.assertEqual(cfg["me"]["sign_up_as"], "Alex")
        self.assertEqual(cfg["actions"], {"fill_sheets": "ask", "chat_replies": "ask"})
        self.assertEqual(config.load()["me"]["teams"], ["Programming"])

    def test_init_refuses_to_overwrite_without_force(self):
        config.init(["Alex"])
        with self.assertRaises(config.ConfigError):
            config.init(["Sam"])
        self.assertEqual(config.init(["Sam"], force=True)["me"]["names"], ["Sam"])

    def test_settings_file_is_private(self):
        config.init(["Alex"], email="alex@example.com")
        mode = stat.S_IMODE(os.stat(config.config_path()).st_mode)
        self.assertEqual(mode, 0o600)

    def test_set_value_parses_json_and_validates(self):
        config.init(["Alex"])
        cfg = config.load()
        config.set_value(cfg, "actions.fill_sheets", "auto")
        config.set_value(cfg, "me.teams", '["Programming", "Drive team"]')
        config.set_value(cfg, "lookback_days", "14")
        self.assertEqual(cfg["actions"]["fill_sheets"], "auto")
        self.assertEqual(cfg["me"]["teams"], ["Programming", "Drive team"])
        self.assertEqual(cfg["lookback_days"], 14)

    def test_set_value_rejects_bad_values_and_unknown_keys(self):
        config.init(["Alex"])
        cfg = config.load()
        with self.assertRaises(config.ConfigError):
            config.set_value(cfg, "actions.fill_sheets", "always")
        with self.assertRaises(config.ConfigError):
            config.set_value(cfg, "actions.chat_replies", "auto")  # auto-sending is deliberately not offered
        with self.assertRaises(config.ConfigError):
            config.set_value(cfg, "nonsense.key", "1")

    def test_older_config_gets_new_defaults(self):
        self.home.mkdir(parents=True)
        (self.home / "config.json").write_text(json.dumps({"me": {"names": ["Alex"], "sign_up_as": "Alex"}}))
        cfg = config.load()
        self.assertEqual(cfg["actions"]["fill_sheets"], "ask")
        self.assertEqual(config.validate(cfg), [])

    def test_validate_lists_problems_in_plain_english(self):
        problems = config.validate(config._merge(config.DEFAULTS, {}))
        self.assertTrue(any("me.names" in p for p in problems))


class StateTests(helpers.IsolatedHome):
    def setUp(self):
        super().setUp()
        config.init(["Alex"])

    def test_first_run_uses_lookback_window(self):
        now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
        result = state.since("Programming", 7, now=now)
        self.assertEqual(result, {"space": "Programming", "since": "2026-11-16T12:00:00Z", "source": "lookback"})

    def test_after_marking_since_picks_up_where_it_left_off(self):
        state.mark("Programming", "2026-11-22T09:30:00Z")
        self.assertEqual(state.since("Programming", 7)["since"], "2026-11-22T09:30:00Z")
        self.assertEqual(state.since("Programming", 7)["source"], "state")

    def test_mark_never_moves_backwards(self):
        state.mark("Programming", "2026-11-22T09:30:00Z")
        state.mark("Programming", "2026-11-01T00:00:00Z")
        self.assertEqual(state.since("Programming", 7)["since"], "2026-11-22T09:30:00Z")

    def test_spaces_are_independent(self):
        state.mark("Programming", "2026-11-22T09:30:00Z")
        self.assertEqual(state.since("Social", 7)["source"], "lookback")

    def test_fill_log_is_an_audit_trail_and_prevents_repeats(self):
        url = "https://docs.google.com/spreadsheets/d/ABC/edit"
        self.assertFalse(state.has_fill(url, "Sheet1", "D5"))
        state.log_fill(url, "Sheet1", "d5", "Alex R.")
        self.assertTrue(state.has_fill(url, "Sheet1", "D5"))
        self.assertFalse(state.has_fill(url, "Sheet2", "D5"))
        self.assertEqual(state.fills(url)[0]["value"], "Alex R.")
        self.assertEqual(state.fills("https://other"), [])

    def test_corrupt_state_is_reported_not_overwritten(self):
        (self.home / "state.json").write_text("{not json")
        with self.assertRaises(config.ConfigError):
            state.load()
        self.assertEqual((self.home / "state.json").read_text(), "{not json")

    def test_parse_when_handles_z_and_offsets(self):
        self.assertEqual(state.parse_when("2026-11-23T08:00:00Z"), datetime(2026, 11, 23, 8, 0, tzinfo=timezone.utc))
        self.assertEqual(state.parse_when("2026-11-23T08:00:00-05:00"), datetime(2026, 11, 23, 13, 0, tzinfo=timezone.utc))
        with self.assertRaises(config.ConfigError):
            state.parse_when("last tuesday")


if __name__ == "__main__":
    unittest.main()
