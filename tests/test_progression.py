"""Pure, deterministic progression checks; no wall clock or user files."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import progression  # noqa: E402


START = "2030-01-01T00:00:00Z"
DIMENSIONS = {
    "memory", "attention", "communication", "executive", "perception", "personality",
    "affect", "motivation", "social", "self", "autonomy", "experience",
}


def instant(days=0, seconds=0):
    return (datetime(2030, 1, 1, tzinfo=timezone.utc) + timedelta(days=days, seconds=seconds)).isoformat().replace("+00:00", "Z")


class ProgressionTests(unittest.TestCase):
    def config(self, **changes):
        value = {
            "mode": "default", "probability": 1.0, "cooldown_turns": 0,
            "max_profile": "severe", "eligible_dimensions": ["memory", "attention"],
            "triggers": [{"id": "park", "terms": ["公园", "Walk"]}],
            "onset_days": 10, "duration_days": 3,
        }
        value.update(changes)
        return progression.normalize_config(value)

    def state(self, **changes):
        return progression.initialize(self.config(**changes), "mild", 27, START)

    @staticmethod
    def event(number=1, text="去公园散步", kind="dialogue", **fields):
        return {"event_id": "event_" + str(number), "text": text, "kind": kind, **fields}

    def advance(self, state, number=1, text="去公园散步", kind="dialogue", at=None, **fields):
        return progression.advance(
            state, self.event(number, text, kind, **fields), at or instant(seconds=number),
            "2026-10-16T20:00:00Z",
        )

    def test_defaults_and_strict_configuration(self):
        config = progression.normalize_config({})
        self.assertEqual(config["mode"], "default")
        self.assertEqual(config["probability"], 0.2)
        self.assertEqual(config["cooldown_turns"], 3)
        self.assertEqual(config["max_profile"], "severe")
        invalid = [
            {"mode": "rapid"}, {"probability": -0.01}, {"probability": 1.01},
            {"probability": True}, {"cooldown_turns": True}, {"cooldown_turns": -1},
            {"onset_days": True}, {"duration_days": 0}, {"eligible_dimensions": ["unknown"]},
            {"eligible_dimensions": ["memory", "memory"]}, {"max_profile": "unknown"},
            {"triggers": [{"id": "park", "terms": []}]},
            {"triggers": [{"id": "park", "terms": ["公园"]}, {"id": "park", "terms": ["散步"]}]},
            {"unexpected": "unsupported"},
        ]
        for value in invalid:
            with self.subTest(config=value):
                with self.assertRaises(ValueError):
                    progression.normalize_config(value)

    def test_same_event_is_deterministic_and_does_not_mutate_inputs(self):
        state = self.state()
        before = deepcopy(state)
        event = self.event()
        event_before = deepcopy(event)
        next_state, decision = progression.advance(state, event, instant(seconds=1), START)
        repeated_state, repeated_decision = progression.advance(state, event, instant(seconds=1), START)
        self.assertEqual(state, before)
        self.assertEqual(event, event_before)
        self.assertIsNot(next_state, state)
        self.assertEqual(next_state, repeated_state)
        self.assertEqual(decision, repeated_decision)
        self.assertEqual(decision["draw"], random.Random("27:event_1").random())
        self.assertEqual(set(next_state["dimension_profiles"]), DIMENSIONS)

    def test_retry_never_rerolls_or_advances_but_conflicting_id_is_rejected(self):
        state, _ = self.advance(self.state())
        retry, decision = self.advance(state, at=instant(days=90))
        self.assertEqual(retry, state)
        self.assertEqual(retry["dialog_turns"], 1)
        self.assertEqual(len(retry["seen_event_ids"]), 1)
        with self.assertRaises(ValueError):
            self.advance(state, text="同一ID的不同内容")

    def test_trigger_matching_happens_before_random_draw(self):
        state, decision = self.advance(self.state(), text="请描述天气")
        self.assertIsNone(decision["draw"])
        self.assertIsNone(decision["changed"])
        self.assertEqual(state["dialog_turns"], 1)
        _, matched = self.advance(self.state(), text="LET US WALK")
        self.assertTrue(matched["matched_triggers"])
        self.assertIsNotNone(matched["draw"])
        _, none = self.advance(self.state(triggers=[]))
        self.assertIsNone(none["draw"])
        self.assertIsNone(none["changed"])

    def test_semantic_matches_require_configured_trigger_and_real_substring_evidence(self):
        state = self.state()
        _, decision = self.advance(
            state, text="我们到户外转一圈", semantic_matches=[{"trigger_id": "park", "evidence": "户外转一圈"}],
        )
        self.assertTrue(decision["matched_triggers"])
        self.assertIn("户外转一圈", str(decision["matched_triggers"]))
        for match in ({"trigger_id": "unknown", "evidence": "户外"},
                      {"trigger_id": "park", "evidence": "不存在的证据"},
                      {"trigger_id": "park", "evidence": ""}):
            with self.subTest(match=match):
                with self.assertRaises(ValueError):
                    self.advance(state, text="我们到户外转一圈", semantic_matches=[match])

    def test_cooldown_blocks_three_following_dialogues_without_drawing(self):
        state = self.state(cooldown_turns=3)
        state, first = self.advance(state)
        self.assertIsNotNone(first["changed"])
        for number in (2, 3, 4):
            state, decision = self.advance(state, number)
            self.assertIsNone(decision["changed"])
            self.assertIsNone(decision["draw"])
        state, fifth = self.advance(state, 5)
        self.assertIsNotNone(fifth["changed"])

    def test_each_change_is_one_dimension_one_level_and_bounded(self):
        state = self.state()
        rank = {"baseline": 0, "preclinical": 1, "mild": 2, "moderate": 3, "severe": 4}
        changes = 0
        for number in range(1, 9):
            previous = deepcopy(state["dimension_profiles"])
            state, decision = self.advance(state, number)
            altered = [key for key in DIMENSIONS if state["dimension_profiles"][key] != previous[key]]
            self.assertLessEqual(len(altered), 1)
            for key in altered:
                self.assertIn(key, {"memory", "attention"})
                self.assertEqual(rank[state["dimension_profiles"][key]] - rank[previous[key]], 1)
                changes += 1
            if not altered:
                self.assertIsNone(decision["changed"])
        self.assertEqual(changes, 4)
        self.assertEqual(state["dimension_profiles"]["memory"], "severe")
        self.assertEqual(state["dimension_profiles"]["attention"], "severe")
        self.assertEqual(state["dimension_profiles"]["personality"], "mild")

    def test_control_fixed_and_paused_do_not_draw_or_change_levels(self):
        state = self.state()
        control, decision = self.advance(state, kind="control")
        self.assertEqual(control["dialog_turns"], 0)
        self.assertIsNone(decision["draw"])
        self.assertEqual(control["dimension_profiles"], state["dimension_profiles"])
        for candidate in (self.state(mode="fixed"), {**self.state(), "paused": True}):
            result, decision = self.advance(candidate)
            self.assertIsNone(decision["draw"])
            self.assertEqual(result["dimension_profiles"], candidate["dimension_profiles"])

    def test_slow_onset_is_sampled_once_within_one_day_of_requested_delay(self):
        config = self.config(mode="slow", onset_days=10, duration_days=3)
        state = progression.initialize(config, "mild", 91, START)
        duplicate = progression.initialize(config, "mild", 91, START)
        onset = datetime.fromisoformat(state["onset_at"].replace("Z", "+00:00"))
        start = datetime.fromisoformat(START.replace("Z", "+00:00"))
        self.assertGreaterEqual((onset - start).total_seconds(), 9 * 86400)
        self.assertLessEqual((onset - start).total_seconds(), 11 * 86400)
        self.assertEqual(state["onset_at"], duplicate["onset_at"])
        before_onset = (onset - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        result, decision = self.advance(state, at=before_onset)
        self.assertIsNone(decision["changed"])
        self.assertEqual(result["onset_at"], state["onset_at"])

    def test_slow_overdue_events_advance_only_one_step_without_probability_or_trigger(self):
        state = self.state(mode="slow", probability=0, cooldown_turns=99, triggers=[])
        initial_onset = state["onset_at"]
        for number in range(1, 5):
            before = deepcopy(state["dimension_profiles"])
            state, decision = self.advance(state, number, text="无触发词", at=instant(days=100, seconds=number))
            self.assertEqual(sum(state["dimension_profiles"][key] != before[key] for key in DIMENSIONS), 1)
            self.assertIsNone(decision["draw"])
            self.assertEqual(state["onset_at"], initial_onset)
        self.assertEqual(state["slow_steps"], 4)
        capped, decision = self.advance(state, 5, at=instant(days=100, seconds=5))
        self.assertIsNone(decision["changed"])
        self.assertEqual(capped["dimension_profiles"], state["dimension_profiles"])


if __name__ == "__main__":
    unittest.main()
