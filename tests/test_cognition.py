"""Exercise the file-backed dialogue protocol through its public CLI.

Each test uses a fresh repository root. No test reads or changes a real user's
state, and no network, model, platform-memory setting, or database is required.
"""

import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
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


class CognitionCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cognition-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(REPO / ".agents", self.root / ".agents")
        (self.root / "state").mkdir()
        self.input_number = 0
        self.original_templates = self.template_hashes(REPO)
        self.copied_templates = self.template_hashes(self.root)

    def tearDown(self):
        self.assertEqual(self.original_templates, self.template_hashes(REPO))
        self.assertEqual(self.copied_templates, self.template_hashes(self.root))

    @staticmethod
    def template_hashes(root):
        return {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / ".agents" / "templates").rglob("*")
            if path.is_file()
        }

    def invoke(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            capture_output=True, text=True, timeout=15,
        )
        if not success:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertTrue(result.stderr.strip(), "Errors must explain the failure")
            return result
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail("Successful CLI calls must return JSON: " + result.stdout[:200])

    def input_file(self, payload, raw=False):
        self.input_number += 1
        directory = self.root / "inputs"
        directory.mkdir(exist_ok=True)
        path = directory / (str(self.input_number) + ".json")
        path.write_text(payload if raw else json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def session_path(self, user="alice", session="one"):
        return self.root / "state" / "users" / user / "sessions" / (session + ".json")

    def memory_path(self, user="alice"):
        return self.root / "state" / "users" / user / "memory.json"

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def start(self, user="alice", session="one", confirmed=True):
        self.invoke("init-session", "--user", user, "--session", session)
        if confirmed:
            self.invoke(
                "confirm-memory", "--user", user, "--session", session,
                "--user-confirmed",
            )

    @staticmethod
    def memory_input(content="用户喜欢咖啡。", **changes):
        payload = {
            "kind": "semantic", "content": content,
            "source": {"kind": "user_statement", "locator": "conversation:turn-1"},
            "confidence": 1.0, "tags": ["饮食"], "valid_until": None,
        }
        payload.update(changes)
        return payload

    def remember(self, payload=None, user="alice", session="one"):
        self.invoke(
            "remember", "--user", user, "--session", session,
            "--input", self.input_file(payload or self.memory_input()),
        )
        return self.read(self.memory_path(user))["records"][-1]

    def context(self, query=None, user="alice", session="one", limit=5):
        args = ["context", "--user", user, "--session", session, "--limit", str(limit)]
        if query is not None:
            args += ["--query", query]
        return self.invoke(*args)

    def test_new_session_requires_explicit_confirmation_for_reads_and_writes(self):
        self.start(confirmed=False)
        state = self.read(self.session_path())
        self.assertEqual(state["memory_gate"]["status"], "pending")
        self.assertIsNone(state["memory_gate"]["confirmed_at"])
        self.assertIsNone(state["memory_gate"]["source"])
        commands = [
            ["context"],
            ["remember", "--input", self.input_file(self.memory_input())],
            ["update-state", "--dimension", "memory", "--patch-file", self.input_file({})],
            ["correct", "--id", "unknown", "--input", self.input_file(self.memory_input())],
            ["forget", "--id", "unknown"],
        ]
        for command in commands:
            with self.subTest(command=command[0]):
                self.invoke(*command, "--user", "alice", "--session", "one", success=False)
        self.invoke("confirm-memory", "--user", "alice", "--session", "one", success=False)
        self.assertEqual(self.read(self.session_path())["memory_gate"]["status"], "pending")

    def test_confirmation_is_a_session_scoped_self_report(self):
        self.start()
        gate = self.read(self.session_path())["memory_gate"]
        self.assertEqual(gate["status"], "user_confirmed_enabled")
        self.assertEqual(gate["source"], "user_self_report")
        self.assertTrue(gate["confirmed_at"])
        self.remember()
        self.start(session="two", confirmed=False)
        self.assertEqual(self.read(self.session_path(session="two"))["memory_gate"]["status"], "pending")
        self.invoke("context", "--user", "alice", "--session", "two", success=False)
        self.invoke("confirm-memory", "--user", "alice", "--session", "two", "--user-confirmed")
        self.assertIn("用户喜欢咖啡。", json.dumps(self.context(session="two"), ensure_ascii=False))

    def test_init_does_not_overwrite_an_existing_session(self):
        self.start()
        before = self.session_path().read_bytes()
        self.invoke("init-session", "--user", "alice", "--session", "one", success=False)
        self.assertEqual(before, self.session_path().read_bytes())

    def test_unsafe_identifiers_cannot_escape_owner_paths(self):
        for identifier in ("../victim", "/tmp/victim", "a/../victim", "..", "a\\victim"):
            for flag in ("--user", "--session"):
                with self.subTest(identifier=identifier, flag=flag):
                    args = {"--user": "alice", "--session": "safe"}
                    args[flag] = identifier
                    self.invoke(
                        "init-session", "--user", args["--user"],
                        "--session", args["--session"], success=False,
                    )
        self.assertFalse((self.root / "state" / "victim").exists())

    def test_context_and_mutations_are_scoped_to_the_user(self):
        self.start()
        alice_record = self.remember(self.memory_input("Alice 私人偏好是咖啡。"))
        self.start(user="bob")
        self.remember(self.memory_input("Bob 私人偏好是红茶。"), user="bob")
        bob_context = json.dumps(self.context(user="bob"), ensure_ascii=False)
        self.assertIn("Bob 私人偏好是红茶。", bob_context)
        self.assertNotIn("Alice 私人偏好是咖啡。", bob_context)
        before = self.memory_path().read_bytes()
        self.invoke("forget", "--user", "bob", "--session", "one", "--id", alice_record["id"], success=False)
        self.invoke(
            "correct", "--user", "bob", "--session", "one", "--id", alice_record["id"],
            "--input", self.input_file(self.memory_input("不应写入。")), success=False,
        )
        self.assertEqual(before, self.memory_path().read_bytes())

    def test_context_rejects_mismatched_owner_metadata(self):
        self.start()
        state = self.read(self.session_path())
        state["user_id"] = "bob"
        self.session_path().write_text(json.dumps(state), encoding="utf-8")
        self.invoke("context", "--user", "alice", "--session", "one", success=False)

    def test_symlinked_state_paths_are_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        users = self.root / "state" / "users"
        users.mkdir()
        (users / "alice").symlink_to(outside, target_is_directory=True)
        self.invoke("init-session", "--user", "alice", "--session", "one", success=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_all_twelve_dimensions_roundtrip_without_changing_stable_persona(self):
        self.start()
        template = self.read(self.root / ".agents" / "templates" / "session.json")
        expected = copy.deepcopy(template["dimensions"])
        persona_path = self.root / ".agents" / "config" / "persona.json"
        persona_before = persona_path.read_bytes()
        patches = {
            "memory": {"last_query": "面试", "pending_clarifications": ["目标岗位尚待确认"]},
            "attention": {"focus": "练习面试", "context_budget": 3, "deferred": ["之后再讨论简历"]},
            "communication": {"detail_level": "brief", "intent": "一次提出一个练习问题", "repair_needed": True},
            "executive": {
                "goal": "完成一次练习", "status": "active", "current_step": "q1",
                "steps": [{"id": "q1", "description": "回答第一题", "status": "active"}],
            },
            "perception": {
                "time_reference": {"value": "2026-10-16", "source": "test-fixture:clock", "timezone": "UTC"},
                "uncertainties": ["用户所在时区未知"],
            },
            "personality": {"context_adjustments": ["本轮按用户要求使用简短表达"]},
            "affect": {
                "user_signal": {"label": "紧张", "basis": "self_report", "source": "test-fixture:turn-1", "confidence": 1.0},
                "response_tone": "supportive", "updated_from": "test-fixture:turn-1",
                "simulation": {"valence": 0.1, "activation": 0.2},
            },
            "motivation": {
                "goals": [{"id": "practice", "description": "完成用户要求的练习", "status": "active", "priority": 1.0}],
                "next_action": "提出第一题",
            },
            "social": {
                "user_claims": [{"content": "用户认为自己回答得不好", "kind": "user_belief", "source": "test-fixture:turn-2", "confidence": 1.0}],
                "interaction_preferences": [{"content": "一次一题", "source": "test-fixture:turn-1"}],
            },
            "self": {"capabilities": ["提出模拟面试问题"], "uncertainties": ["没有招聘方内部评分标准"]},
            "autonomy": {
                "pending_actions": [{"id": "ask1", "description": "提出模拟问题", "status": "planned", "tool": None, "evidence": None}],
            },
            "experience": {
                "feedback": [{"content": "这个节奏合适", "source": "test-fixture:turn-3"}],
                "interaction_load": "low",
                "monitoring": {"memory_supported": True, "files_accessible": True, "tool_results_verified": False},
            },
        }
        self.assertEqual(set(patches), DIMENSIONS)
        for dimension, patch in patches.items():
            with self.subTest(dimension=dimension):
                self.invoke(
                    "update-state", "--user", "alice", "--session", "one",
                    "--dimension", dimension, "--patch-file", self.input_file(patch),
                )
                expected[dimension].update(patch)
        state = self.read(self.session_path())
        self.assertEqual(set(state["dimensions"]), DIMENSIONS)
        self.assertEqual(state["dimensions"], expected)
        context = self.context()
        self.assertEqual(context["dimensions"], expected)
        self.assertEqual(persona_before, persona_path.read_bytes())
        self.invoke("validate")

    def test_context_limit_obeys_current_dialogue_configuration(self):
        self.start()
        config_path = self.root / ".agents" / "config" / "dialogue.json"
        config = self.read(config_path)
        current_max = config["retrieval"]["max_limit"]
        self.context(limit=current_max)
        self.invoke(
            "context", "--user", "alice", "--session", "one",
            "--limit", str(current_max + 1), success=False,
        )
        config["retrieval"]["max_limit"] = 2
        config["retrieval"]["default_limit"] = 2
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self.context(limit=2)
        self.invoke(
            "context", "--user", "alice", "--session", "one",
            "--limit", "3", success=False,
        )

    def test_new_session_personality_uses_current_persona_configuration(self):
        persona_path = self.root / ".agents" / "config" / "persona.json"
        persona = self.read(persona_path)
        persona["profile_id"] = "focused-test-profile"
        persona["version"] = 7
        persona_path.write_text(json.dumps(persona), encoding="utf-8")
        self.start()
        personality = self.read(self.session_path())["dimensions"]["personality"]
        self.assertEqual(personality["profile_id"], "focused-test-profile")
        self.assertEqual(personality["profile_version"], 7)
        self.assertEqual(self.context()["persona"], persona)

    def test_chinese_recall_filters_expired_records_and_obeys_limit(self):
        self.start()
        self.remember(self.memory_input("用户喜欢咖啡，并希望少加糖。"))
        self.remember(self.memory_input("咖啡旧安排已到期。", valid_until="2000-01-01T00:00:00Z"))
        self.remember(self.memory_input("用户会骑自行车。", kind="procedural", tags=["运动"]))
        context = self.context(query="咖啡", limit=1)
        serialized = json.dumps(context, ensure_ascii=False)
        self.assertIn("用户喜欢咖啡，并希望少加糖。", serialized)
        self.assertNotIn("咖啡旧安排已到期。", serialized)
        self.assertNotIn("用户会骑自行车。", serialized)

    def test_correction_replaces_content_and_preserves_auditable_revision(self):
        self.start()
        old = self.remember()
        replacement = self.memory_input(
            "用户现在改喝无咖啡因茶。",
            source={"kind": "user_statement", "locator": "conversation:turn-9-correction"},
        )
        self.invoke(
            "correct", "--user", "alice", "--session", "one", "--id", old["id"],
            "--input", self.input_file(replacement),
        )
        records = self.read(self.memory_path())["records"]
        self.assertEqual(len(records), 1)
        new = records[0]
        self.assertEqual(new["id"], old["id"])
        self.assertEqual(new["created_at"], old["created_at"])
        self.assertEqual(new["revision"], old["revision"] + 1)
        self.assertEqual(new["source"], replacement["source"])
        self.assertEqual(new["content"], replacement["content"])
        self.assertNotIn(old["content"], json.dumps(self.context(), ensure_ascii=False))

    def test_forget_removes_canonical_content_without_echoing_it(self):
        self.start()
        record = self.remember(self.memory_input("要删除的私人内容-蓝色风筝。"))
        result = self.invoke("forget", "--user", "alice", "--session", "one", "--id", record["id"])
        self.assertNotIn(record["content"], json.dumps(result, ensure_ascii=False))
        self.assertEqual(self.read(self.memory_path())["records"], [])
        self.assertNotIn(record["content"], self.memory_path().read_text(encoding="utf-8"))
        self.assertNotIn(record["content"], json.dumps(self.context(), ensure_ascii=False))

    def test_memory_inputs_reject_malformed_data_and_unknown_fields(self):
        self.start()
        invalid = [
            self.memory_input(confidence=1.1),
            self.memory_input(confidence=True),
            self.memory_input(kind="model_guess"),
            self.memory_input(source={"kind": "model_guess", "locator": "guess"}),
            self.memory_input(source={"kind": "user_statement", "locator": ""}),
            self.memory_input(valid_until="tomorrow"),
            self.memory_input(tags="饮食"),
            self.memory_input(unexpected="sensitive-payload-should-not-echo"),
            {"content": "缺少来源与类型。"},
            [],
        ]
        for payload in invalid:
            with self.subTest(payload_type=type(payload).__name__):
                result = self.invoke(
                    "remember", "--user", "alice", "--session", "one",
                    "--input", self.input_file(payload), success=False,
                )
                self.assertNotIn("sensitive-payload-should-not-echo", result.stderr)
        self.invoke(
            "remember", "--user", "alice", "--session", "one",
            "--input", self.input_file("{broken", raw=True), success=False,
        )
        if self.memory_path().exists():
            self.assertEqual(self.read(self.memory_path())["records"], [])

    def test_state_patch_rejects_unknown_dimensions_fields_and_nonobjects(self):
        self.start()
        before = self.session_path().read_bytes()
        for dimension, patch in (
            ("not-a-dimension", {}),
            ("memory", {"unexpected": "do-not-persist"}),
            ("memory", {"memory_gate": {"status": "user_confirmed_enabled"}}),
            ("memory", []),
        ):
            self.invoke(
                "update-state", "--user", "alice", "--session", "one",
                "--dimension", dimension, "--patch-file", self.input_file(patch), success=False,
            )
            self.assertEqual(before, self.session_path().read_bytes())

    def test_validate_detects_corrupted_state_without_repairing_it(self):
        self.start()
        self.remember()
        self.invoke("validate")
        state = self.read(self.session_path())
        del state["dimensions"]["attention"]
        self.session_path().write_text(json.dumps(state), encoding="utf-8")
        before = self.session_path().read_bytes()
        self.invoke("validate", success=False)
        self.assertEqual(before, self.session_path().read_bytes())

    def test_missing_sessions_are_not_silently_created(self):
        self.invoke("context", "--user", "alice", "--session", "missing", success=False)
        self.invoke("confirm-memory", "--user", "alice", "--session", "missing", "--user-confirmed", success=False)
        self.assertFalse(self.session_path(session="missing").exists())

    def test_concurrent_memory_writers_do_not_silently_lose_successful_writes(self):
        self.start()
        inputs = [
            self.input_file(self.memory_input("并发测试记录-" + str(number)))
            for number in range(8)
        ]

        def write(path):
            return subprocess.run(
                [sys.executable, str(CLI), "--root", str(self.root), "remember",
                 "--user", "alice", "--session", "one", "--input", path],
                capture_output=True, text=True, timeout=15,
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(write, inputs))
        succeeded = []
        for path, result in zip(inputs, results):
            if result.returncode == 0:
                json.loads(result.stdout)
                succeeded.append(self.read(Path(path))["content"])
            else:
                # An explicit busy error is safe; an acknowledged lost write is not.
                self.assertTrue(result.stderr.strip())
                self.assertNotIn("Traceback", result.stderr)
        self.assertTrue(succeeded)
        records = self.read(self.memory_path())["records"]
        self.assertEqual(sorted(record["content"] for record in records), sorted(succeeded))
        self.assertEqual(len({record["id"] for record in records}), len(records))


if __name__ == "__main__":
    unittest.main()
