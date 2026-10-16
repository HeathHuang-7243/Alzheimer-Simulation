"""Explicit, uncalibrated AD portrayal presets; never mutate canonical memories."""

from copy import deepcopy
from datetime import datetime, timezone


PROFILES = ("baseline", "preclinical", "mild", "moderate", "severe")
BOUNDED_PROFILES = ("mild", "moderate", "severe")
DEFINITION_VERSION = 1


class ConfigurationError(Exception):
    """A safe-to-display error in the affected layer."""


# Every control is checked, including protections that may never be switched off.
# A tuple means a closed enum; an integer range is identified by a dict.
CONTROL_SPEC = {
    "memory": {
        "recent_episode_window": {"minimum": 0, "nullable": True},
        "semantic_window": {"minimum": 0, "nullable": True},
        "procedural_window": {"minimum": 0, "nullable": True},
        "cue_bonus": {"minimum": 0},
        "encoding": ("ordinary", "effortful", "fragile"),
        "repetition": ("off", "possible", "prominent"),
    },
    "attention": {
        "context_items": {"minimum": 1, "maximum": 20},
        "topic_switching": ("ordinary", "effortful", "difficult"),
    },
    "communication": {
        "word_finding": ("ordinary", "occasional", "frequent", "marked"),
        "utterance_style": ("ordinary", "shorter", "brief_fragments"),
        "comprehension_load": ("ordinary", "single_idea", "single_step"),
    },
    "executive": {
        "planning_steps": {"minimum": 1, "maximum": 20},
        "prompting": ("none", "occasional", "stepwise", "continuous"),
    },
    "perception": {
        "time_orientation": ("ordinary", "uncertain", "often_uncertain"),
        "person_recognition": ("not_assumed_impaired", "case_specific"),
        "scene_tracking": ("ordinary", "needs_explicit_context"),
    },
    "personality": {
        "trait_change": ("not_assumed", "case_specific"),
        "expression_consistency": ("ordinary", "variable"),
        "premorbid_profile_preserved": (True,),
    },
    "affect": {
        "anxiety": ("not_assumed", "case_specific"),
        "irritability": ("not_assumed", "case_specific"),
        "event_recollection_and_affect": ("ordinary", "may_dissociate", "uncertain"),
        "emotion_capacity": ("not_inferred_from_speech",),
    },
    "motivation": {
        "initiation": ("ordinary", "may_need_prompt", "needs_prompt"),
        "sustain_goal": ("ordinary", "variable", "requires_scaffolding"),
        "apathy": ("not_assumed", "case_specific"),
    },
    "social": {
        "perspective_taking": ("ordinary", "may_be_reduced", "variable"),
        "emotional_concern": ("not_assumed_absent",),
        "relationship_recognition": ("ordinary", "case_specific"),
    },
    "self": {
        "error_awareness": ("ordinary", "variable", "may_be_reduced"),
        "autobiographical_detail": ("ordinary", "less_specific", "fragmentary"),
        "identity_erasure": (False,),
    },
    "autonomy": {
        "simulated_task_support": ("independent", "complex_tasks", "basic_tasks", "continuous"),
        "choice_expression": ("retain_when_possible",),
        "real_tool_permissions": ("unchanged",),
    },
    "experience": {
        "self_report": ("ordinary", "supported", "limited"),
        "proxy_equivalence": (False,),
        "subjective_experience": ("unproven",),
        "comfort_priority": (True,),
    },
}


def selection(profile="baseline"):
    if profile not in PROFILES:
        raise ConfigurationError("未知的 AD 工程配置")
    return {"condition": "alzheimer", "profile": profile,
            "definition_version": DEFINITION_VERSION}


def validate_selection(value):
    if not isinstance(value, dict) or set(value) != {"condition", "profile", "definition_version"}:
        raise ConfigurationError("AD 会话选择格式无效")
    if (value["condition"] != "alzheimer" or value["profile"] not in PROFILES
            or type(value["definition_version"]) is not int
            or value["definition_version"] != DEFINITION_VERSION):
        raise ConfigurationError("AD 会话的配置或定义版本无效")


def validate_profile(value, profile_id):
    expected = {"schema_version", "profile_id", "label", "target", "calibration",
                "automatic_progression", "controls", "notes"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ConfigurationError("AD 配置字段不完整或包含未知字段")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["profile_id"] != profile_id or value["target"] != "simulated_agent"
            or value["calibration"] != "uncalibrated_engineering_preset"
            or value["automatic_progression"] is not False
            or not isinstance(value["label"], str) or not value["label"].strip()
            or not isinstance(value["notes"], list)
            or any(not isinstance(note, str) for note in value["notes"])):
        raise ConfigurationError("AD 配置的版本、目标、校准声明或标签无效")
    controls = value["controls"]
    if not isinstance(controls, dict) or set(controls) != set(CONTROL_SPEC):
        raise ConfigurationError("AD 配置必须包含恰好 12 个控制维度")
    for dimension, fields in CONTROL_SPEC.items():
        settings = controls[dimension]
        if not isinstance(settings, dict) or set(settings) != set(fields):
            raise ConfigurationError("AD 维度控制字段无效：" + dimension)
        for key, rule in fields.items():
            setting = settings[key]
            if isinstance(rule, dict):
                valid = (setting is None and rule.get("nullable", False)) or (
                    type(setting) is int and setting >= rule["minimum"]
                    and ("maximum" not in rule or setting <= rule["maximum"]))
            else:
                valid = any(type(setting) is type(allowed) and setting == allowed for allowed in rule)
            if not valid:
                raise ConfigurationError("AD 控制值无效：" + dimension + "." + key)


