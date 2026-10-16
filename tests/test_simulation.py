"""Scenario CLI integration in isolated roots; no real user runs are started."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "scripts" / "simulation.py"
START = "2030-01-01T00:00:00Z"
DIMENSIONS = {
    "memory", "attention", "communication", "executive", "perception", "personality",
    "affect", "motivation", "social", "self", "autonomy", "experience",
}


class SimulationCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="simulation-cli-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(REPO / ".agents", self.root / ".agents")
        (self.root / "state").mkdir()
        self.input_count = 0

    def invoke(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            capture_output=True, text=True, timeout=15,
        )
        if not success:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(result.stderr.strip())
            self.assertNotIn("Traceback", result.stderr)
            return result
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def input_file(self, value):
        self.input_count += 1
        path = self.root / "inputs" / (str(self.input_count) + ".json")
        self.write(path, value)
        return str(path)

    def simulations(self, user="alice"):
        return self.root / "state" / "users" / user / "simulations"

    def run_path(self, simulation, user="alice"):
        return self.simulations(user) / "runs" / simulation

    def prepare(self, data=None, user="alice", seed=43):
        if data is None:
            data = {"initial_profile": "mild", "progression": {"mode": "fixed"},
                    "clock": {"mode": "manual", "start_at": START, "timezone": "UTC"}}
        return self.invoke("prepare", "--user", user, "--input", self.input_file(data), "--seed", str(seed))

    def start(self, data=None, user="alice"):
        prepared = self.prepare(data, user)
        simulation = prepared["simulation_id"]
        self.invoke("start", "--user", user, "--simulation", simulation, "--confirmed", "--user-confirmed-memory")
        return simulation

    def context(self, simulation, user="alice", view="actor"):
        return self.invoke("context", "--user", user, "--simulation", simulation, "--view", view, "--limit", "20")

    @staticmethod
    def memory_input(content="合成测试偏好。", **fields):
        data = {
            "kind": "semantic", "content": content,
            "source": {"kind": "user_statement", "locator": "synthetic:user-turn-1"},
            "confidence": 1.0, "tags": [], "valid_until": None,
            "event_at": None, "event_time_note": "时间未知",
        }
        data.update(fields)
        return data

    def remember(self, simulation, content="合成测试偏好。", user="alice", **fields):
        return self.invoke(
            "remember", "--user", user, "--simulation", simulation,
            "--input", self.input_file(self.memory_input(content, **fields)),
        )

    def turn(self, simulation, event, user="alice", success=True):
        return self.invoke("turn", "--user", user, "--simulation", simulation,
                           "--input", self.input_file(event), success=success)

    def assert_utc(self, text):
        self.assertIsInstance(text, str)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        return parsed

    def test_prepare_returns_reviewable_card_without_starting_or_copying_memory(self):
        data = {"character": {"name": "测试角色", "counterpart_known": False},
                "scene": {"recent_experiences": []}}
        prepared = self.prepare(data)
        simulation = prepared["simulation_id"]
        self.assertTrue(simulation.startswith("sim_"))
        self.assertEqual(prepared["status"], "draft")
        self.assertIn("setup", prepared)
        self.assertIn("background", prepared)
        self.assertIs(prepared["requires_confirmation"], True)
        self.assertEqual(set(prepared["setup"]) & {"initial_profile", "progression", "clock", "generation"},
                         {"initial_profile", "progression", "clock", "generation"})
        shown = self.invoke("show-setup", "--user", "alice", "--simulation", simulation)
        self.assertEqual(shown["background"], prepared["background"])
        self.assertEqual(shown["setup"], prepared["setup"])
        self.assertFalse((self.simulations() / "active.json").exists())
        self.assertFalse(self.run_path(simulation).exists())

    def test_setup_rejects_unknown_keys_wrong_types_and_invalid_manual_clock(self):
        invalid = [
            {"unknown": "must-not-echo-this-secret"},
            {"character": {"counterpart_known": "false"}},
            {"character": {"unknown": "field"}}, {"scene": {"recent_experiences": "昨天"}},
            {"dimension_notes": {"unknown": "unsupported"}},
            {"generation": {"fill_missing": "yes"}}, {"initial_profile": "unknown"},
            {"progression": {"probability": True}}, {"progression": {"mode": "rapid"}},
            {"clock": {"mode": "manual", "start_at": None}},
            {"clock": {"mode": "manual", "start_at": "2030-01-01T00:00:00+08:00"}},
            {"clock": {"mode": "manual", "start_at": START, "unexpected": True}},
        ]
        for data in invalid:
            with self.subTest(data=data):
                result = self.invoke("prepare", "--user", "alice", "--input", self.input_file(data), success=False)
                self.assertNotIn("must-not-echo-this-secret", result.stderr)
        self.assertFalse((self.simulations() / "active.json").exists())

    def test_start_requires_both_confirmations_before_replacing_an_active_run(self):
        active = self.start()
        self.remember(active, "必须保留到真正确认新场景。")
        pointer_before = (self.simulations() / "active.json").read_bytes()
        memory_before = (self.run_path(active) / "memory.json").read_bytes()
        draft = self.prepare()["simulation_id"]
        for flags in ([], ["--confirmed"], ["--user-confirmed-memory"]):
            self.invoke("start", "--user", "alice", "--simulation", draft, *flags, success=False)
            self.assertEqual((self.simulations() / "active.json").read_bytes(), pointer_before)
            self.assertEqual((self.run_path(active) / "memory.json").read_bytes(), memory_before)
            self.assertFalse(self.run_path(draft).exists())
        self.invoke("start", "--user", "alice", "--simulation", active,
                    "--confirmed", "--user-confirmed-memory", success=False)
        self.assertEqual((self.run_path(active) / "memory.json").read_bytes(), memory_before)

    def test_new_simulation_resets_only_this_users_old_active_run(self):
        old = self.start()
        self.remember(old, "旧模拟私人内容。")
        self.invoke("update-state", "--user", "alice", "--simulation", old, "--dimension", "attention",
                    "--patch-file", self.input_file({"focus": "旧任务"}))
        bob = self.start(user="bob")
        self.remember(bob, "Bob 独立内容。", user="bob")
        bob_before = (self.run_path(bob, "bob") / "memory.json").read_bytes()
        legacy = self.root / "state" / "users" / "alice" / "memory.json"
        self.write(legacy, {"legacy_marker": "不能删除全局旧格式文件"})
        legacy_before = legacy.read_bytes()
        prepared = self.prepare()
        new = prepared["simulation_id"]
        self.assertTrue(self.run_path(old).exists())  # Preparation alone never resets.
        self.invoke("start", "--user", "alice", "--simulation", new, "--confirmed", "--user-confirmed-memory")
        self.assertEqual(self.read(self.simulations() / "active.json")["simulation_id"], new)
        self.assertFalse(self.run_path(old).exists())
        self.assertEqual(self.read(self.run_path(new) / "memory.json")["records"], [])
        self.assertIsNone(self.read(self.run_path(new) / "dimensions" / "attention.json")["value"]["focus"])
        self.assertEqual((self.run_path(bob, "bob") / "memory.json").read_bytes(), bob_before)
        self.assertEqual(legacy.read_bytes(), legacy_before)
        self.assertTrue((self.simulations() / "drafts" / (old + ".json")).exists())
        self.invoke("context", "--user", "alice", "--simulation", old, success=False)

    def test_resume_retains_state_and_requires_a_new_explicit_self_report(self):
        simulation = self.start()
        self.remember(simulation, "恢复会话仍须存在的内容。")
        before = (self.run_path(simulation) / "memory.json").read_bytes()
        self.invoke("resume", "--user", "alice", "--simulation", simulation, success=False)
        resumed = self.invoke("resume", "--user", "alice", "--simulation", simulation, "--user-confirmed-memory")
        self.assertEqual(resumed["status"], "active")
        self.assertEqual((self.run_path(simulation) / "memory.json").read_bytes(), before)
        self.assertIn("恢复会话仍须存在的内容。", json.dumps(self.context(simulation), ensure_ascii=False))

    def test_dimensions_and_memory_have_scoped_timestamps_and_independent_revisions(self):
        simulation = self.start()
        directory = self.run_path(simulation) / "dimensions"
        self.assertEqual({path.stem for path in directory.glob("*.json")}, DIMENSIONS)
        before_communication = (directory / "communication.json").read_bytes()
        attention = self.read(directory / "attention.json")
        for dimension in DIMENSIONS:
            record = self.read(directory / (dimension + ".json"))
            self.assertEqual(record["simulation_id"], simulation)
            self.assertEqual(record["user_id"], "alice")
            self.assertEqual(record["dimension"], dimension)
            self.assertEqual(record["revision"], 1)
            self.assertEqual(record["simulation_at"], START)
            self.assertIsNone(record["event_at"])
            self.assertIn("source", record)
            for field in ("created_at", "updated_at", "recorded_at"):
                self.assert_utc(record[field])
        self.invoke("update-state", "--user", "alice", "--simulation", simulation, "--dimension", "attention",
                    "--patch-file", self.input_file({"focus": "当前目标"}))
        updated = self.read(directory / "attention.json")
        self.assertEqual(updated["revision"], attention["revision"] + 1)
        self.assertEqual(updated["created_at"], attention["created_at"])
        self.assertEqual(updated["value"]["focus"], "当前目标")
        self.assertEqual((directory / "communication.json").read_bytes(), before_communication)
        self.remember(simulation, "很久以前发生的合成事件。", kind="episodic", event_at="1995-01-01T00:00:00Z",
                      source={"kind": "user_inferred", "locator": "synthetic:uncertain-story"})
        record = self.read(self.run_path(simulation) / "memory.json")["records"][0]
        self.assertEqual(record["simulation_id"], simulation)
        self.assertEqual(record["event_at"], "1995-01-01T00:00:00Z")
        self.assertEqual(record["simulation_at"], START)
        self.assertEqual(record["source"]["kind"], "user_inferred")
        self.assertGreater(self.assert_utc(record["recorded_at"]), self.assert_utc(record["event_at"]))
        self.invoke("validate")

    def test_context_is_read_only_and_exposes_background_origin(self):
        simulation = self.start()
        directory = self.run_path(simulation)
        before = {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*.json")}
        for view in ("actor", "controller"):
            context = self.context(simulation, view=view)
            self.assertEqual(set(context["dimensions"]), DIMENSIONS)
            self.assertEqual(set(context["dimension_records"]), DIMENSIONS)
            self.assertIn("provenance", context["background"])
            self.assertTrue(context["background"]["generated"])
        after = {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*.json")}
        self.assertEqual(after, before)

    def test_manual_clock_dedupe_and_control_events_do_not_reroll(self):
        data = {"progression": {"mode": "default", "probability": 1.0, "cooldown_turns": 0,
                                "eligible_dimensions": ["memory"], "triggers": [{"id": "park", "terms": ["公园"]}]},
                "clock": {"mode": "manual", "start_at": START, "timezone": "UTC"}}
        simulation = self.start(data)
        event = {"event_id": "turn-1", "kind": "dialogue", "text": "一起去公园", "simulation_at": "2030-01-02T00:00:00Z"}
        self.turn(simulation, event)
        self.turn(simulation, {**event, "event_id": "turn-2", "simulation_at": "2030-01-03T00:00:00Z"})
        run_path = self.run_path(simulation) / "run.json"
        before_retry = self.read(run_path)["progression"]
        self.turn(simulation, event)  # An old timestamp on a known retry is not a new clock event.
        after_retry = self.read(run_path)["progression"]
        self.assertEqual(after_retry, before_retry)
        self.assertEqual(after_retry["dialog_turns"], 2)
        control = {"event_id": "control-1", "kind": "control", "text": "查询状态", "simulation_at": "2030-01-03T01:00:00Z"}
        self.turn(simulation, control)
        after_control = self.read(run_path)["progression"]
        self.assertEqual(after_control["dialog_turns"], 2)
        self.assertEqual(after_control["dimension_profiles"], before_retry["dimension_profiles"])
        before_bad = run_path.read_bytes()
        self.turn(simulation, {**event, "event_id": "turn-backwards", "simulation_at": "2030-01-01T00:00:01Z"}, success=False)
        self.assertEqual(run_path.read_bytes(), before_bad)

    def test_pause_resume_progression_and_severe_memory_maintenance(self):
        data = {"initial_profile": "severe", "progression": {"mode": "fixed"},
                "clock": {"mode": "manual", "start_at": START, "timezone": "UTC"}}
        simulation = self.start(data)
        self.invoke("pause", "--user", "alice", "--simulation", simulation)
        self.assertIs(self.read(self.run_path(simulation) / "run.json")["progression"]["paused"], True)
        self.invoke("resume-progression", "--user", "alice", "--simulation", simulation)
        self.assertIs(self.read(self.run_path(simulation) / "run.json")["progression"]["paused"], False)
        record_ids = [
            self.remember(simulation, content, kind="episodic")["id"]
            for content in ("首条合成经历。", "第二条合成经历。", "第三条合成经历。")
        ]
        visible_ids = {record["id"] for record in self.context(simulation)["memories"]}
        first = next(memory_id for memory_id in record_ids if memory_id not in visible_ids)
        replacement = self.memory_input("明确纠正的新内容。", kind="episodic",
                                        source={"kind": "user_statement", "locator": "synthetic:correction"})
        self.invoke("correct", "--user", "alice", "--simulation", simulation, "--id", first,
                    "--input", self.input_file(replacement))
        record = next(r for r in self.read(self.run_path(simulation) / "memory.json")["records"] if r["id"] == first)
        self.assertEqual(record["revision"], 2)
        self.assertEqual(record["source"], replacement["source"])
        self.invoke("forget", "--user", "alice", "--simulation", simulation, "--id", first)
        self.assertNotIn(first, {r["id"] for r in self.context(simulation, view="controller")["memories"]})
        self.assertNotIn(replacement["content"], (self.run_path(simulation) / "memory.json").read_text(encoding="utf-8"))

    def test_background_edits_keep_seed_and_unchanged_provenance(self):
        simulation = self.start()
        path = self.run_path(simulation) / "background.json"
        before = self.read(path)
        self.invoke("edit-background", "--user", "alice", "--simulation", simulation,
                    "--input", self.input_file({"character": {"name": "明确指定的新名字"}}))
        after = self.read(path)
        self.assertEqual(after["seed"], before["seed"])
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertEqual(after["provenance"]["scene.setting"], before["provenance"]["scene.setting"])
        self.assertEqual(after["provenance"]["character.name"]["source_kind"], "user_provided")
        self.assertEqual(self.read(self.run_path(simulation) / "memory.json")["records"], [])

    def test_user_active_id_and_metadata_ownership_are_enforced(self):
        alice = self.start()
        bob = self.start(user="bob")
        self.invoke("context", "--user", "bob", "--simulation", alice, success=False)
        self.invoke("context", "--user", "../alice", "--simulation", alice, success=False)
        self.invoke("context", "--user", "alice", "--simulation", "../" + bob, success=False)
        path = self.run_path(alice) / "dimensions" / "memory.json"
        record = self.read(path)
        record["simulation_id"] = bob
        self.write(path, record)
        before = path.read_bytes()
        self.invoke("context", "--user", "alice", "--simulation", alice, success=False)
        self.invoke("validate", success=False)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_or_cross_run_background_provenance_is_rejected_read_only(self):
        simulation = self.start()
        bob = self.start(user="bob")
        path = self.run_path(simulation) / "background.json"
        original = self.read(path)
        self.assertEqual(original["user_id"], "alice")
        self.assertEqual(original["simulation_id"], simulation)
        invalid = []
        missing_all = deepcopy(original)
        missing_all["provenance"] = {}
        invalid.append(missing_all)
        missing_one = deepcopy(original)
        del missing_one["provenance"]["character.name"]
        invalid.append(missing_one)
        extra = deepcopy(original)
        extra["provenance"]["character.unknown_field"] = {
            "source_kind": "user_provided", "recorded_at": original["created_at"],
        }
        invalid.append(extra)
        # Equal generation seeds do not make another run's provenance transferable.
        invalid.append(self.read(self.run_path(bob, "bob") / "background.json"))
        for number, value in enumerate(invalid):
            with self.subTest(case=number):
                self.write(path, value)
                before = path.read_bytes()
                self.invoke("context", "--user", "alice", "--simulation", simulation, success=False)
                self.invoke("validate", success=False)
                self.assertEqual(path.read_bytes(), before)
        self.write(path, original)
        self.invoke("validate")

    def test_symlink_in_old_active_run_blocks_reset_before_pointer_replacement(self):
        active = self.start()
        external = self.root / "protected-external"
        external.mkdir()
        marker = external / "keep.txt"
        marker.write_text("外部文件必须保留", encoding="utf-8")
        link = self.run_path(active) / "unexpected-link"
        link.symlink_to(external, target_is_directory=True)
        prepared = self.prepare()["simulation_id"]
        pointer_before = (self.simulations() / "active.json").read_bytes()
        self.invoke("start", "--user", "alice", "--simulation", prepared,
                    "--confirmed", "--user-confirmed-memory", success=False)
        self.assertEqual((self.simulations() / "active.json").read_bytes(), pointer_before)
        self.assertTrue(self.run_path(active).exists())
        self.assertTrue(link.is_symlink())
        self.assertFalse(self.run_path(prepared).exists())
        self.assertEqual(marker.read_text(encoding="utf-8"), "外部文件必须保留")


if __name__ == "__main__":
    unittest.main()
