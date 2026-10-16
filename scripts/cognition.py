#!/usr/bin/env python3
"""Repository-local cognitive state and memory. Python standard library only."""

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid


DIMENSIONS = (
    "memory", "attention", "communication", "executive", "perception",
    "personality", "affect", "motivation", "social", "self", "autonomy", "experience",
)
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
MAX_RETRIEVAL_LIMIT = 50
UTC_DATE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)\Z")
SCHEMA_KEYS = {
    "$schema", "$id", "$defs", "definitions", "$ref", "$comment", "title",
    "description", "default", "examples", "type", "required", "properties",
    "additionalProperties", "enum", "const", "items", "minItems", "maxItems",
    "uniqueItems", "minLength", "maxLength", "minimum", "maximum", "pattern", "format",
}


class Error(Exception):
    """An expected, safe-to-display error (never include a user payload)."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str) or not UTC_DATE.fullmatch(value):
        raise Error("时间必须为 UTC ISO 日期时间（以 Z 或 +00:00 结尾）")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Error("日期时间无效") from None


def identifier(value):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise Error("标识符须为 1–64 个字母、数字、下划线或连字符，首位须为字母或数字")
    return value


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle, object_pairs_hook=unique_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except FileNotFoundError:
        raise Error("所需 JSON 文件不存在") from None
    except (ValueError, UnicodeError):
        raise Error("JSON 文件格式无效；不接受重复键、NaN 或 Infinity") from None


def resolve_ref(root, ref):
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise Error("仅支持当前 schema 内的 JSON Pointer 引用")
    value = root
    try:
        for part in ref[2:].split("/"):
            value = value[part.replace("~1", "/").replace("~0", "~")]
    except (KeyError, TypeError):
        raise Error("schema 引用不存在") from None
    return value


def check_schema(schema, root=None, seen=None):
    """Reject unsupported assertions instead of silently ignoring them."""
    if isinstance(schema, bool):
        return
    if not isinstance(schema, dict):
        raise Error("schema 必须是 JSON 对象或布尔值")
    root = schema if root is None else root
    seen = set() if seen is None else seen
    if id(schema) in seen:
        return
    seen.add(id(schema))
    unknown = set(schema) - SCHEMA_KEYS
    if unknown:
        raise Error("schema 包含不支持的关键字：" + ", ".join(sorted(unknown)))
    if "format" in schema and schema["format"] != "date-time":
        raise Error("仅支持 date-time 格式断言")
    if "$ref" in schema:
        check_schema(resolve_ref(root, schema["$ref"]), root, seen)
    for key in ("$defs", "definitions", "properties"):
        if key in schema:
            if not isinstance(schema[key], dict):
                raise Error("schema 子定义必须是对象")
            for child in schema[key].values():
                check_schema(child, root, seen)
    for key in ("items", "additionalProperties"):
        if key in schema:
            check_schema(schema[key], root, seen)
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    if not isinstance(kinds, list) or any(k not in (
        "null", "boolean", "integer", "number", "string", "array", "object"
    ) for k in kinds):
        raise Error("schema type 无效")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except (re.error, TypeError):
            raise Error("schema pattern 无效") from None


def matches_type(value, kind):
    return {
        "null": value is None,
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool)
                  and (not isinstance(value, float) or math.isfinite(value)),
        "string": isinstance(value, str),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }.get(kind, False)


def validate_value(value, schema, root=None, location="$"):
    root = schema if root is None else root
    if schema is True:
        return
    if schema is False:
        raise Error(f"数据不符合 schema：{location}")
    if "$ref" in schema:
        validate_value(value, resolve_ref(root, schema["$ref"]), root, location)
    kinds = schema.get("type")
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not any(matches_type(value, kind) for kind in kinds):
            raise Error(f"数据类型不符合 schema：{location}")
    # JSON equality must distinguish true from 1, unlike Python equality.
    canonical = lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if "const" in schema and canonical(value) != canonical(schema["const"]):
        raise Error(f"数据常量不符合 schema：{location}")
    if "enum" in schema and canonical(value) not in [canonical(x) for x in schema["enum"]]:
        raise Error(f"数据枚举不符合 schema：{location}")
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            raise Error(f"缺少必需字段：{location}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child = properties.get(key, additional)
            # Do not print arbitrary field names: they can contain user content.
            child_location = f"{location}.{key}" if key in properties else f"{location}.[额外字段]"
            validate_value(item, child, root, child_location)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise Error(f"数组长度不符合 schema：{location}")
        if schema.get("uniqueItems") and len({canonical(x) for x in value}) != len(value):
            raise Error(f"数组包含重复值：{location}")
        for item in value:
            validate_value(item, schema.get("items", True), root, f"{location}[]")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            raise Error(f"字符串长度不符合 schema：{location}")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise Error(f"字符串格式不符合 schema：{location}")
        if schema.get("format") == "date-time":
            timestamp(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if (isinstance(value, float) and not math.isfinite(value)) or value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise Error(f"数值范围不符合 schema：{location}")


class Repository:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise Error("仓库根目录不存在")

    def path(self, *parts):
        path = self.root.joinpath(*parts)
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            raise Error("路径超出仓库范围") from None
        current = self.root
        for part in relative.parts:
            if part in (".", ".."):
                raise Error("不接受相对路径跳转")
            current /= part
            if current.is_symlink():
                raise Error("配置和状态路径不接受符号链接")
        if not path.resolve().is_relative_to(self.root):
            raise Error("路径超出仓库范围")
        return path

    def read(self, *parts):
        return read_json(self.path(*parts))

    def user_paths(self, user, session):
        identifier(user)
        identifier(session)
        return (
            self.path("state", "users", user, "sessions", session + ".json"),
            self.path("state", "users", user, "memory.json"),
        )

    @contextmanager
    def lock(self, path):
        # A stable lock inode avoids the unlink/recreate race between writers.
        try:
            import fcntl
        except ImportError:
            raise Error("本工具的安全并发写入需要支持 fcntl 的系统") from None
        self.path(path.relative_to(self.root))
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_name("." + path.name + ".lock")
        self.path(lock_path.relative_to(self.root))
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Error("状态正在被另一操作更新，请重试") from None
            yield
        finally:
            os.close(fd)

    def write(self, path, value):
        self.path(path.relative_to(self.root))
        data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".tmp-", suffix=".json", dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self.path(path.relative_to(self.root))
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def schema(self, kind):
        schema = self.read(".agents", "schemas", kind + ".schema.json")
        check_schema(schema)
        return schema

    def validate_session(self, session, user, session_id):
        validate_value(session, self.schema("session"))
        if session.get("schema_version") != 1 or session.get("user_id") != user or session.get("session_id") != session_id:
            raise Error("会话所有权或版本不匹配")
        identifier(user)
        identifier(session_id)
        for field in ("created_at", "updated_at"):
            timestamp(session.get(field))
        dimensions = session.get("dimensions")
        if not isinstance(dimensions, dict) or set(dimensions) != set(DIMENSIONS) or any(not isinstance(v, dict) for v in dimensions.values()):
            raise Error("会话必须包含恰好 12 个有效维度")
        gate = session.get("memory_gate", {})
        if gate.get("status") == "pending":
            if gate.get("confirmed_at") is not None or gate.get("source") is not None:
                raise Error("待确认的记忆门禁不能包含确认记录")
        elif gate.get("status") == "user_confirmed_enabled":
            timestamp(gate.get("confirmed_at"))
            if gate.get("source") != "user_self_report":
                raise Error("记忆门禁只能记录用户明确自述")
        else:
            raise Error("记忆门禁状态无效")

    def session(self, user, session_id, confirmed=True):
        path, _ = self.user_paths(user, session_id)
        data = read_json(path)
        self.validate_session(data, user, session_id)
        if confirmed and data["memory_gate"]["status"] != "user_confirmed_enabled":
            raise Error("请先要求用户开启平台记忆并明确确认；工具无法检测或开启该设置")
        return data

    def new_memory(self, user):
        data = self.read(".agents", "templates", "memory.json")
        if not isinstance(data, dict) or data.get("records") != []:
            raise Error("记忆模板必须为空")
        data["user_id"] = user
        self.validate_memory(data, user)
        return data

    def validate_memory(self, data, user):
        validate_value(data, self.schema("memory"))
        if data.get("schema_version") != 1 or data.get("user_id") != user:
            raise Error("记忆所有权或版本不匹配")
        identifier(user)
        records = data.get("records")
        if not isinstance(records, list):
            raise Error("记忆 records 必须是数组")
        ids = set()
        for record in records:
            memory_id = identifier(record.get("id"))
            if memory_id in ids:
                raise Error("记忆包含重复 ID")
            ids.add(memory_id)
            for field in ("created_at", "updated_at"):
                timestamp(record.get(field))
            if record.get("valid_until") is not None:
                timestamp(record["valid_until"])

    def memory(self, user, path):
        if not path.exists():
            return self.new_memory(user)
        data = read_json(path)
        self.validate_memory(data, user)
        return data

    def configuration(self):
        manifest = self.read(".agents", "manifest.json")
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            raise Error("manifest 版本无效")
        dimensions = manifest.get("dimensions")
        if not isinstance(dimensions, list) or len(dimensions) != 12 or {item.get("id") for item in dimensions if isinstance(item, dict)} != set(DIMENSIONS):
            raise Error("manifest 必须声明恰好 12 个维度")
        for item in dimensions:
            module = item.get("module")
            if item.get("state_key") != item["id"] or not isinstance(item.get("label"), str) or not item["label"]:
                raise Error("manifest 维度定义无效")
            if not isinstance(module, str) or not module.startswith(".agents/modules/") or not self.path(module).is_file():
                raise Error("manifest 模块文件不存在或路径无效")
        persona = self.read(".agents", "config", "persona.json")
        dialogue = self.read(".agents", "config", "dialogue.json")
        if not isinstance(persona, dict) or not isinstance(dialogue, dict):
            raise Error("人格和对话配置必须是对象")
        return manifest, persona, dialogue


def memory_input(path):
    value = read_json(Path(path))
    allowed = {"kind", "content", "source", "confidence", "tags", "valid_until"}
    required = {"kind", "content", "source", "confidence"}
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise Error("记忆输入须仅包含规定字段，并提供 kind、content、source、confidence")
    value.setdefault("tags", [])
    value.setdefault("valid_until", None)
    return value


def terms(text):
    result = set()
    for token in re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]+", text.lower()):
        result.add(token)
        if re.fullmatch(r"[\u3400-\u9fff]+", token):
            result.update(token[i:i + 2] for i in range(len(token) - 1))
    return result


def retrieve(records, query, limit):
    instant = datetime.now(timezone.utc)
    active = [r for r in records if r["valid_until"] is None or timestamp(r["valid_until"]) > instant]
    query_terms = terms(query or "")
    ranked = []
    for record in active:
        text = record["content"] + " " + " ".join(record["tags"])
        score = len(query_terms & terms(text))
        score += sum(1 for term in query_terms if len(term) == 1
                     and re.fullmatch(r"[\u3400-\u9fff]", term) and term in text)
        if not query_terms or score:
            ranked.append((score, record["updated_at"], record["id"], record))
    ranked.sort(key=lambda item: (item[0], timestamp(item[1]), item[2]), reverse=True)
    return [item[3] for item in ranked[:limit]]


def execute(args):
    repo = Repository(args.root)
    if args.command == "validate":
        repo.configuration()
        repo.schema("memory-input")
        template = repo.read(".agents", "templates", "session.json")
        if template.get("memory_gate") != {"status": "pending", "confirmed_at": None, "source": None}:
            raise Error("新会话模板的记忆门禁必须未确认")
        instantiated = deepcopy(template)
        instantiated.update(user_id="template", session_id="template", created_at=now(), updated_at=now())
        repo.validate_session(instantiated, "template", "template")
        empty_memory = repo.new_memory("template")
        if empty_memory["records"]:
            raise Error("记忆模板必须为空")
        counts = {"sessions": 0, "memory_files": 0, "records": 0}
        users_path = repo.path("state", "users")
        if users_path.exists():
            for user_path in sorted(users_path.iterdir()):
                repo.path(user_path.relative_to(repo.root))
                if not user_path.is_dir():
                    raise Error("用户状态目录包含未知文件")
                user = identifier(user_path.name)
                memory_path = repo.path(user_path.relative_to(repo.root), "memory.json")
                if memory_path.exists():
                    memory = repo.memory(user, memory_path)
                    counts["memory_files"] += 1
                    counts["records"] += len(memory["records"])
                sessions_path = repo.path(user_path.relative_to(repo.root), "sessions")
                if sessions_path.exists():
                    for path in sorted(sessions_path.iterdir()):
                        repo.path(path.relative_to(repo.root))
                        if path.name.startswith(".") and path.name.endswith(".lock"):
                            continue
                        if path.suffix != ".json" or not path.is_file():
                            raise Error("会话目录包含未知文件")
                        repo.session(user, identifier(path.stem), confirmed=False)
                        counts["sessions"] += 1
        return {"ok": True, "dimensions": len(DIMENSIONS), **counts, "schema_keywords_supported": sorted(SCHEMA_KEYS)}

    session_path, memory_path = repo.user_paths(args.user, args.session)
    if args.command == "init-session":
        template = repo.read(".agents", "templates", "session.json")
        if template.get("memory_gate") != {"status": "pending", "confirmed_at": None, "source": None}:
            raise Error("新会话模板的记忆门禁必须未确认")
        template.update(user_id=args.user, session_id=args.session, created_at=now(), updated_at=now())
        persona = repo.read(".agents", "config", "persona.json")
        if not isinstance(persona, dict):
            raise Error("人格配置必须是对象")
        template["dimensions"]["personality"].update(
            profile_id=persona.get("profile_id"), profile_version=persona.get("version"))
        repo.validate_session(template, args.user, args.session)
        with repo.lock(session_path):
            if session_path.exists():
                raise Error("会话已存在，拒绝覆盖；请使用新的会话 ID")
            repo.write(session_path, template)
        return {"created": True, "user_id": args.user, "session_id": args.session, "memory_gate": template["memory_gate"]}

    if args.command == "confirm-memory":
        if not args.user_confirmed:
            raise Error("只有收到用户明确确认后才能使用 --user-confirmed")
        repo.session(args.user, args.session, confirmed=False)
        with repo.lock(session_path):
            session = repo.session(args.user, args.session, confirmed=False)
            if session["memory_gate"]["status"] == "pending":
                session["memory_gate"] = {"status": "user_confirmed_enabled", "confirmed_at": now(), "source": "user_self_report"}
                session["updated_at"] = now()
                repo.validate_session(session, args.user, args.session)
                repo.write(session_path, session)
        return {"memory_gate": session["memory_gate"], "setting_verified": False}

    session = repo.session(args.user, args.session)
    if args.command == "context":
        manifest, persona, dialogue = repo.configuration()
        settings = dialogue.get("retrieval", {})
        if not isinstance(settings, dict):
            raise Error("检索配置无效")
        maximum = settings.get("max_limit")
        default = settings.get("default_limit")
        if (not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= MAX_RETRIEVAL_LIMIT
                or not isinstance(default, int) or isinstance(default, bool) or not 1 <= default <= maximum):
            raise Error("检索上限配置须为 1–50 的整数，默认数量须在有效上限内")
        limit = default if args.limit is None else args.limit
        if limit < 1 or limit > maximum:
            raise Error(f"limit 必须在 1–{maximum} 之间（由对话配置规定）")
        memory = repo.memory(args.user, memory_path)
        return {"user_id": args.user, "session_id": args.session, "memory_gate": session["memory_gate"],
                "persona": persona, "dialogue_config": dialogue, "dimensions": session["dimensions"],
                "memories": retrieve(memory["records"], args.query, limit), "modules": manifest["dimensions"],
                "retrieval": {"method": "lexical", "query": args.query, "limit": limit}}

    if args.command == "update-state":
        patch = read_json(Path(args.patch_file))
        if not isinstance(patch, dict):
            raise Error("维度补丁必须是 JSON 对象")
        with repo.lock(session_path):
            session = repo.session(args.user, args.session)
            session["dimensions"][args.dimension].update(patch)
            session["updated_at"] = now()
            repo.validate_session(session, args.user, args.session)
            repo.write(session_path, session)
        return {"dimension": args.dimension, "updated": True}

    # The memory gate has already passed. Only the owner-scoped memory file is read.
    replacement = memory_input(args.input) if args.command in ("remember", "correct") else None
    if replacement is not None:
        validate_value(replacement, repo.schema("memory-input"))
    if args.command in ("correct", "forget"):
        identifier(args.id)
    with repo.lock(memory_path):
        memory = repo.memory(args.user, memory_path)
        if args.command == "remember":
            record = {**replacement, "id": "mem_" + uuid.uuid4().hex,
                      "created_at": now(), "updated_at": now(), "revision": 1}
            memory["records"].append(record)
        else:
            matches = [i for i, record in enumerate(memory["records"]) if record["id"] == args.id]
            if not matches:
                raise Error("此用户的记忆中不存在该 ID")
            index = matches[0]
            old = memory["records"][index]
            if args.command == "forget":
                del memory["records"][index]
            elif args.command == "correct":
                record = {**replacement, "id": old["id"], "created_at": old["created_at"],
                          "updated_at": now(), "revision": old["revision"] + 1}
                memory["records"][index] = record
        repo.validate_memory(memory, args.user)
        repo.write(memory_path, memory)
    if args.command == "forget":
        return {"id": args.id, "removed": True}
    return {"id": record["id"], "revision": record["revision"]}


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="仓库根目录")
    commands = cli.add_subparsers(dest="command", required=True)
    for name in ("init-session", "confirm-memory", "context", "update-state", "remember", "correct", "forget"):
        command = commands.add_parser(name)
        command.add_argument("--user", required=True)
        command.add_argument("--session", required=True)
        if name == "confirm-memory":
            command.add_argument("--user-confirmed", action="store_true", help="仅在用户明确确认后使用；不能开启或检测平台设置")
        elif name == "context":
            command.add_argument("--query", default="")
            command.add_argument("--limit", type=int, help="默认及上限由 dialogue.json 的 retrieval 配置规定")
        elif name == "update-state":
            command.add_argument("--dimension", choices=DIMENSIONS, required=True)
            command.add_argument("--patch-file", required=True)
        if name in ("remember", "correct"):
            command.add_argument("--input", required=True)
        if name in ("correct", "forget"):
            command.add_argument("--id", required=True)
    commands.add_parser("validate")
    return cli


def main():
    args = parser().parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Error as exc:
        print("错误：" + str(exc), file=sys.stderr)
    except OSError:
        print("错误：文件访问失败；请检查路径、权限和磁盘状态", file=sys.stderr)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        print("错误：配置或状态结构无效", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
