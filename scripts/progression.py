"""Pure, auditable progression for fictional dialogue experiments.

No files, clocks, network calls, clinical estimates or model generation live
here. Callers supply both timestamps and persist the returned state atomically.
Only a new dialogue event can change one dimension by one engineering level.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import random
import re


DIMENSIONS = (
    "memory", "attention", "communication", "executive", "perception",
    "personality", "affect", "motivation", "social", "self", "autonomy",
    "experience",
)
PROFILES = ("baseline", "preclinical", "mild", "moderate", "severe")
MODES = ("default", "fixed", "slow")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
DEFAULT_TRIGGERS = [
    {"id": "context_recall", "terms": ["记得", "以前", "昨天", "刚才", "回家", "回去"]},
]
DEFAULT_CONFIG = {
    "mode": "default",
    "probability": 0.2,
    "cooldown_turns": 3,
    "max_profile": "severe",
    "eligible_dimensions": ["memory", "attention", "communication", "executive"],
    "triggers": DEFAULT_TRIGGERS,
    "onset_days": 10,
    "duration_days": 3,
}


class ProgressionError(ValueError):
    """Safe-to-display input error; never includes the user's narrative."""


def _error(message):
    raise ProgressionError(message)


def _integer(value, minimum=None):
    return type(value) is int and (minimum is None or value >= minimum)


def _number(value, minimum=None, maximum=None):
    if type(value) not in (int, float):
        return False
    try:
        return (math.isfinite(value)
                and (minimum is None or value >= minimum)
                and (maximum is None or value <= maximum))
    except (OverflowError, ValueError):
        return False


def _identifier(value):
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None


def _time(value):
    if not isinstance(value, str) or "T" not in value:
        _error("进展时间必须是带 UTC 时区的 ISO 时间")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        _error("进展时间格式无效")
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        _error("进展时间必须使用 UTC")
    return result.astimezone(timezone.utc)


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def normalize_config(value):
    """Validate a complete config, filling only absent fields with defaults.

    An explicit empty trigger list disables default-mode progression. Probability
    and dialogue cooldown apply only to default mode; slow uses calendar due
    times and one step per new dialogue instead. Step size is always exactly 1.
    """
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - set(DEFAULT_CONFIG):
        _error("进展配置包含未知字段或不是对象")
    config = deepcopy(DEFAULT_CONFIG)
    config.update(deepcopy(value))
    if config["mode"] not in MODES:
        _error("进展模式必须是 default、fixed 或 slow")
    if not _number(config["probability"], 0, 1):
        _error("进展概率必须是 0 到 1 的有限数值")
    if not _integer(config["cooldown_turns"], 0):
        _error("冷却轮数必须是非负整数")
    if config["max_profile"] not in PROFILES:
        _error("进展上限配置无效")
    dimensions = config["eligible_dimensions"]
    if (not isinstance(dimensions, list)
            or any(not isinstance(d, str) or d not in DIMENSIONS for d in dimensions)
            or len(set(dimensions)) != len(dimensions)):
        _error("可进展维度必须是互不重复的有效维度列表")
    if not _number(config["onset_days"], 0):
        _error("首次变化天数必须是非负有限数值")
    if not _number(config["duration_days"], 0) or config["duration_days"] == 0:
        _error("渐变持续天数必须是正有限数值")
    triggers = config["triggers"]
    if not isinstance(triggers, list):
        _error("触发规则必须是列表")
    ids = set()
    for trigger in triggers:
        if not isinstance(trigger, dict) or set(trigger) != {"id", "terms"}:
            _error("触发规则字段无效")
        if not _identifier(trigger["id"]) or trigger["id"] in ids:
            _error("触发规则 ID 无效或重复")
        ids.add(trigger["id"])
        terms = trigger["terms"]
        if (not isinstance(terms, list) or not terms
                or any(not isinstance(term, str) or not term.strip() for term in terms)):
            _error("触发规则需要非空词条列表")
        folded = [term.casefold() for term in terms]
        if len(set(folded)) != len(folded):
            _error("同一触发规则不能包含重复词条")
    return config


