# 仓库文件状态

新场景模拟使用 `simulations/active.json` 与 `simulations/runs/<simulation_id>/`，每次包含独立的 `run.json`、`background.json`、`memory.json` 和 `dimensions/` 下十二份带时间戳的源文件。完整结构、重置与继续规则见[新协议](../docs/scenario-onboarding.md)。新建先准备草稿，确认启动后才清理同用户上一活跃新格式run；继续不清空。不跨用户、ID或旧版记忆检索。

以下是保留的旧版兼容结构，新场景模拟不读取它：

真实状态由文件工具写入本仓库目录：

```text
state/users/<user>/
├── memory.json                # 用户范围内的长期记忆
└── sessions/<session>.json    # 当前会话门控与12维状态
```

模板位于 [.agents/templates](../.agents/templates/session.json)。会话初始化使用新模板，不继承上一会话的记忆确认。模型按 [AGENTS.md](../AGENTS.md) 在确认后检索该用户历史。

本feature的新会话还包含 `affected` 阶段选择，默认baseline；旧会话缺少该字段时仍按baseline读取。选择AD预设只改变演员可用视图和行为规则，不直接损坏 `memory.json`。真实纠正与删除仍对规范记录生效，平台记忆门控不受模拟影响。

`state/users/` 默认由Git忽略，避免把实际对话自动推送；数据仍在本仓库的本地目录里，没有外部数据库。版本管理保存规则、配置、模板和合成示例。文件是否跨运行保留取决于宿主的存储方式；临时容器销毁会丢失未另行保存的文件。

用户标识需要由可信宿主或用户提供。目录分用户和路径检查可防止误用，不能替代宿主的身份认证或操作系统文件权限隔离。修改JSON应使用工具的原子写入；不要让多个模型同时手改同一文件。

`forget`移除该用户规范记忆文件中的指定记录，不自动删除会话中已有摘录、备份、Git历史或平台记忆。模型应检查已知副本，按用户要求清理并准确报告范围。
