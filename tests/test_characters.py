"""Fiction generation is reproducible data with editable provenance."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import characters  # noqa: E402


CREATED = "2026-10-16T20:00:00Z"
EDITED = "2026-10-16T20:01:00Z"
DIMENSIONS = {
    "memory", "attention", "communication", "executive", "perception", "personality",
    "affect", "motivation", "social", "self", "autonomy", "experience",
}


class CharacterTests(unittest.TestCase):
    def test_generation_is_reproducible_and_records_its_origin(self):
        first = characters.build_background({}, 19, CREATED)
        self.assertEqual(first, characters.build_background({}, 19, CREATED))
        self.assertEqual(first["recipe_version"], 1)
        self.assertEqual(first["seed"], 19)
        self.assertIs(first["generated"], True)
        self.assertEqual(first["revision"], 1)
        self.assertEqual(first["created_at"], CREATED)
        self.assertEqual(first["updated_at"], CREATED)
        self.assertEqual(set(first["dimension_notes"]), DIMENSIONS)
        self.assertTrue(all(isinstance(value, str) and value for value in first["dimension_notes"].values()))
        for path in ("character.name", "scene.setting", "dimension_notes.memory"):
            self.assertEqual(first["provenance"][path]["source_kind"], "generated_fiction")
            self.assertEqual(first["provenance"][path]["recorded_at"], CREATED)

    def test_explicit_false_empty_text_and_empty_experiences_are_preserved(self):
        data = {
            "character": {"based_on_known_person": False, "counterpart_known": False,
                          "name": "自定名字", "speech_style": ""},
            "scene": {"recent_experiences": [], "goal": ""},
            "dimension_notes": {"memory": ""},
        }
        before = deepcopy(data)
        background = characters.build_background(data, 3, CREATED)
        self.assertEqual(data, before)
        for path, expected in (("character.based_on_known_person", False),
                               ("character.counterpart_known", False), ("character.name", "自定名字"),
                               ("character.speech_style", ""), ("scene.recent_experiences", []),
                               ("scene.goal", ""), ("dimension_notes.memory", "")):
            group, field = path.split(".")
            self.assertEqual(background[group][field], expected)
            self.assertEqual(background["provenance"][path]["source_kind"], "user_provided")

    def test_declining_generation_leaves_unknowns_without_fabricating_origin(self):
        background = characters.build_background({"generation": {"fill_missing": False}}, 3, CREATED)
        self.assertIs(background["generated"], False)
        self.assertEqual(background["provenance"]["character.name"]["source_kind"], "unknown")
        self.assertEqual(background["provenance"]["dimension_notes.memory"]["source_kind"], "unknown")

    def test_known_person_missing_details_remain_labelled_fiction(self):
        background = characters.build_background({"character": {"based_on_known_person": True}}, 4, CREATED)
        self.assertIs(background["character"]["based_on_known_person"], True)
        self.assertEqual(background["provenance"]["character.based_on_known_person"]["source_kind"], "user_provided")
        self.assertEqual(background["provenance"]["character.name"]["source_kind"], "generated_fiction")
        self.assertNotIn("diagnosis", background["character"])

    def test_edits_preserve_generation_history_and_unchanged_sources(self):
        background = characters.build_background({}, 8, CREATED)
        before = deepcopy(background)
        patch = {"character": {"name": "用户指定新名字"}, "dimension_notes": {"attention": "用户明确给出的设定"}}
        changed = characters.edit_background(background, patch, EDITED)
        self.assertEqual(background, before)
        for key in ("seed", "recipe_version", "generated", "created_at"):
            self.assertEqual(changed[key], background[key])
        self.assertEqual(changed["updated_at"], EDITED)
        self.assertEqual(changed["revision"], 2)
        self.assertEqual(changed["provenance"]["scene.setting"], background["provenance"]["scene.setting"])
        self.assertEqual(changed["scene"], background["scene"])
        for path in ("character.name", "dimension_notes.attention"):
            self.assertEqual(changed["provenance"][path], {"source_kind": "user_provided", "recorded_at": EDITED})

    def test_invalid_edits_and_narrative_types_are_rejected(self):
        background = characters.build_background({}, 8, CREATED)
        patches = [
            {"seed": 99}, {"character": {"unsupported": "value"}},
            {"character": {"based_on_known_person": "yes"}},
            {"scene": {"recent_experiences": "yesterday"}},
            {"dimension_notes": {"unknown": "unsupported"}},
        ]
        for patch in patches:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    characters.edit_background(background, patch, EDITED)
        with self.assertRaises(ValueError):
            characters.build_background({"generation": {"fill_missing": "yes"}}, 1, CREATED)

    def test_public_validation_requires_exact_provenance_coverage(self):
        background = characters.build_background({}, 8, CREATED)
        characters.validate_background(background)
        invalid = []
        missing_all = deepcopy(background)
        missing_all["provenance"] = {}
        invalid.append(missing_all)
        missing_one = deepcopy(background)
        del missing_one["provenance"]["character.name"]
        invalid.append(missing_one)
        extra = deepcopy(background)
        extra["provenance"]["character.unknown_field"] = {
            "source_kind": "user_provided", "recorded_at": CREATED,
        }
        invalid.append(extra)
        bad_source = deepcopy(background)
        bad_source["provenance"]["character.name"]["source_kind"] = "verified_real_person_fact"
        invalid.append(bad_source)
        for number, value in enumerate(invalid):
            with self.subTest(case=number):
                with self.assertRaises(ValueError):
                    characters.validate_background(value)

    def test_scoped_background_ownership_survives_edits_and_cannot_be_partial(self):
        background = characters.build_background({}, 8, CREATED)
        background.update(user_id="alice", simulation_id="sim_fixture")
        characters.validate_background(background)
        edited = characters.edit_background(background, {"character": {"name": "新名字"}}, EDITED)
        self.assertEqual(edited["user_id"], "alice")
        self.assertEqual(edited["simulation_id"], "sim_fixture")
        del background["simulation_id"]
        with self.assertRaises(ValueError):
            characters.validate_background(background)

    def test_replacing_experiences_does_not_transfer_old_item_provenance(self):
        background = characters.build_background({"scene": {"recent_experiences": [
            {"description": "原来的第一件事", "event_at": "1990-01-01T00:00:00Z", "time_note": "明确旧时间"},
            {"description": "原来的第二件事", "event_at": None, "time_note": "另一条记录"},
        ]}}, 8, CREATED)
        edited = characters.edit_background(background, {"scene": {"recent_experiences": [
            {"description": "明确替换的新经历"},
        ]}}, EDITED)
        self.assertEqual(len(edited["scene"]["recent_experiences"]), 1)
        self.assertIsNone(edited["scene"]["recent_experiences"][0]["event_at"])
        self.assertEqual(edited["provenance"]["scene.recent_experiences.0.description"],
                         {"source_kind": "user_provided", "recorded_at": EDITED})
        self.assertEqual(edited["provenance"]["scene.recent_experiences.0.event_at"]["source_kind"], "unknown")
        self.assertFalse(any(path.startswith("scene.recent_experiences.1.") for path in edited["provenance"]))
        self.assertEqual(edited["provenance"]["character.name"], background["provenance"]["character.name"])


if __name__ == "__main__":
    unittest.main()