def _total_steps(state):
    return len(state["config"]["eligible_dimensions"]) * (
        PROFILES.index(state["config"]["max_profile"])
        - PROFILES.index(state["initial_profile"])
    )


def _onset(seed, config, start):
    lower = max(0, config["onset_days"] - 1)
    upper = config["onset_days"] + 1
    offset = random.Random(str(seed) + ":slow-onset").uniform(lower, upper)
    try:
        return _iso(start + timedelta(days=offset)), offset
    except (OverflowError, ValueError):
        _error("首次变化日期超出可表示范围")


def initialize(config, initial_profile, seed, simulation_start):
    """Create all 12 independent profiles and sample slow onset exactly once."""
    config = normalize_config(config)
    if not isinstance(initial_profile, str) or initial_profile not in PROFILES:
        _error("初始配置无效")
    if PROFILES.index(initial_profile) > PROFILES.index(config["max_profile"]):
        _error("进展上限不能低于初始配置")
    if not _integer(seed):
        _error("进展 seed 必须是整数")
    start = _time(simulation_start)
    onset, offset = (None, None)
    if config["mode"] == "slow":
        onset, offset = _onset(seed, config, start)
        try:
            _time(onset) + timedelta(days=config["duration_days"])
        except (OverflowError, ValueError):
            _error("渐变结束日期超出可表示范围")
    return {
        "schema_version": 1,
        "config": config,
        "initial_profile": initial_profile,
        "seed": seed,
        "dimension_profiles": {d: initial_profile for d in DIMENSIONS},
        "start_at": _iso(start),
        "onset_at": onset,
        "onset_offset_days": offset,
        "dialog_turns": 0,
        "events": [],
        "seen_event_ids": [],
        "last_changed_turn": None,
        "slow_steps": 0,
        "paused": False,
        "last_simulation_at": _iso(start),
    }


def _next_due(state):
    total = _total_steps(state)
    if state["config"]["mode"] != "slow" or state["slow_steps"] >= total:
        return None
    offset = 0 if total <= 1 else (
        state["config"]["duration_days"] * state["slow_steps"] / (total - 1)
    )
    try:
        return _iso(_time(state["onset_at"]) + timedelta(days=offset))
    except (OverflowError, ValueError):
        _error("渐变日程超出可表示范围")


def _validate_event(event, config):
    required = {"event_id", "text", "kind"}
    allowed = required | {"semantic_matches", "simulation_at"}
    if (not isinstance(event, dict) or not required <= set(event)
            or set(event) - allowed):
        _error("进展事件字段无效")
    if not _identifier(event["event_id"]):
        _error("事件 ID 无效")
    if event["kind"] not in ("dialogue", "control"):
        _error("事件类型必须是 dialogue 或 control")
    if not isinstance(event["text"], str) or (
            event["kind"] == "dialogue" and not event["text"].strip()):
        _error("对话事件需要非空文本")
    annotations = event.get("semantic_matches", [])
    configured = {item["id"] for item in config["triggers"]}
    if not isinstance(annotations, list):
        _error("语义命中必须是列表")
    for annotation in annotations:
        if (not isinstance(annotation, dict)
                or set(annotation) != {"trigger_id", "evidence"}
                or not isinstance(annotation["trigger_id"], str)
                or annotation["trigger_id"] not in configured
                or not isinstance(annotation["evidence"], str)
                or not annotation["evidence"].strip()
                or annotation["evidence"] not in event["text"]):
            _error("语义命中必须引用已配置规则及输入中的实际片段")
    normalized = {
        "event_id": event["event_id"], "kind": event["kind"],
        "text": event["text"], "semantic_matches": deepcopy(annotations),
    }
    if "simulation_at" in event:
        normalized["simulation_at"] = _iso(_time(event["simulation_at"]))
    return normalized


def _fingerprint(event):
    payload = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _casefold_evidence(text, term):
    """Return an actual text slice even for casefold expansions, e.g. ß -> ss."""
    pieces = [character.casefold() for character in text]
    folded = "".join(pieces)
    needle = term.casefold()
    position = folded.find(needle)
    if position < 0:
        return None
    offsets = [index for index, piece in enumerate(pieces) for _ in piece]
    return text[offsets[position]:offsets[position + len(needle) - 1] + 1]