def validate_catalog(repo, dimensions):
    entry = repo.read(".agents", "manifest.json").get("condition_manifest")
    if entry is not None and entry != ".agents/alzheimer/manifest.json":
        raise ConfigurationError("根 manifest 的 AD 入口路径无效")
    manifest = repo.read(".agents", "alzheimer", "manifest.json")
    if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int
            or manifest.get("schema_version") != 1 or manifest.get("condition") != "alzheimer"
            or manifest.get("target") != "simulated_agent"
            or type(manifest.get("definition_version")) is not int
            or manifest.get("definition_version") != DEFINITION_VERSION
            or manifest.get("default_profile") != "baseline"
            or manifest.get("automatic_progression") is not False):
        raise ConfigurationError("AD manifest 的版本、目标或默认配置无效")
    paths = manifest.get("profiles")
    if not isinstance(paths, dict) or set(paths) != set(PROFILES):
        raise ConfigurationError("AD manifest 必须声明五个完整配置")
    definitions = manifest.get("dimensions")
    if (not isinstance(definitions, list) or len(definitions) != len(dimensions)
            or {item.get("id") for item in definitions if isinstance(item, dict)} != set(dimensions)):
        raise ConfigurationError("AD manifest 必须声明恰好 12 个维度定义")
    for item in definitions:
        path = item.get("definition")
        if (not isinstance(item.get("label"), str) or not item["label"].strip()
                or not isinstance(path, str) or not path.startswith(".agents/alzheimer/definitions/")
                or not repo.path(path).is_file()):
            raise ConfigurationError("AD 维度定义文件不存在或路径无效")
    profiles = {}
    for profile_id, path in paths.items():
        if not isinstance(path, str) or not path.startswith(".agents/alzheimer/profiles/"):
            raise ConfigurationError("AD 配置路径无效")
        value = repo.read(path)
        validate_profile(value, profile_id)
        profiles[profile_id] = value
    if profiles["preclinical"]["controls"] != profiles["baseline"]["controls"]:
        raise ConfigurationError("症状前配置必须与母版使用相同控制，不强制可见损伤")
    return manifest, profiles


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def actor_records(records, profile, support, limit):
    """Filter active records by kind+recency before lexical retrieval; no mutation."""
    controls = profile["controls"]
    bonus = controls["memory"]["cue_bonus"] if support in ("cue", "stepwise") else 0
    windows = {
        "episodic": controls["memory"]["recent_episode_window"],
        "semantic": controls["memory"]["semantic_window"],
        "procedural": controls["memory"]["procedural_window"],
    }
    windows = {kind: None if cap is None else cap + bonus for kind, cap in windows.items()}
    instant = datetime.now(timezone.utc)
    active = [record for record in records
              if record["valid_until"] is None or _time(record["valid_until"]) > instant]
    selected = []
    for kind, cap in windows.items():
        candidates = sorted((record for record in active if record["kind"] == kind),
                            key=lambda record: (_time(record["updated_at"]), record["id"]), reverse=True)
        selected.extend(candidates if cap is None else candidates[:cap])
    effective_limit = min(limit, controls["attention"]["context_items"] + bonus)
    return selected, effective_limit, windows, bonus


def context_rules(manifest, profile, view, support, limit, windows=None, bonus=0):
    bounded = view == "actor" and profile["profile_id"] in BOUNDED_PROFILES
    guidance = [
        "仅模拟 AI 角色；这些预设未经临床校准，不能判断真实用户的疾病或阶段。",
        "数字窗口和步骤上限是工程参数，不代表测得的患者能力或概率。",
        "语言、情绪、人格表达等由宿主依据各维度定义呈现；文件助手不会自动生成这些表现。",
        "真实权限、门禁、记忆纠错删除、工具结果和宿主身份必须准确，不参与角色能力衰减。",
        "隐藏角色视图记录不会擦除既有对话、宿主上下文、平台记忆或模型权重中的信息。",
    ]
    if view == "controller":
        guidance.append("这是出戏的控制器视图；用于维护和核验，不直接作为受影响角色的可回忆内容。")
    else:
        guidance.append("受影响角色只使用本次可见记忆；不要利用此前见过的控制器记录补回被排除内容。")
    if support == "cue" and bounded:
        guidance.append("本轮有明确线索支持；窗口仅增加一次 cue_bonus，不假定完全恢复。")
    elif support == "stepwise" and bounded:
        guidance.append("本轮有逐步支持；窗口仅增加一次 cue_bonus，分步解释但不虚构已完成行动。")
    elif support != "none":
        guidance.append("支持标签已记录；对照或控制器视图不应用角色窗口加成，也不虚构已完成行动。")
    return {
        **selection(profile["profile_id"]), "label": profile["label"], "target": profile["target"],
        "calibration": profile["calibration"], "automatic_progression": False,
        "view": view, "support": support, "controls": deepcopy(profile["controls"]),
        "definitions": {item["id"]: item["definition"] for item in manifest["dimensions"]},
        "mechanical_effects": {
            "memory_window_applied": bounded, "attention_limit_applied": bounded,
            "effective_memory_windows": windows, "effective_context_limit": limit,
            "cue_bonus_applied": bonus,
            "retrieval_order": "expire_then_kind_recency_caps_then_lexical_limit" if bounded else "normal_lexical_limit",
        },
        "host_model_effects": list(CONTROL_SPEC), "guidance": guidance,
    }
