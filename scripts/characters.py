"""Pure, provenance-preserving fictional scenario construction.

Only the bundled fictional bank is read.  These helpers never inspect personal
state, infer diagnoses, or write files.  Narrative defaults are scenario material,
not verified facts about a known person or a source of clinical profile selection.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import random
import re


DIMENSIONS = (
    "memory", "attention", "communication", "executive", "perception",
    "personality", "affect", "motivation", "social", "self", "autonomy",
    "experience",
)
RECIPE_VERSION = 1
BANK_PATH = Path(__file__).resolve().parents[1] / ".agents" / "scenario" / "character-bank.json"
CHARACTER_FIELDS = (
    "based_on_known_person", "counterpart_known", "recognizes_counterpart",
    "name", "premorbid_personality", "speech_style", "interests", "identity",
)
SCENE_FIELDS = ("setting", "first_meeting", "recent_experiences", "goal")
EXPERIENCE_FIELDS = ("description", "event_at", "time_note")
SOURCE_KINDS = {"user_provided", "generated_fiction", "unknown"}
_KNOWN_PERSON_PREFIX = "【虚构替代，非真人事实】"
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)")


def _timestamp(value):
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("a UTC timestamp is required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        raise ValueError("a UTC timestamp is required") from None
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("a UTC timestamp is required")
    return value


def _datetime(value):
    value = _timestamp(value)
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def _object(value, allowed, label):
    if not isinstance(value, dict) or any(key not in allowed for key in value):
        raise ValueError("invalid " + label + " fields")
    return value


def _validate_value(group, field, value):
    if group == "character" and field in {"based_on_known_person", "counterpart_known"}:
        if not isinstance(value, bool):
            raise ValueError("character flags must be booleans")
    elif group == "character" and field == "recognizes_counterpart":
        if not isinstance(value, str) or value not in {"yes", "no", "unknown"}:
            raise ValueError("invalid counterpart recognition")
    elif group == "scene" and field == "recent_experiences":
        if not isinstance(value, list):
            raise ValueError("recent experiences must be an array")
        for entry in value:
            _object(entry, EXPERIENCE_FIELDS, "recent experience")
            for key, item in entry.items():
                if key == "event_at":
                    if item is not None:
                        _timestamp(item)
                elif not isinstance(item, str):
                    raise ValueError("recent experience text must be a string")
    elif not isinstance(value, str):
        raise ValueError("background text must be a string")


def _load_profile(seed):
    try:
        bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
        if bank.get("schema_version") != 1 or bank.get("recipe_version") != RECIPE_VERSION:
            raise ValueError
        profiles = bank["profiles"]
        if not isinstance(profiles, list) or not profiles:
            raise ValueError
        profile = random.Random(seed).choice(profiles)
        for group, fields in (("character", CHARACTER_FIELDS[3:]), ("scene", SCENE_FIELDS),
                              ("dimension_notes", DIMENSIONS)):
            if not isinstance(profile[group], dict) or set(profile[group]) != set(fields):
                raise ValueError
            for field in fields:
                _validate_value(group, field, profile[group][field])
        return profile
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("fictional character bank is unavailable or malformed") from None


def _stamp(provenance, path, kind, recorded_at):
    provenance[path] = {"source_kind": kind, "recorded_at": recorded_at}


def _adapt_profile(profile, groups):
    """Keep fictional defaults coherent with explicitly supplied constraints."""
    profile = deepcopy(profile)
    character = groups["character"]
    scene = groups["scene"]
    if "first_meeting" in scene and "setting" not in scene:
        profile["scene"]["setting"] = "以用户提供的初遇情境为准，未另行指定具体地点。"
    if "goal" in scene:
        profile["dimension_notes"]["executive"] = "任务以用户明确给出的对话目标为准；当前步骤、支持需求与真实完成情况分别记录。"
    if "setting" in scene or "first_meeting" in scene:
        profile["scene"]["first_meeting"] = "对话者在用户提供的场景中与角色开始交流，不补造此前共同经历。"
        profile["scene"]["recent_experiences"] = [{
            "description": "角色来到所设场景，准备选择一个愿意交谈的话题。",
            "event_at": None, "time_note": "本场景开始前不久，具体时刻未设定",
        }]
        profile["scene"]["goal"] = "围绕用户设定的场景自然交谈，保留角色选择话题或停止的机会。"
        profile["dimension_notes"]["attention"] = "当前关注用户设定的场景；信息负荷与提示依实际互动和所选预设决定。"
        profile["dimension_notes"]["perception"] = "以用户提供的场景描述为约束；未给或空白地点保持未设定，不另补精确位置或感官能力。"
        profile["dimension_notes"]["executive"] = "任务以用户确认的场景目标为准；没有实际完成的步骤不得报告为完成。"
    if character.get("counterpart_known") is True:
        profile["scene"]["first_meeting"] = "双方已有认识关系；本次是否辨认对方依明确设置，不补造具体共同往事。"
        profile["dimension_notes"]["social"] = "双方认识，但熟悉程度、称呼和共同经历未提供的部分仍未知；认识与当前辨认能力分开。"
    elif character.get("recognizes_counterpart") == "no":
        profile["dimension_notes"]["social"] = "本场景明确设置角色暂不辨认对话者；不据此推断没有情感或补造双方过往关系。"
    for field, dimension in (("premorbid_personality", "personality"), ("speech_style", "communication"),
                             ("identity", "self"), ("interests", "motivation")):
        if field in character:
            profile["dimension_notes"][dimension] = {
                "personality": "病前倾向以用户提供的人格描述为准；显式空白表示未提供，不用模板人格代填，不把当前失误解释成品格。",
                "communication": "惯常表达以用户提供的说话方式为准；显式空白保持未说明，当前表现仍受所选预设约束。",
                "self": "角色身份以用户明确提供的内容为准；不从代称、兴趣或语气推断完整生平与诊断。",
                "motivation": "兴趣以用户提供的内容为准；显式空白不等于没有兴趣，具体是否参与由角色选择和场景决定。",
            }[dimension]
    if any(field in character for field in ("identity", "interests")) or any(field in scene for field in ("setting", "first_meeting")):
        profile["dimension_notes"]["memory"] = "熟悉背景以当前已确认资料为准；未提供的知识不补造成真人事实，近期回忆与技能表现由所选视图和预设决定。"
    return profile


def _experiences(value, kind, recorded_at, provenance, known_person=False):
    """Replace an event list; missing dates remain unknown, never fabricated."""
    path = "scene.recent_experiences"
    _stamp(provenance, path, kind, recorded_at)
    result = []
    for index, entry in enumerate(value):
        item = {}
        for field in EXPERIENCE_FIELDS:
            supplied = field in entry
            field_value = deepcopy(entry[field]) if supplied else (None if field == "event_at" else "")
            field_kind = kind if supplied else "unknown"
            if field == "event_at" and field_value is None:
                field_kind = "user_provided" if supplied and kind == "user_provided" else "unknown"
            if known_person and field_kind == "generated_fiction" and isinstance(field_value, str):
                field_value = _KNOWN_PERSON_PREFIX + field_value
            item[field] = field_value
            _stamp(provenance, path + "." + str(index) + "." + field, field_kind, recorded_at)
        result.append(item)
    return result


def build_background(data, seed, recorded_at):
    """Normalize setup into an independent background with per-field sources.

    Explicit supported values, including false, empty strings and empty event
    arrays, are never treated as missing.  Unknown narrative fields become empty
    strings when fill_missing is false; timestamps never become fictional dates.
    """
    recorded_at = _timestamp(recorded_at)
    if not isinstance(data, dict):
        raise ValueError("setup must be an object")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    generation = _object(data.get("generation", {}), {"fill_missing"}, "generation")
    fill_missing = generation.get("fill_missing", True)
    if not isinstance(fill_missing, bool):
        raise ValueError("fill_missing must be a boolean")
    groups = {
        "character": _object(data.get("character", {}), CHARACTER_FIELDS, "character"),
        "scene": _object(data.get("scene", {}), SCENE_FIELDS, "scene"),
        "dimension_notes": _object(data.get("dimension_notes", {}), DIMENSIONS, "dimension note"),
    }
    for group, values in groups.items():
        for field, value in values.items():
            _validate_value(group, field, value)
    profile = _adapt_profile(_load_profile(seed), groups) if fill_missing else None
    known_person = groups["character"].get("based_on_known_person", False)
    provenance = {}
    result = {
        "recipe_version": RECIPE_VERSION, "seed": seed, "generated": False,
        "character": {}, "scene": {}, "dimension_notes": {},
        "provenance": provenance, "created_at": recorded_at,
        "updated_at": recorded_at, "revision": 1,
    }
    flag_defaults = {"based_on_known_person": False, "counterpart_known": False,
                     "recognizes_counterpart": "unknown"}
    for group, fields in (("character", CHARACTER_FIELDS), ("scene", SCENE_FIELDS),
                          ("dimension_notes", DIMENSIONS)):
        for field in fields:
            if field in groups[group]:
                value = deepcopy(groups[group][field])
                kind = "user_provided"
            elif group == "character" and field in flag_defaults:
                value, kind = flag_defaults[field], "unknown"
            elif fill_missing:
                value = deepcopy(profile[group][field])
                kind = "generated_fiction"
            else:
                value = [] if field == "recent_experiences" else ""
                kind = "unknown"
            if field == "recent_experiences":
                value = _experiences(value, kind, recorded_at, provenance, known_person)
            else:
                if known_person and kind == "generated_fiction":
                    value = _KNOWN_PERSON_PREFIX + value
                _stamp(provenance, group + "." + field, kind, recorded_at)
            result[group][field] = value
    result["generated"] = any(item["source_kind"] == "generated_fiction" for item in provenance.values())
    validate_background(result)
    return result


def validate_background(background):
    """Validate current values, complete provenance coverage and metadata.

    Optional ownership fields must occur together.  Matching them to the active
    user/run is the caller's responsibility.  Source labels are an audit record,
    not cryptographic authentication of user-supplied claims or hand-edited files.
    """
    if not isinstance(background, dict):
        raise ValueError("background must be an object")
    required = {"recipe_version", "seed", "generated", "character", "scene", "dimension_notes",
                "provenance", "created_at", "updated_at", "revision"}
    ownership = {"user_id", "simulation_id"}
    if not required.issubset(background) or set(background) - required - ownership:
        raise ValueError("invalid background metadata fields")
    present_owner = ownership.intersection(background)
    if present_owner and present_owner != ownership:
        raise ValueError("incomplete background ownership")
    for field in present_owner:
        if not isinstance(background[field], str) or _SAFE_ID.fullmatch(background[field]) is None:
            raise ValueError("invalid background ownership")
    if type(background.get("recipe_version")) is not int or background["recipe_version"] != RECIPE_VERSION:
        raise ValueError("invalid background recipe version")
    if not isinstance(background.get("seed"), int) or isinstance(background.get("seed"), bool):
        raise ValueError("invalid background seed")
    if not isinstance(background.get("generated"), bool):
        raise ValueError("invalid generation metadata")
    revision = background.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("invalid background revision")
    created = _datetime(background["created_at"])
    updated = _datetime(background["updated_at"])
    if updated < created:
        raise ValueError("background timestamps are out of order")
    expected_paths = set()
    for group, fields in (("character", CHARACTER_FIELDS), ("scene", SCENE_FIELDS),
                          ("dimension_notes", DIMENSIONS)):
        values = _object(background.get(group), fields, group)
        if set(values) != set(fields):
            raise ValueError("incomplete background fields")
        for field, value in values.items():
            _validate_value(group, field, value)
            path = group + "." + field
            expected_paths.add(path)
            if group == "scene" and field == "recent_experiences":
                for index, entry in enumerate(value):
                    if set(entry) != set(EXPERIENCE_FIELDS):
                        raise ValueError("incomplete recent experience fields")
                    expected_paths.update(path + "." + str(index) + "." + key for key in EXPERIENCE_FIELDS)
    provenance = background.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != expected_paths:
        raise ValueError("background provenance must cover exactly the current fields")
    for item in provenance.values():
        if (not isinstance(item, dict) or set(item) != {"source_kind", "recorded_at"}
                or not isinstance(item.get("source_kind"), str)
                or item["source_kind"] not in SOURCE_KINDS):
            raise ValueError("invalid background provenance")
        source_time = _datetime(item["recorded_at"])
        if not created <= source_time <= updated:
            raise ValueError("background source timestamp is outside the record lifetime")
        if item["source_kind"] == "generated_fiction" and not background["generated"]:
            raise ValueError("generation metadata conflicts with current sources")


def edit_background(background, patch, recorded_at):
    """Return a copy with supplied fields marked user-provided, without re-roll.

    Generation metadata remains historical even after every generated field has
    been replaced.  Replacing the event array removes obsolete event provenance.
    """
    recorded_at = _timestamp(recorded_at)
    validate_background(background)
    _object(patch, {"character", "scene", "dimension_notes"}, "background patch")
    field_sets = {"character": CHARACTER_FIELDS, "scene": SCENE_FIELDS,
                  "dimension_notes": DIMENSIONS}
    for group, values in patch.items():
        _object(values, field_sets[group], group)
        for field, value in values.items():
            _validate_value(group, field, value)
    result = deepcopy(background)
    for group, values in patch.items():
        for field, value in values.items():
            path = group + "." + field
            if field == "recent_experiences":
                for key in list(result["provenance"]):
                    if key == path or key.startswith(path + "."):
                        del result["provenance"][key]
                result[group][field] = _experiences(value, "user_provided", recorded_at, result["provenance"])
            else:
                result[group][field] = deepcopy(value)
                _stamp(result["provenance"], path, "user_provided", recorded_at)
    result["revision"] += 1
    result["updated_at"] = recorded_at
    validate_background(result)
    return result