def _matches(event, config):
    matches = []
    for trigger in config["triggers"]:
        for term in trigger["terms"]:
            evidence = _casefold_evidence(event["text"], term)
            if evidence is not None:
                matches.append({
                    "trigger_id": trigger["id"], "method": "literal_casefold",
                    "inferred": False, "term": term, "evidence": evidence,
                })
    for annotation in event["semantic_matches"]:
        matches.append({
            "trigger_id": annotation["trigger_id"], "method": "semantic_annotation",
            "inferred": True, "term": None, "evidence": annotation["evidence"],
        })
    return matches


def _candidates(state):
    maximum = PROFILES.index(state["config"]["max_profile"])
    return [dimension for dimension in state["config"]["eligible_dimensions"]
            if PROFILES.index(state["dimension_profiles"][dimension]) < maximum]


def validate_state(state):
    """Validate persisted progression, including the complete transition audit.

    Pause/resume may change only ``paused`` outside ``advance``. Histories are
    replayed to reject inconsistent counters, jumps, out-of-scope dimensions and
    changes hidden in copied state. This is an engineering integrity check.
    """
    required = {
        "schema_version", "config", "initial_profile", "seed", "dimension_profiles",
        "start_at", "onset_at", "onset_offset_days", "dialog_turns", "events",
        "seen_event_ids", "last_changed_turn", "slow_steps", "paused", "last_simulation_at",
    }
    if not isinstance(state, dict) or set(state) != required:
        _error("进展状态字段无效")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        _error("进展状态版本无效")
    config = normalize_config(state["config"])
    if state["config"] != config or not _integer(state["seed"]):
        _error("进展配置或 seed 未规范化")
    initial = state["initial_profile"]
    if not isinstance(initial, str) or initial not in PROFILES:
        _error("进展初始配置无效")
    if PROFILES.index(initial) > PROFILES.index(config["max_profile"]):
        _error("进展上限低于初始配置")
    start = _time(state["start_at"])
    last = _time(state["last_simulation_at"])
    if last < start:
        _error("进展时间早于开始时间")
    if config["mode"] == "slow":
        offset = state["onset_offset_days"]
        if not _number(offset, max(0, config["onset_days"] - 1), config["onset_days"] + 1):
            _error("首次变化偏移超出配置范围")
        try:
            onset = _iso(start + timedelta(days=offset))
            _time(state["onset_at"])
            _time(onset) + timedelta(days=config["duration_days"])
        except (OverflowError, ValueError):
            _error("渐变结束日期超出可表示范围")
        if state["onset_at"] != onset:
            _error("首次变化日期与已记录的抽样偏移不一致")
    elif state["onset_at"] is not None or state["onset_offset_days"] is not None:
        _error("非慢模式不应有首次变化日程")
    if (not _integer(state["dialog_turns"], 0) or not _integer(state["slow_steps"], 0)
            or type(state["paused"]) is not bool
            or (state["last_changed_turn"] is not None
                and not _integer(state["last_changed_turn"], 1))):
        _error("进展计数或暂停状态无效")
    if not isinstance(state["events"], list) or not isinstance(state["seen_event_ids"], list):
        _error("进展事件审核记录无效")
    seen = state["seen_event_ids"]
    if (any(not _identifier(item) for item in seen) or len(set(seen)) != len(seen)
            or len(state["events"]) != len(seen)):
        _error("事件去重记录无效")
    profiles = {dimension: initial for dimension in DIMENSIONS}
    turns, last_change, slow_steps = 0, None, 0
    last_time = start
    reasons = {
        "changed", "control", "fixed", "paused", "cap_reached", "no_trigger",
        "cooldown", "probability_not_met", "before_onset", "not_due",
    }
    for index, decision in enumerate(state["events"]):
        if not isinstance(decision, dict):
            _error("进展审核条目无效")
        keys = {"event_id", "kind", "mode", "recorded_at", "simulation_at", "dialog_turn",
                "reason", "eligible", "matched_triggers", "draw", "seed", "changed",
                "before_profiles", "after_profiles", "input_fingerprint", "schedule_due_at",
                "selection_method"}
        if set(decision) != keys:
            _error("进展审核字段无效")
        if (decision["event_id"] != seen[index] or decision["kind"] not in ("dialogue", "control")
                or decision["mode"] != config["mode"] or decision["seed"] != state["seed"]
                or type(decision["seed"]) is not int
                or not isinstance(decision["reason"], str) or decision["reason"] not in reasons
                or type(decision["eligible"]) is not bool
                or not isinstance(decision["input_fingerprint"], str)
                or re.fullmatch(r"[a-f0-9]{64}", decision["input_fingerprint"]) is None):
            _error("进展审核标识或来源无效")
        timestamp = _time(decision["simulation_at"])
        _time(decision["recorded_at"])
        if timestamp < last_time:
            _error("进展审核时间不能倒退")
        last_time = timestamp
        if decision["kind"] == "dialogue":
            turns += 1
        if type(decision["dialog_turn"]) is not int or decision["dialog_turn"] != turns:
            _error("有效对话计数不一致")
        if decision["before_profiles"] != profiles:
            _error("进展审核的前置维度配置不一致")
        matches = decision["matched_triggers"]
        configured_ids = {item["id"] for item in config["triggers"]}
        if not isinstance(matches, list):
            _error("进展触发审核无效")
        for match in matches:
            if (not isinstance(match, dict)
                    or set(match) != {"trigger_id", "method", "inferred", "term", "evidence"}
                    or not isinstance(match["trigger_id"], str)
                    or match["trigger_id"] not in configured_ids
                    or match["method"] not in ("literal_casefold", "semantic_annotation")
                    or type(match["inferred"]) is not bool
                    or match["inferred"] != (match["method"] == "semantic_annotation")
                    or not isinstance(match["evidence"], str) or not match["evidence"].strip()):
                _error("进展触发审核字段无效")
            terms = next(item["terms"] for item in config["triggers"]
                         if item["id"] == match["trigger_id"])
            if match["method"] == "literal_casefold":
                if (not isinstance(match["term"], str) or match["term"] not in terms
                        or match["term"].casefold() not in match["evidence"].casefold()):
                    _error("字面触发审核与词条不一致")
            elif match["term"] is not None:
                _error("语义标注不能伪装成字面词条")
        draw = decision["draw"]
        if draw is not None:
            if (config["mode"] != "default" or not _number(draw, 0, 1)
                    or draw >= 1 or not matches or not decision["eligible"]):
                _error("进展抽样审核无效")
        reason = decision["reason"]
        if decision["kind"] == "control":
            if reason != "control" or matches or decision["eligible"]:
                _error("控制事件审核不能伪装成对话决策")
        elif reason == "control":
            _error("对话事件不能记为控制事件")
        if config["mode"] == "fixed":
            if decision["kind"] != "control" and reason != "fixed":
                _error("固定模式不得生成进展决策")
        elif reason == "fixed":
            _error("非固定模式不能记为固定模式")
        if config["mode"] == "default":
            if reason in ("before_onset", "not_due") or decision["schedule_due_at"] is not None:
                _error("默认模式不能使用慢模式日程")
            if reason in ("changed", "probability_not_met"):
                if draw is None or not decision["eligible"]:
                    _error("默认模式的合格决策需要唯一抽样记录")
                if reason == "probability_not_met" and draw < config["probability"]:
                    _error("概率未命中的审核结果不一致")
            elif draw is not None or decision["eligible"]:
                _error("不合格事件不得抽样")
            if reason == "no_trigger" and matches:
                _error("无触发结果与触发审核不一致")
            if reason == "cooldown" and (not matches or last_change is None
                    or turns - last_change > config["cooldown_turns"]):
                _error("冷却审核与有效对话间隔不一致")
        else:
            if draw is not None or reason in ("no_trigger", "cooldown", "probability_not_met"):
                _error("非默认模式不能执行概率或对话冷却")
            if decision["eligible"] != (reason == "changed"):
                _error("非默认模式的可进展标记不一致")
        maximum = PROFILES.index(config["max_profile"])
        candidates = [dimension for dimension in config["eligible_dimensions"]
                      if PROFILES.index(profiles[dimension]) < maximum]
        if reason == "cap_reached" and candidates:
            _error("上限审核仍存在可提升维度")
        expected_due = None
        if config["mode"] == "slow":
            total = len(config["eligible_dimensions"]) * (maximum - PROFILES.index(initial))
            if slow_steps < total:
                expected_due = _iso(_time(state["onset_at"]) + timedelta(
                    days=0 if total <= 1 else config["duration_days"] * slow_steps / (total - 1)))
            if reason == "before_onset" and timestamp >= _time(state["onset_at"]):
                _error("首次变化等待状态与时间不一致")
            if reason == "not_due" and (expected_due is None
                    or timestamp < _time(state["onset_at"]) or timestamp >= _time(expected_due)):
                _error("渐变等待状态与时间不一致")
        if decision["schedule_due_at"] != expected_due:
            _error("进展审核中的下次日程不一致")
        changed = decision["changed"]
        if changed is not None:
            if (not isinstance(changed, dict) or set(changed) != {"dimension", "before", "after"}
                    or changed["dimension"] not in config["eligible_dimensions"]
                    or decision["kind"] != "dialogue" or decision["reason"] != "changed"
                    or not decision["eligible"] or config["mode"] == "fixed"):
                _error("进展更改审核无效")
            dimension = changed["dimension"]
            before = profiles[dimension]
            level = PROFILES.index(before)
            if (changed["before"] != before or level >= PROFILES.index(config["max_profile"])
                    or changed["after"] != PROFILES[level + 1]):
                _error("每个事件只能提升一个维度的一级配置")
            if config["mode"] == "default":
                if draw is None or draw >= config["probability"]:
                    _error("默认模式更改缺少有效抽样")
                if last_change is not None and turns - last_change <= config["cooldown_turns"]:
                    _error("默认模式更改违反冷却限制")
                token = str(state["seed"]) + ":" + decision["event_id"] + ":dimension"
                choice = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
                expected_dimension = candidates[choice % len(candidates)]
                if (dimension != expected_dimension
                        or decision["selection_method"] != "seeded_hash_index"):
                    _error("默认模式维度选择与确定性规则不一致")
            else:
                total = len(config["eligible_dimensions"]) * (
                    PROFILES.index(config["max_profile"]) - PROFILES.index(initial))
                due = _time(state["onset_at"]) + timedelta(
                    days=0 if total <= 1 else config["duration_days"] * slow_steps / (total - 1))
                if timestamp < due:
                    _error("慢模式更改早于日程")
                expected_dimension = min(candidates, key=lambda candidate: (
                    PROFILES.index(profiles[candidate]),
                    config["eligible_dimensions"].index(candidate)))
                if (dimension != expected_dimension
                        or decision["selection_method"] != "lowest_level_then_configured_order"):
                    _error("慢模式维度选择与日程规则不一致")
                slow_steps += 1
            profiles[dimension] = changed["after"]
            last_change = turns
        elif decision["reason"] == "changed":
            _error("进展更改缺少具体维度")
        elif decision["selection_method"] is not None:
            _error("未变化事件不应有维度选择记录")
        if decision["after_profiles"] != profiles:
            _error("进展审核的后置维度配置不一致")
        if decision["schedule_due_at"] is not None:
            _time(decision["schedule_due_at"])
        if decision["kind"] == "control" and (draw is not None or changed is not None):
            _error("控制事件不得推进或抽样")
    if (profiles != state["dimension_profiles"] or turns != state["dialog_turns"]
            or last_change != state["last_changed_turn"] or slow_steps != state["slow_steps"]
            or last != last_time):
        _error("当前进展与审核记录不一致")


