#!/usr/bin/env python3
"""Scenario-led, file-only simulations. No model calls, databases, or networking."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import secrets
import shutil
import sys
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import alzheimer
import characters
import cognition
import progression


DIMENSIONS = cognition.DIMENSIONS
Error = cognition.Error
now = cognition.now
timestamp = cognition.timestamp
identifier = cognition.identifier
read_json = cognition.read_json
SOURCE_KINDS = ("user_statement", "tool_result", "generated_fiction", "user_inferred")


def integer(value, minimum=None):
    return type(value) is int and (minimum is None or value >= minimum)


def object_keys(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise Error("JSON 对象含未知字段或缺少必需字段")


def check_times(value, fields):
    for field in fields:
        timestamp(value.get(field))
    if value.get("event_at") is not None:
        timestamp(value["event_at"])


def clock_config(value, active=False):
    if value is None:
        value = {}
    object_keys(value, ("mode", "start_at", "timezone"))
    mode = value.get("mode", "real")
    if mode not in ("real", "manual"):
        raise Error("时钟模式仅支持 real 或 manual")
    zone = value.get("timezone", "UTC")
    if not isinstance(zone, str) or not zone:
        raise Error("时区必须是有效的 IANA 时区名称")
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise Error("时区名称无效或本机缺少该时区资料") from None
    start = value.get("start_at")
    if start is not None:
        start = timestamp(start).isoformat().replace("+00:00", "Z")
    if mode == "manual" and start is None:
        raise Error("手动时钟须显式提供 UTC start_at")
    if mode == "real" and start is not None and not active:
        raise Error("实时时钟在启动时取实际 UTC；自定 start_at 请使用 manual 模式")
    return {"mode": mode, "start_at": start, "timezone": zone}


def normalize_setup(data):
    object_keys(data, ("character", "scene", "dimension_notes", "generation", "initial_profile", "progression", "clock"))
    generation = data.get("generation", {})
    object_keys(generation, ("fill_missing",))
    fill = generation.get("fill_missing", True)
    if type(fill) is not bool:
        raise Error("fill_missing 必须是布尔值")
    initial = data.get("initial_profile", "mild")
    if initial not in alzheimer.PROFILES:
        raise Error("初始工程配置无效")
    config = progression.normalize_config(data.get("progression", {}))
    if alzheimer.PROFILES.index(initial) > alzheimer.PROFILES.index(config["max_profile"]):
        raise Error("进展上限不能低于初始配置")
    return {"initial_profile": initial, "progression": config,
            "clock": clock_config(data.get("clock", {})), "generation": {"fill_missing": fill}}


def validate_background(value, user=None, simulation=None):
    characters.validate_background(value)
    if user is not None and (value.get("user_id") != user or value.get("simulation_id") != simulation):
        raise Error("背景记录所属用户或模拟不匹配")


class Store(cognition.Repository):
    def base(self, user):
        identifier(user)
        return self.path("state", "users", user, "simulations")

    def draft_path(self, user, simulation):
        identifier(simulation)
        return self.path(self.base(user).relative_to(self.root), "drafts", simulation + ".json")

    def run_path(self, user, simulation, *parts):
        identifier(simulation)
        return self.path(self.base(user).relative_to(self.root), "runs", simulation, *parts)

    def active_path(self, user):
        return self.path(self.base(user).relative_to(self.root), "active.json")

    def read_path(self, path):
        return read_json(self.path(path.relative_to(self.root)))

    def draft(self, user, simulation):
        value = self.read_path(self.draft_path(user, simulation))
        object_keys(value, ("schema_version", "user_id", "simulation_id", "status", "seed", "setup",
                            "background", "created_at", "updated_at", "activated_at"),
                    ("schema_version", "user_id", "simulation_id", "status", "seed", "setup",
                     "background", "created_at", "updated_at", "activated_at"))
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["user_id"] != user or value["simulation_id"] != simulation
                or value["status"] not in ("draft", "activated") or not integer(value["seed"])):
            raise Error("草稿身份、版本或状态无效")
        check_times(value, ("created_at", "updated_at"))
        if value["activated_at"] is not None:
            timestamp(value["activated_at"])
        if (value["status"] == "draft") != (value["activated_at"] is None):
            raise Error("草稿激活记录不一致")
        setup = value["setup"]
        object_keys(setup, ("initial_profile", "progression", "clock", "generation"),
                    ("initial_profile", "progression", "clock", "generation"))
        if normalize_setup(setup) != setup:
            raise Error("草稿设置未规范化")
        validate_background(value["background"], user, simulation)
        if value["background"]["seed"] != value["seed"]:
            raise Error("背景生成种子与草稿不一致")
        return value

    def pointer(self, user):
        value = self.read_path(self.active_path(user))
        object_keys(value, ("schema_version", "user_id", "simulation_id", "created_at", "updated_at"),
                    ("schema_version", "user_id", "simulation_id", "created_at", "updated_at"))
        if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["user_id"] != user:
            raise Error("活动指针身份或版本无效")
        identifier(value["simulation_id"])
        check_times(value, ("created_at", "updated_at"))
        return value

    def run(self, user, simulation):
        if self.pointer(user)["simulation_id"] != simulation:
            raise Error("仅可访问该用户当前活动的 simulation_id")
        value = self.read_path(self.run_path(user, simulation, "run.json"))
        required = {"schema_version", "user_id", "simulation_id", "status", "seed", "initial_profile", "clock",
                    "memory_gate", "created_at", "updated_at", "recorded_at", "simulation_at", "progression"}
        object_keys(value, required, required)
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["user_id"] != user or value["simulation_id"] != simulation
                or value["status"] != "active" or not integer(value["seed"])
                or value["initial_profile"] not in alzheimer.PROFILES):
            raise Error("活动模拟身份、版本或状态无效")
        check_times(value, ("created_at", "updated_at", "recorded_at", "simulation_at"))
        if clock_config(value["clock"], active=True) != value["clock"]:
            raise Error("活动时钟配置无效")
        gate = value["memory_gate"]
        object_keys(gate, ("status", "confirmed_at", "source"), ("status", "confirmed_at", "source"))
        if gate["status"] != "user_confirmed_enabled" or gate["source"] != "user_self_report":
            raise Error("需要当前模拟的用户记忆设置明确确认")
        timestamp(gate["confirmed_at"])
        self.validate_progression(value)
        return value

    def validate_progression(self, run):
        state = run["progression"]
        progression.validate_state(state)
        if not isinstance(state, dict) or state.get("seed") != run["seed"]:
            raise Error("进展状态或种子无效")
        profiles = state.get("dimension_profiles")
        if (not isinstance(profiles, dict) or set(profiles) != set(DIMENSIONS)
                or any(profile not in alzheimer.PROFILES for profile in profiles.values())
                or not integer(state.get("dialog_turns"), 0) or type(state.get("paused")) is not bool
                or not isinstance(state.get("events"), list) or not isinstance(state.get("seen_event_ids"), list)):
            raise Error("进展维度、计数或事件结构无效")
        if progression.normalize_config(state.get("config")) != state["config"]:
            raise Error("进展配置未规范化")
        for field in ("start_at", "last_simulation_at"):
            timestamp(state.get(field))
        if state.get("onset_at") is not None:
            timestamp(state["onset_at"])
        seen = state["seen_event_ids"]
        if len(set(seen)) != len(seen):
            raise Error("进展事件 ID 重复")
        for event_id in seen:
            identifier(event_id)
        if state["last_simulation_at"] != run["simulation_at"]:
            raise Error("模拟时钟与进展状态不一致")

    def dimension(self, user, simulation, dimension):
        value = self.read_path(self.run_path(user, simulation, "dimensions", dimension + ".json"))
        self.validate_dimension(value, user, simulation, dimension)
        return value

    def validate_dimension(self, value, user, simulation, dimension):
        required = {"schema_version", "user_id", "simulation_id", "dimension", "created_at", "updated_at",
                    "recorded_at", "event_at", "simulation_at", "revision", "value", "source"}
        object_keys(value, required, required)
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["user_id"] != user or value["simulation_id"] != simulation
                or value["dimension"] != dimension or not integer(value["revision"], 1)):
            raise Error("维度记录身份、版本或修订号无效")
        check_times(value, ("created_at", "updated_at", "recorded_at", "simulation_at"))
        source = value["source"]
        object_keys(source, ("kind", "locator"), ("kind", "locator"))
        if source["kind"] not in ("project_template", "explicit_state_update") or not isinstance(source["locator"], str) or not source["locator"]:
            raise Error("维度来源无效")
        schema = self.schema("session")
        cognition.validate_value(value["value"], schema["properties"]["dimensions"]["properties"][dimension], schema)

    def background(self, user, simulation):
        value = self.read_path(self.run_path(user, simulation, "background.json"))
        validate_background(value, user, simulation)
        if value["seed"] != self.run(user, simulation)["seed"]:
            raise Error("背景生成种子与当前模拟不匹配")
        return value

    def memory(self, user, simulation):
        value = self.read_path(self.run_path(user, simulation, "memory.json"))
        self.validate_memories(value, user, simulation)
        return value

    def validate_memories(self, value, user, simulation):
        object_keys(value, ("schema_version", "user_id", "simulation_id", "records"),
                    ("schema_version", "user_id", "simulation_id", "records"))
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["user_id"] != user or value["simulation_id"] != simulation
                or not isinstance(value["records"], list)):
            raise Error("记忆文件身份或结构无效")
        ids = set()
        for record in value["records"]:
            fields = {"kind", "content", "source", "confidence", "tags", "valid_until", "event_at", "event_time_note",
                      "id", "simulation_id", "recorded_at", "created_at", "updated_at", "simulation_at", "revision"}
            object_keys(record, fields, fields)
            identifier(record["id"])
            if record["id"] in ids or record["simulation_id"] != simulation or not integer(record["revision"], 1):
                raise Error("记忆 ID、所属模拟或修订号无效")
            ids.add(record["id"])
            validate_memory_input(self, {key: record[key] for key in (
                "kind", "content", "source", "confidence", "tags", "valid_until", "event_at", "event_time_note")})
            check_times(record, ("created_at", "updated_at", "recorded_at", "simulation_at"))


def validate_memory_input(repo, value):
    fields = {"kind", "content", "source", "confidence", "tags", "valid_until", "event_at", "event_time_note"}
    object_keys(value, fields, ("kind", "content", "source", "confidence"))
    result = deepcopy(value)
    result.setdefault("tags", [])
    result.setdefault("valid_until", None)
    result.setdefault("event_at", None)
    result.setdefault("event_time_note", None)
    source = result["source"]
    object_keys(source, ("kind", "locator"), ("kind", "locator"))
    if source["kind"] not in SOURCE_KINDS:
        raise Error("记忆来源种类无效")
    schema = repo.schema("memory-input")
    schema["properties"]["source"]["properties"]["kind"]["enum"] = list(SOURCE_KINDS)
    core = {key: result[key] for key in ("kind", "content", "source", "confidence", "tags", "valid_until")}
    cognition.validate_value(core, schema)
    if result["event_at"] is not None:
        timestamp(result["event_at"])
    if result["event_time_note"] is not None and not isinstance(result["event_time_note"], str):
        raise Error("event_time_note 必须是字符串或 null")
    return result


def simulation_time(run):
    return now() if run["clock"]["mode"] == "real" else run["simulation_at"]


def setup_card(draft):
    return {"simulation_id": draft["simulation_id"], "status": draft["status"], "setup": draft["setup"],
            "background": draft["background"], "seed": draft["seed"],
            "requires_confirmation": draft["status"] == "draft",
            "notice": "背景是可编辑的场景约束；generated_fiction 不是真实用户事实。开始需要确认场景及开启平台记忆的自述。"}


def start_run(repo, args):
    if not args.confirmed or not args.user_confirmed_memory:
        raise Error("开始前须明确确认场景卡，并确认已开启平台记忆；工具不能检测设置")
    with repo.lock(repo.active_path(args.user)):
        draft = repo.draft(args.user, args.simulation)
        if draft["status"] != "draft":
            raise Error("该草稿已启动，不能重复启动并清空状态；请使用 resume")
        old_pointer = repo.pointer(args.user) if repo.active_path(args.user).exists() else None
        if old_pointer and old_pointer["simulation_id"] == args.simulation:
            raise Error("该模拟已处于活动状态，拒绝再次重置")
        old = None
        if old_pointer:
            repo.run(args.user, old_pointer["simulation_id"])
            old = repo.run_path(args.user, old_pointer["simulation_id"])
            for path in old.rglob("*"):
                repo.path(path.relative_to(repo.root))
        final = repo.run_path(args.user, args.simulation)
        if final.exists():
            raise Error("该模拟运行目录已存在，拒绝覆盖")
        alzheimer.validate_catalog(repo, DIMENSIONS)
        repo.configuration()
        recorded = now()
        setup = draft["setup"]
        clock = deepcopy(setup["clock"])
        clock["start_at"] = recorded if clock["mode"] == "real" else clock["start_at"]
        simulated = clock["start_at"]
        state = progression.initialize(setup["progression"], setup["initial_profile"], draft["seed"], simulated)
        run = {"schema_version": 1, "user_id": args.user, "simulation_id": args.simulation,
               "status": "active", "seed": draft["seed"], "initial_profile": setup["initial_profile"], "clock": clock,
               "memory_gate": {"status": "user_confirmed_enabled", "confirmed_at": recorded, "source": "user_self_report"},
               "created_at": recorded, "updated_at": recorded, "recorded_at": recorded,
               "simulation_at": simulated, "progression": state}
        repo.validate_progression(run)
        template = repo.read(".agents", "templates", "session.json")
        persona = repo.read(".agents", "config", "persona.json")
        values = deepcopy(template["dimensions"])
        values["personality"].update(profile_id=persona.get("profile_id"), profile_version=persona.get("version"))
        if set(values) != set(DIMENSIONS):
            raise Error("模板必须含全部 12 维")
        final.parent.mkdir(parents=True, exist_ok=True)
        staging = repo.path(final.parent.relative_to(repo.root), ".staging-" + args.simulation + "-" + uuid.uuid4().hex)
        staging.mkdir()
        activated = False
        renamed = False
        try:
            (staging / "dimensions").mkdir()
            repo.write(staging / "run.json", run)
            repo.write(staging / "background.json", draft["background"])
            repo.write(staging / "memory.json", {"schema_version": 1, "user_id": args.user,
                       "simulation_id": args.simulation, "records": []})
            for dimension in DIMENSIONS:
                envelope = {"schema_version": 1, "user_id": args.user, "simulation_id": args.simulation,
                            "dimension": dimension, "created_at": recorded, "updated_at": recorded,
                            "recorded_at": recorded, "event_at": None, "simulation_at": simulated,
                            "revision": 1, "value": values[dimension],
                            "source": {"kind": "project_template", "locator": ".agents/templates/session.json"}}
                repo.validate_dimension(envelope, args.user, args.simulation, dimension)
                repo.write(staging / "dimensions" / (dimension + ".json"), envelope)
            staging.rename(final)
            renamed = True
            try:
                repo.write(repo.active_path(args.user), {"schema_version": 1, "user_id": args.user,
                           "simulation_id": args.simulation, "created_at": recorded, "updated_at": recorded})
            finally:
                # A directory fsync can fail after the atomic pointer replacement.
                # Never remove a complete run already named by the visible pointer.
                try:
                    activated = repo.pointer(args.user)["simulation_id"] == args.simulation
                except (Error, OSError):
                    activated = True  # Preserve data if activation outcome is uncertain.
            draft.update(status="activated", activated_at=recorded, updated_at=recorded)
            repo.write(repo.draft_path(args.user, args.simulation), draft)
            if old is not None and old.exists():
                shutil.rmtree(old)
        finally:
            if not activated:
                cleanup = final if renamed else staging
                if cleanup.exists():
                    shutil.rmtree(cleanup)
        return {"simulation_id": args.simulation, "status": "active", "memory_gate": run["memory_gate"],
                "setting_verified": False, "dimension_profiles": state["dimension_profiles"],
                "simulation_at": simulated, "previous_active_cleared": old_pointer is not None}


def context(repo, args, run):
    _, persona, dialogue = repo.configuration()
    manifest, profiles = alzheimer.validate_catalog(repo, DIMENSIONS)
    settings = dialogue.get("retrieval", {})
    maximum, default = settings.get("max_limit"), settings.get("default_limit")
    if not integer(maximum, 1) or maximum > cognition.MAX_RETRIEVAL_LIMIT or not integer(default, 1) or default > maximum:
        raise Error("检索数量配置无效")
    limit = default if args.limit is None else args.limit
    if not integer(limit, 1) or limit > maximum:
        raise Error("检索数量超出当前配置范围")
    current = run["progression"]["dimension_profiles"]
    controls = {dimension: deepcopy(profiles[current[dimension]]["controls"][dimension]) for dimension in DIMENSIONS}
    records = repo.memory(args.user, args.simulation)["records"]
    envelopes = {dimension: repo.dimension(args.user, args.simulation, dimension) for dimension in DIMENSIONS}
    background = repo.background(args.user, args.simulation)
    memory_bounded = args.view == "actor" and current["memory"] in alzheimer.BOUNDED_PROFILES
    attention_bounded = args.view == "actor" and current["attention"] in alzheimer.BOUNDED_PROFILES
    windows, bonus = None, 0
    if memory_bounded or attention_bounded:
        effective = deepcopy(controls)
        if not memory_bounded:
            effective["memory"].update(recent_episode_window=None, semantic_window=None, procedural_window=None, cue_bonus=0)
        if not attention_bounded:
            effective["attention"]["context_items"] = limit
        records, limit, windows, bonus = alzheimer.actor_records(records, {"controls": effective}, args.support, limit)
    memories = cognition.retrieve(records, args.query, limit)
    if args.view == "actor":
        visible = {record["id"] for record in memories}
        active = envelopes["memory"]["value"]["active_ids"]
        envelopes["memory"]["value"]["active_ids"] = [item for item in active if item in visible]
    return {"simulation_id": args.simulation, "user_id": args.user, "view": args.view,
            "out_of_character": args.view == "controller", "memory_gate": run["memory_gate"], "setting_verified": False,
            "character": background["character"], "scene": background["scene"], "background": background,
            "persona": persona, "dimensions": {key: value["value"] for key, value in envelopes.items()},
            "dimension_records": envelopes, "dimension_profiles": current, "memories": memories,
            "simulation_at": run["simulation_at"],
            "progression": {key: run["progression"][key] for key in ("dialog_turns", "paused", "onset_at")},
            "affected": {"condition": "alzheimer", "target": "simulated_agent", "definition_version": 1,
                         "calibration": "uncalibrated_engineering_preset", "controls": controls,
                         "dimension_profiles": current, "support": args.support,
                         "definitions": {item["id"]: item["definition"] for item in manifest["dimensions"]},
                         "mechanical_effects": {"memory_window_applied": memory_bounded,
                             "attention_limit_applied": attention_bounded, "effective_memory_windows": windows,
                             "effective_context_limit": limit, "cue_bonus_applied": bonus},
                         "notice": "角色行为由宿主按定义呈现；场景背景是已声明约束。文件视图不能擦除历史对话、状态副本、平台记忆或模型知识。"}}


def validate_all(repo):
    _, persona, _ = repo.configuration()
    alzheimer.validate_catalog(repo, DIMENSIONS)
    repo.schema("session")
    repo.schema("memory-input")
    template = repo.read(".agents", "templates", "session.json")
    if template.get("memory_gate") != {"status": "pending", "confirmed_at": None, "source": None}:
        raise Error("会话模板必须保留待确认记忆门禁")
    template.update(user_id="template", session_id="template", created_at=now(), updated_at=now())
    template["dimensions"]["personality"].update(
        profile_id=persona.get("profile_id"), profile_version=persona.get("version"))
    repo.validate_session(template, "template", "template")
    repo.new_memory("template")
    defaults = repo.read(".agents", "scenario", "defaults.json")
    if not isinstance(defaults, dict) or type(defaults.get("schema_version")) is not int or defaults["schema_version"] != 1:
        raise Error("场景默认配置版本无效")
    visible_defaults = {key: defaults.get(key) for key in ("initial_profile", "progression", "clock", "generation")}
    if normalize_setup(visible_defaults) != normalize_setup({}):
        raise Error("场景默认配置与运行器后备默认值不一致")
    for key in ("input_example", "questionnaire", "character_bank", "runtime"):
        if not isinstance(defaults.get(key), str):
            raise Error("场景默认配置引用路径无效")
        path = repo.path(defaults[key])
        if key in ("questionnaire", "character_bank") and not path.is_file():
            raise Error("场景默认配置引用文件不存在")
    questionnaire = repo.read(".agents", "scenario", "questionnaire.json")
    if (not isinstance(questionnaire, dict) or type(questionnaire.get("schema_version")) is not int
            or questionnaire["schema_version"] != 1 or not isinstance(questionnaire.get("steps"), list)
            or not isinstance(questionnaire.get("dimension_prompts"), dict)
            or set(questionnaire["dimension_prompts"]) != set(DIMENSIONS)):
        raise Error("问卷配置版本、步骤或十二维提示无效")
    education = questionnaire.get("education", {})
    if (not isinstance(education, dict) or education.get("prompt") != "你想了解更多吗？"
            or education.get("optional") is not True or not isinstance(education.get("url"), str)
            or not education["url"].startswith("https://")
            or not isinstance(education.get("local_source"), str)):
        raise Error("可选维度说明入口无效")
    repo.path(education["local_source"])
    counts = {"drafts": 0, "active_runs": 0, "dimensions": 0, "memories": 0}
    users = repo.path("state", "users")
    if users.exists():
        for user_path in users.iterdir():
            repo.path(user_path.relative_to(repo.root))
            if not user_path.is_dir():
                raise Error("用户目录结构无效")
            user = identifier(user_path.name)
            base = repo.base(user)
            if not base.exists():
                continue
            drafts = repo.path(base.relative_to(repo.root), "drafts")
            if drafts.exists():
                for path in drafts.iterdir():
                    repo.path(path.relative_to(repo.root))
                    if path.name.startswith(".") and path.name.endswith(".lock"):
                        continue
                    if path.suffix != ".json" or not path.is_file():
                        raise Error("草稿目录包含未知文件")
                    repo.draft(user, identifier(path.stem))
                    counts["drafts"] += 1
            if repo.active_path(user).exists():
                simulation = repo.pointer(user)["simulation_id"]
                run = repo.run(user, simulation)
                repo.background(user, simulation)
                memory = repo.memory(user, simulation)
                counts["memories"] += len(memory["records"])
                for dimension in DIMENSIONS:
                    repo.dimension(user, simulation, dimension)
                    counts["dimensions"] += 1
                directory = repo.run_path(user, simulation, "dimensions")
                expected = {dimension + ".json" for dimension in DIMENSIONS}
                actual = set()
                for path in directory.iterdir():
                    repo.path(path.relative_to(repo.root))
                    if not path.is_file():
                        raise Error("维度目录结构无效")
                    actual.add(path.name)
                if actual != expected:
                    raise Error("当前模拟须恰好包含 12 个维度文件")
                counts["active_runs"] += 1
    return {"ok": True, **counts}


def execute(args):
    repo = Store(args.root)
    if args.command == "validate":
        return validate_all(repo)
    identifier(args.user)
    if args.command == "prepare":
        data = read_json(Path(args.input))
        setup = normalize_setup(data)
        seed = secrets.randbits(63) if args.seed is None else args.seed
        recorded = now()
        simulation = "sim_" + uuid.uuid4().hex
        background = characters.build_background(data, seed, recorded)
        background.update(user_id=args.user, simulation_id=simulation)
        validate_background(background, args.user, simulation)
        draft = {"schema_version": 1, "user_id": args.user, "simulation_id": simulation, "status": "draft",
                 "seed": seed, "setup": setup, "background": background,
                 "created_at": recorded, "updated_at": recorded, "activated_at": None}
        path = repo.draft_path(args.user, simulation)
        with repo.lock(path):
            if path.exists():
                raise Error("草稿标识冲突，请重试")
            repo.write(path, draft)
        return setup_card(draft)
    identifier(args.simulation)
    if args.command == "show-setup":
        return setup_card(repo.draft(args.user, args.simulation))
    if args.command == "start":
        return start_run(repo, args)
    if args.command == "resume" and not args.user_confirmed_memory:
        raise Error("继续前须重新取得用户开启平台记忆的明确自述")
    with repo.lock(repo.active_path(args.user)):
        run = repo.run(args.user, args.simulation)
        if args.command == "context":
            return context(repo, args, run)
        recorded = now()
        simulated = simulation_time(run)
        run_path = repo.run_path(args.user, args.simulation, "run.json")
        if args.command == "resume":
            run["memory_gate"] = {"status": "user_confirmed_enabled", "confirmed_at": recorded, "source": "user_self_report"}
            run["updated_at"] = recorded
            repo.write(run_path, run)
            return {"simulation_id": args.simulation, "status": "active", "memory_gate": run["memory_gate"], "setting_verified": False}
        if args.command in ("pause", "resume-progression"):
            run["progression"]["paused"] = args.command == "pause"
            run["updated_at"] = recorded
            repo.write(run_path, run)
            return {"simulation_id": args.simulation, "paused": run["progression"]["paused"]}
        if args.command == "turn":
            event = read_json(Path(args.input))
            object_keys(event, ("event_id", "text", "kind", "semantic_matches", "simulation_at"), ("event_id", "text", "kind"))
            identifier(event["event_id"])
            if not isinstance(event["text"], str) or not event["text"].strip() or event["kind"] not in ("dialogue", "control"):
                raise Error("事件文字或种类无效")
            if run["clock"]["mode"] == "manual":
                if "simulation_at" not in event:
                    raise Error("手动时钟的每个事件须显式提供 simulation_at")
                simulated = event["simulation_at"]
                timestamp(simulated)
            elif "simulation_at" in event:
                raise Error("实时时钟事件不能指定 simulation_at")
            state, decision = progression.advance(run["progression"], event, simulated, recorded)
            if state != run["progression"]:
                run.update(progression=state, updated_at=recorded, simulation_at=state["last_simulation_at"])
                repo.validate_progression(run)
                repo.write(run_path, run)
            return {"simulation_id": args.simulation, "decision": decision,
                    "dimension_profiles": state["dimension_profiles"], "dialog_turns": state["dialog_turns"]}
        if args.command == "update-state":
            patch = read_json(Path(args.patch_file))
            if not isinstance(patch, dict):
                raise Error("维度补丁必须是 JSON 对象")
            envelope = repo.dimension(args.user, args.simulation, args.dimension)
            envelope["value"].update(patch)
            envelope.update(updated_at=recorded, recorded_at=recorded, simulation_at=simulated,
                            revision=envelope["revision"] + 1,
                            source={"kind": "explicit_state_update", "locator": "simulation.py:update-state"})
            repo.validate_dimension(envelope, args.user, args.simulation, args.dimension)
            repo.write(repo.run_path(args.user, args.simulation, "dimensions", args.dimension + ".json"), envelope)
            return {"dimension": args.dimension, "revision": envelope["revision"], "updated": True}
        if args.command == "edit-background":
            background = characters.edit_background(repo.background(args.user, args.simulation), read_json(Path(args.input)), recorded)
            validate_background(background, args.user, args.simulation)
            repo.write(repo.run_path(args.user, args.simulation, "background.json"), background)
            return {"simulation_id": args.simulation, "background": background}
        memory = repo.memory(args.user, args.simulation)
        supplied = read_json(Path(args.input)) if args.command in ("remember", "correct") else None
        replacement = validate_memory_input(repo, supplied) if supplied is not None else None
        if args.command == "remember":
            record = {**replacement, "id": "mem_" + uuid.uuid4().hex, "simulation_id": args.simulation,
                      "recorded_at": recorded, "created_at": recorded, "updated_at": recorded,
                      "simulation_at": simulated, "revision": 1}
            memory["records"].append(record)
        else:
            identifier(args.id)
            matches = [i for i, value in enumerate(memory["records"]) if value["id"] == args.id]
            if not matches:
                raise Error("当前模拟的记忆中不存在该 ID")
            index = matches[0]
            old = memory["records"][index]
            if args.command == "forget":
                del memory["records"][index]
            else:
                for field in ("event_at", "event_time_note"):
                    if field not in supplied:
                        replacement[field] = old[field]
                record = {**replacement, "id": old["id"], "simulation_id": args.simulation,
                          "recorded_at": recorded, "created_at": old["created_at"], "updated_at": recorded,
                          "simulation_at": simulated, "revision": old["revision"] + 1}
                memory["records"][index] = record
        repo.validate_memories(memory, args.user, args.simulation)
        repo.write(repo.run_path(args.user, args.simulation, "memory.json"), memory)
        return {"id": args.id, "removed": True} if args.command == "forget" else {"id": record["id"], "revision": record["revision"]}


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    commands = cli.add_subparsers(dest="command", required=True)
    names = ("prepare", "show-setup", "start", "resume", "context", "turn", "pause", "resume-progression",
             "update-state", "remember", "correct", "forget", "edit-background")
    for name in names:
        command = commands.add_parser(name)
        command.add_argument("--user", required=True)
        if name == "prepare":
            command.add_argument("--seed", type=int)
        else:
            command.add_argument("--simulation", required=True)
        if name in ("prepare", "turn", "remember", "correct", "edit-background"):
            command.add_argument("--input", required=True)
        if name == "start":
            command.add_argument("--confirmed", action="store_true")
        if name in ("start", "resume"):
            command.add_argument("--user-confirmed-memory", action="store_true")
        if name == "context":
            command.add_argument("--query", default="")
            command.add_argument("--limit", type=int)
            command.add_argument("--view", choices=("actor", "controller"), default="actor")
            command.add_argument("--support", choices=("none", "cue", "stepwise"), default="none")
        if name == "update-state":
            command.add_argument("--dimension", choices=DIMENSIONS, required=True)
            command.add_argument("--patch-file", required=True)
        if name in ("correct", "forget"):
            command.add_argument("--id", required=True)
    commands.add_parser("validate")
    return cli


def main():
    args = parser().parse_args()
    try:
        print(json.dumps(execute(args), ensure_ascii=False, allow_nan=False))
        return 0
    except (Error, alzheimer.ConfigurationError) as exc:
        print("错误：" + str(exc), file=sys.stderr)
    except OSError:
        print("错误：文件操作失败；请检查路径、权限、锁和磁盘状态", file=sys.stderr)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        print("错误：设置、输入或状态结构无效", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
