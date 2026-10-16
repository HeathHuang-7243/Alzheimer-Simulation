"""CLI checks for explicit, file-backed affected-agent profiles.

These synthetic fixtures test control plumbing and memory visibility, not
clinical validity or a language model's portrayal of a person with disease.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "scripts" / "cognition.py"
DIMENSIONS = {
    "memory", "attention", "communication", "executive", "perception",
    "personality", "affect", "motivation", "social", "self", "autonomy",
    "experience",
}
PROFILES = ("baseline", "preclinical", "mild", "moderate", "severe")


class AlzheimerCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="affected-agent-test-")
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
            return result
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def input_file(self, data):
        self.input_count += 1
        path = self.root / "inputs" / (str(self.input_count) + ".json")
        self.write(path, data)
        return str(path)

    def session_path(self, session="one"):
        return self.root / "state" / "users" / "alice" / "sessions" / (session + ".json")

    def memory_path(self):
        return self.root / "state" / "users" / "alice" / "memory.json"

    def profile_path(self, profile):
        return self.root / ".agents" / "alzheimer" / "profiles" / (profile + ".json")

    def start(self, profile=None, session="one", confirmed=True):
        args = ["init-session", "--user", "alice", "--session", session]
        if profile is not None:
            args += ["--affected-profile", profile]
        self.invoke(*args)
        if confirmed:
            self.invoke("confirm-memory", "--user", "alice", "--session", session, "--user-confirmed")

    def context(self, view="actor", support="none", query=None, limit=20, session="one"):
        args = ["context", "--user", "alice", "--session", session,
                "--view", view, "--support", support, "--limit", str(limit)]
        if query is not None:
            args += ["--query", query]
        return self.invoke(*args)

    def set_profile(self, profile, session="one", success=True):
        return self.invoke(
            "set-affected-profile", "--user", "alice", "--session", session,
            "--profile", profile, success=success,
        )

    def configure_windows(self, windows=(2, 3, 4), bonus=1, context_items=20, profile="moderate"):
        path = self.profile_path(profile)
        data = self.read(path)
        for key, value in zip(("recent_episode_window", "semantic_window", "procedural_window"), windows):
            data["controls"]["memory"][key] = value
        data["controls"]["memory"]["cue_bonus"] = bonus
        data["controls"]["attention"]["context_items"] = context_items
        self.write(path, data)
        return data

    def seed_memories(self, count=6, expired=False):
        """Write a deterministic, valid synthetic corpus without model calls."""
        memory = self.read(self.root / ".agents" / "templates" / "memory.json")
        memory["user_id"] = "alice"
        records = []
        for kind in ("episodic", "semantic", "procedural"):
            for number in range(count):
                instant = f"2020-01-{number + 1:02d}T00:00:00Z"
                records.append({
                    "id": f"mem_{kind}_{number}", "kind": kind,
                    "content": f"合成记忆正文-{kind}-{number}-独立内容",
                    "source": {"kind": "user_statement", "locator": f"synthetic:{kind}:{number}"},
                    "confidence": 1.0, "tags": ["合成验收"], "valid_until": None,
                    "created_at": instant, "updated_at": instant, "revision": 1,
                })
        if expired:
            old = deepcopy(records[0])
            old.update(id="mem_expired", content="已到期，不应参与窗口计算。",
                       updated_at="2025-01-01T00:00:00Z", valid_until="2000-01-01T00:00:00Z")
            records.append(old)
        memory["records"] = records
        self.write(self.memory_path(), memory)
        return records

    @staticmethod
    def ids(context):
        return {record["id"] for record in context["memories"]}

    def test_each_profile_initializes_pending_and_exports_all_twelve_controls(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                self.start(profile, session=profile, confirmed=False)
                state = self.read(self.session_path(profile))
                self.assertEqual(state["memory_gate"]["status"], "pending")
                self.assertEqual(state["affected"], {
                    "condition": "alzheimer", "profile": profile, "definition_version": 1,
                })
                self.invoke("confirm-memory", "--user", "alice", "--session", profile, "--user-confirmed")
                context = self.context(session=profile)
                self.assertEqual(context["affected"]["controls"], self.read(self.profile_path(profile))["controls"])
                self.assertEqual(set(context["affected"]["controls"]), DIMENSIONS)
                self.assertEqual(set(context["affected"]["definitions"]), DIMENSIONS)
        self.invoke("validate")

    def test_affected_profile_never_bypasses_the_memory_gate(self):
        self.start("severe", confirmed=False)
        for view in ("actor", "controller"):
            self.invoke("context", "--user", "alice", "--session", "one", "--view", view, success=False)
        self.set_profile("mild", success=False)
        self.assertEqual(self.read(self.session_path())["affected"]["profile"], "severe")

    def test_old_session_without_affected_metadata_behaves_as_baseline(self):
        self.start()
        self.seed_memories()
        current = self.context()
        state = self.read(self.session_path())
        state.pop("affected", None)
        self.write(self.session_path(), state)
        before = self.session_path().read_bytes()
        legacy = self.context()
        self.assertEqual(legacy["affected"]["profile"], "baseline")
        self.assertEqual(legacy["memories"], current["memories"])
        self.assertEqual(legacy["dimensions"], current["dimensions"])
        self.assertEqual(before, self.session_path().read_bytes())
        self.invoke("validate")

    def test_preclinical_profile_does_not_force_visible_memory_deficits(self):
        self.start("baseline")
        self.seed_memories()
        baseline = self.context()
        self.set_profile("preclinical")
        preclinical = self.context()
        self.assertEqual(preclinical["memories"], baseline["memories"])
        self.assertEqual(preclinical["dimensions"], baseline["dimensions"])

    def test_preclinical_matches_baseline_above_twenty_records_when_config_allows(self):
        config_path = self.root / ".agents" / "config" / "dialogue.json"
        config = self.read(config_path)
        config["retrieval"]["max_limit"] = 50
        self.write(config_path, config)
        self.start("baseline")
        self.seed_memories(count=12)  # 36 valid records, enough to expose a hidden cap of 20.
        baseline = self.context(limit=30)
        self.assertEqual(len(baseline["memories"]), 30)
        self.set_profile("preclinical")
        preclinical = self.context(limit=30)
        self.assertEqual(preclinical["memories"], baseline["memories"])
        for context in (baseline, preclinical):
            self.assertIs(context["affected"]["mechanical_effects"]["memory_window_applied"], False)
            self.assertIs(context["affected"]["mechanical_effects"]["attention_limit_applied"], False)

    def test_actor_caps_each_memory_kind_before_retrieval_and_hides_excluded_records(self):
        self.configure_windows()
        self.start("moderate")
        records = self.seed_memories(expired=True)
        memory = self.read(self.memory_path())
        memory["records"][0]["content"] = "紫檀旧桥"
        records[0]["content"] = "紫檀旧桥"
        self.write(self.memory_path(), memory)
        state = self.read(self.session_path())
        state["dimensions"]["memory"]["active_ids"] = [r["id"] for r in records]
        self.write(self.session_path(), state)
        actor = self.context()
        expected = {
            f"mem_{kind}_{number}"
            for kind, first in (("episodic", 4), ("semantic", 3), ("procedural", 2))
            for number in range(first, 6)
        }
        self.assertEqual(self.ids(actor), expected)
        self.assertEqual(set(actor["dimensions"]["memory"]["active_ids"]), expected)
        serialized = json.dumps(actor, ensure_ascii=False)
        for record in records:
            if record["id"] not in expected:
                self.assertNotIn(record["id"], serialized)
                self.assertNotIn(record["content"], serialized)
        # A lexical hit outside the actor window must not recover the record.
        self.assertEqual(self.context(query="紫檀旧桥")["memories"], [])
        self.assertEqual(self.ids(self.context(view="controller", query="紫檀旧桥")), {"mem_episodic_0"})

    def test_controller_retains_canonical_view_and_is_marked_out_of_character(self):
        self.configure_windows(windows=(0, 0, 0), bonus=0)
        self.start("moderate")
        records = self.seed_memories()
        self.assertEqual(self.context()["memories"], [])
        controller = self.context(view="controller")
        self.assertEqual(self.ids(controller), {r["id"] for r in records})
        self.assertEqual(controller["view"], "controller")
        self.assertIs(controller["out_of_character"], True)
        self.assertEqual(controller["affected"]["view"], "controller")
        self.assertEqual(controller["memories"], self.context(view="controller", support="cue")["memories"])
        self.assertEqual(controller["memories"], self.context(view="controller", support="stepwise")["memories"])
        self.assertIs(controller["affected"]["mechanical_effects"]["memory_window_applied"], False)
        self.assertIs(controller["affected"]["mechanical_effects"]["attention_limit_applied"], False)

    def test_cue_and_stepwise_support_have_bounded_nonaccumulating_effects(self):
        self.configure_windows(windows=(1, 1, 1), bonus=2, context_items=4)
        self.start("moderate")
        self.seed_memories()
        before = self.memory_path().read_bytes()
        self.assertEqual(len(self.context()["memories"]), 3)
        cue = self.context(support="cue")
        stepwise = self.context(support="stepwise")
        self.assertEqual(len(cue["memories"]), 6)  # Attention: 4 + one bonus of 2.
        self.assertEqual(self.ids(cue), self.ids(stepwise))
        self.assertEqual(self.ids(cue), self.ids(self.context(support="cue")))
        for kind in ("episodic", "semantic", "procedural"):
            self.assertLessEqual(sum(r["kind"] == kind for r in cue["memories"]), 3)
        self.assertEqual(len(self.context(support="stepwise", limit=2)["memories"]), 2)
        self.assertEqual(before, self.memory_path().read_bytes())

    def test_profile_changes_preserve_canonical_memory_persona_and_dimension_state(self):
        self.start()
        self.seed_memories()
        self.invoke(
            "update-state", "--user", "alice", "--session", "one", "--dimension", "attention",
            "--patch-file", self.input_file({"focus": "保留当前任务", "deferred": ["之后讨论"]}),
        )
        dimensions = self.read(self.session_path())["dimensions"]
        memory_before = self.memory_path().read_bytes()
        persona_path = self.root / ".agents" / "config" / "persona.json"
        persona_before = persona_path.read_bytes()
        for profile in ("severe", "mild", "baseline"):
            self.set_profile(profile)
            self.assertEqual(self.read(self.session_path())["dimensions"], dimensions)
            self.assertEqual(self.memory_path().read_bytes(), memory_before)
            self.assertEqual(persona_path.read_bytes(), persona_before)

    def test_correction_and_forgetting_work_even_when_actor_cannot_recall_the_record(self):
        self.configure_windows(windows=(0, 0, 0), bonus=0)
        self.start("moderate")
        records = self.seed_memories(count=1)
        record = records[0]
        self.assertNotIn(record["id"], self.ids(self.context()))
        replacement = {
            "kind": "episodic", "content": "用户明确纠正后的合成内容。",
            "source": {"kind": "user_statement", "locator": "synthetic:explicit-correction"},
            "confidence": 1.0, "tags": [], "valid_until": None,
        }
        self.invoke(
            "correct", "--user", "alice", "--session", "one", "--id", record["id"],
            "--input", self.input_file(replacement),
        )
        corrected = next(r for r in self.read(self.memory_path())["records"] if r["id"] == record["id"])
        self.assertEqual(corrected["revision"], 2)
        self.assertEqual(corrected["source"], replacement["source"])
        self.assertEqual(corrected["content"], replacement["content"])
        self.assertEqual(self.context()["memories"], [])
        self.assertIn(record["id"], self.ids(self.context(view="controller")))
        result = self.invoke("forget", "--user", "alice", "--session", "one", "--id", record["id"])
        self.assertNotIn(replacement["content"], json.dumps(result, ensure_ascii=False))
        self.assertNotIn(record["id"], self.ids(self.context(view="controller")))
        self.assertNotIn(replacement["content"], self.memory_path().read_text(encoding="utf-8"))

    def test_unknown_profile_rejected_without_changing_existing_session(self):
        self.start("mild")
        before = self.session_path().read_bytes()
        for profile in ("unknown", "../severe"):
            self.set_profile(profile, success=False)
            self.invoke(
                "init-session", "--user", "alice", "--session", "bad",
                "--affected-profile", profile, success=False,
            )
        self.assertEqual(before, self.session_path().read_bytes())
        state = self.read(self.session_path())
        state["affected"]["profile"] = "unknown"
        self.write(self.session_path(), state)
        self.invoke("context", "--user", "alice", "--session", "one", success=False)
        self.invoke("validate", success=False)

    def test_invalid_profile_controls_and_metadata_are_rejected(self):
        path = self.profile_path("moderate")
        original = self.read(path)
        self.invoke("validate")
        invalid_profiles = []
        for value in (-1, True, "two"):
            invalid = deepcopy(original)
            invalid["controls"]["memory"]["recent_episode_window"] = value
            invalid_profiles.append(invalid)
        for field, value in (("profile_id", "mild"), ("target", "real_user"),
                             ("calibration", "clinically_validated"), ("automatic_progression", True)):
            invalid = deepcopy(original)
            invalid[field] = value
            invalid_profiles.append(invalid)
        invalid = deepcopy(original)
        del invalid["controls"]["social"]
        invalid_profiles.append(invalid)
        invalid = deepcopy(original)
        invalid["controls"]["memory"]["unsupported_control"] = 1
        invalid_profiles.append(invalid)
        for number, invalid in enumerate(invalid_profiles):
            with self.subTest(case=number):
                self.write(path, invalid)
                self.invoke("validate", success=False)
        self.write(path, original)
        manifest_path = self.root / ".agents" / "alzheimer" / "manifest.json"
        manifest = self.read(manifest_path)
        invalid_manifest = deepcopy(manifest)
        invalid_manifest["profiles"]["moderate"] = "../outside.json"
        self.write(manifest_path, invalid_manifest)
        self.invoke("validate", success=False)
        self.write(manifest_path, manifest)
        preclinical_path = self.profile_path("preclinical")
        preclinical = self.read(preclinical_path)
        changed_preclinical = deepcopy(preclinical)
        changed_preclinical["controls"]["memory"]["recent_episode_window"] = 1
        self.write(preclinical_path, changed_preclinical)
        self.invoke("validate", success=False)
        self.write(preclinical_path, preclinical)
        self.invoke("validate")

    def test_turns_support_and_state_updates_do_not_advance_the_profile(self):
        self.start("mild")
        state = self.read(self.session_path())
        initial = state["affected"]
        state["created_at"] = "2000-01-01T00:00:00Z"
        state["updated_at"] = "2000-01-01T00:00:00Z"
        self.write(self.session_path(), state)
        for support in ("none", "cue", "stepwise", "none"):
            context = self.context(support=support)
            self.assertEqual(context["affected"]["profile"], "mild")
        self.invoke(
            "update-state", "--user", "alice", "--session", "one", "--dimension", "communication",
            "--patch-file", self.input_file({"intent": "继续本轮对话"}),
        )
        self.assertEqual(self.read(self.session_path())["affected"], initial)
        for profile in PROFILES:
            self.assertIs(self.read(self.profile_path(profile))["automatic_progression"], False)


if __name__ == "__main__":
    unittest.main()