def advance(state, event, simulation_at, recorded_at):
    """Return ``(new_state, decision)`` without mutating any argument.

    Default mode matches configured context first, observes cooldown, then makes
    exactly one deterministic probability draw. Slow mode uses its stored first
    onset and due schedule, with at most one step per input (no batch catch-up).
    Same-ID/same-input retries are a no-op; conflicting ID reuse is rejected.
    """
    validate_state(state)
    event = _validate_event(event, state["config"])
    when, recorded = _time(simulation_at), _time(recorded_at)
    if "simulation_at" in event and _time(event["simulation_at"]) != when:
        _error("事件时间与调用者的模拟时钟不一致")
    fingerprint = _fingerprint(event)
    new = deepcopy(state)
    config = new["config"]
    decision = {
        "event_id": event["event_id"], "kind": event["kind"], "mode": config["mode"],
        "recorded_at": _iso(recorded), "simulation_at": _iso(when),
        "dialog_turn": new["dialog_turns"], "reason": None, "eligible": False,
        "matched_triggers": [], "draw": None, "seed": new["seed"], "changed": None,
        "before_profiles": deepcopy(new["dimension_profiles"]),
        "after_profiles": deepcopy(new["dimension_profiles"]),
        "input_fingerprint": fingerprint, "schedule_due_at": _next_due(new),
        "selection_method": None,
    }
    if event["event_id"] in new["seen_event_ids"]:
        index = new["seen_event_ids"].index(event["event_id"])
        if new["events"][index]["input_fingerprint"] != fingerprint:
            _error("相同事件 ID 不能用于不同输入")
        decision["reason"] = "duplicate"
        return new, decision
    if when < _time(new["last_simulation_at"]):
        _error("新事件的模拟时间不能倒退")
    if event["kind"] == "dialogue":
        new["dialog_turns"] += 1
        decision["dialog_turn"] = new["dialog_turns"]
        decision["matched_triggers"] = _matches(event, config)
    candidates = _candidates(new)
    selected = None
    if event["kind"] == "control":
        decision["reason"] = "control"
    elif config["mode"] == "fixed":
        decision["reason"] = "fixed"
    elif new["paused"]:
        decision["reason"] = "paused"
    elif not candidates:
        decision["reason"] = "cap_reached"
    elif config["mode"] == "default":
        if not decision["matched_triggers"]:
            decision["reason"] = "no_trigger"
        elif (new["last_changed_turn"] is not None
                and new["dialog_turns"] - new["last_changed_turn"] <= config["cooldown_turns"]):
            decision["reason"] = "cooldown"
        else:
            decision["eligible"] = True
            draw = random.Random(str(new["seed"]) + ":" + event["event_id"]).random()
            decision["draw"] = draw
            if draw >= config["probability"]:
                decision["reason"] = "probability_not_met"
            else:
                # One probability draw only; dimension selection is separately
                # deterministic, auditable and not a second chance to progress.
                token = str(new["seed"]) + ":" + event["event_id"] + ":dimension"
                choice = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
                selected = candidates[choice % len(candidates)]
                decision["selection_method"] = "seeded_hash_index"
    else:
        due = _time(decision["schedule_due_at"])
        if when < _time(new["onset_at"]):
            decision["reason"] = "before_onset"
        elif when < due:
            decision["reason"] = "not_due"
        else:
            decision["eligible"] = True
            selected = min(candidates, key=lambda dimension: (
                PROFILES.index(new["dimension_profiles"][dimension]),
                config["eligible_dimensions"].index(dimension)))
            decision["selection_method"] = "lowest_level_then_configured_order"
    if selected is not None:
        before = new["dimension_profiles"][selected]
        after = PROFILES[PROFILES.index(before) + 1]
        new["dimension_profiles"][selected] = after
        new["last_changed_turn"] = new["dialog_turns"]
        if config["mode"] == "slow":
            new["slow_steps"] += 1
        decision["reason"] = "changed"
        decision["changed"] = {"dimension": selected, "before": before, "after": after}
        decision["after_profiles"] = deepcopy(new["dimension_profiles"])
    new["last_simulation_at"] = _iso(when)
    new["seen_event_ids"].append(event["event_id"])
    new["events"].append(deepcopy(decision))
    validate_state(new)
    return new, decision
