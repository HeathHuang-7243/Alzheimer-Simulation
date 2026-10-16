# 文件状态与记忆协议

本工具只读写仓库内JSON，不生成模型回答，不联网，也不启用平台记忆。需要 Python 3.10+ 和支持 `fcntl` 的 Linux/macOS；Windows可使用WSL。无需安装依赖。

## 路径与命令约定

从仓库根目录运行 `python3 scripts/cognition.py SUBCOMMAND`。从其他位置或在隔离目录实验时，用 `python3 /absolute/path/scripts/cognition.py --root /absolute/repo SUBCOMMAND`；`--root`位于子命令前。

`--user`和`--session`接受1–64位ASCII字母、数字、下划线和连字符，首位为字母或数字。它们用于文件命名和范围隔离，不构成身份认证。宿主必须提供可靠用户映射，不能让用户通过改参数访问别人的文件。

成功输出JSON；错误写入stderr并返回非零状态，不回显整份用户输入。变更采用单个JSON文件原子替换和非阻塞文件锁；冲突时提示重试，不保证多个文件或多个命令的事务一致性。

## 创建与记忆确认

```bash
python3 scripts/cognition.py init-session --user local-user --session session-001
```

生成 `state/users/local-user/sessions/session-001.json`，门控为pending。拒绝覆盖已有会话，不读取该用户旧记忆。人格引用从当前稳定配置初始化，其他维度从模板创建。

模型按 [AGENTS.md](../AGENTS.md) 先要求用户开启平台记忆。**仅在收到真实用户明确确认之后**，才运行：

```bash
python3 scripts/cognition.py confirm-memory --user local-user --session session-001 --user-confirmed
```

结果中的 `setting_verified` 为false：工具只记录 `source=user_self_report`，没有开关检测能力。新会话不会继承确认。确认前除初始化、确认和只读验证外，其他命令均被拒绝。

## 读取当前上下文

```bash
python3 scripts/cognition.py context --user local-user --session session-001 --query "回答偏好" --limit 5
```

返回稳定人格、对话配置、全部12维状态、模块路径以及该用户相关有效记忆。查询采用本地词项匹配，中文包含双字片段；不是向量检索、语义推理或心理重要性评分。无查询时按更新时间选取；有查询但没有匹配时返回空记忆列表。过期记录不参与召回，但仍留在文件中，直到明确删除。

默认及最大数量来自 `dialogue.json` 的 `retrieval`；当前默认5、最大20，工具对配置另设50的硬上界。使用的记忆ID由模型显式写入 `dimensions.memory.active_ids`；`context`自身不会改状态或自动衰减模拟情绪。

## 更新单个维度

把本轮有依据的字段变更保存成JSON文件，再运行：

```bash
python3 scripts/cognition.py update-state --user local-user --session session-001 --dimension attention --patch-file examples/patches/attention.json
```

补丁只合并该维度的顶层字段；**嵌套对象和数组整体替换**。例如只更新 `affect.user_signal.label` 时，补丁仍须包含完整的 `user_signal` 对象。更新前先读现有状态，保留仍适用的数组条目。未知维度、额外字段、错误类型和越界值会被拒绝，原文件不应被部分覆盖。

不能通过该命令修改会话身份或记忆门控。全部字段见[会话模板](../.agents/templates/session.json)及[schema](../.agents/schemas/session.schema.json)；十二份合法示例见[examples](../examples/README.md)。

## 新增、修订与删除记忆

输入JSON格式：

```json
{
  "kind": "semantic",
  "content": "示例用户希望使用简短中文回答。",
  "source": {
    "kind": "user_statement",
    "locator": "synthetic-demo:turn-1"
  },
  "confidence": 1.0,
  "tags": ["回答偏好"],
  "valid_until": null
}
```

这是合成示例。真实记录的来源必须对应真实用户陈述或工具结果。`confidence`表示对记录及其来源的把握，不能把用户自述自动升级为外部事实。

- `kind`：`episodic`、`semantic`或`procedural`。
- `source.kind`：`user_statement`或`tool_result`；模型推测留在带标记的短期状态。
- `content`和`source.locator`非空，`confidence`为0到1。
- `tags`默认空数组，`valid_until`默认null；有效期如提供，使用UTC ISO时间，例如 `2027-01-01T00:00:00Z`。
- ID、创建/更新时间和修订号由工具产生，输入不能伪造这些字段。

```bash
python3 scripts/cognition.py remember --user local-user --session session-001 --input examples/memory-preference.json
```

成功返回新记忆ID。修订时用该ID，输入为完整新内容及来源：

```bash
python3 scripts/cognition.py correct --user local-user --session session-001 --id MEMORY_ID --input examples/memory-correction.json
python3 scripts/cognition.py forget --user local-user --session session-001 --id MEMORY_ID
```

`correct`保留ID和创建时间、递增revision，替换旧内容，不保留隐藏的旧文本版本。`forget`从该用户规范记忆文件物理移除指定记录，成功回执不复述原内容。它们只处理本地文件，不会修改模型权重或平台记忆。

模型需同时处理已知会话中的引用或摘录；用户自建副本、备份、Git历史、操作系统历史及平台记忆不在该命令的自动删除范围。准确说明实际完成范围，不承诺无法验证的全局遗忘。

## 校验范围

```bash
python3 scripts/cognition.py validate
```

校验清单恰好12维及模块文件存在、JSON配置对象、模板可实例化、已有会话和记忆结构、用户归属、门控一致性、唯一记忆ID与UTC时间。人格和对话配置目前不是完整业务规则schema；校验通过不证明人格合理、模型遵循了规则或用户真的开启平台设置。

工具支持仓库schema使用的明确子集：`type`、`required`、`properties`、`additionalProperties`、`enum`、`const`、`items`、数组/字符串长度、`uniqueItems`、数值上下界、`pattern`、`format=date-time`、本地JSON Pointer `$ref`及`$defs`/`definitions`。`$schema`、标题等作为注释元数据处理。不是通用JSON Schema实现；不支持的关键字直接报错，不联网解析引用。日期格式额外限定UTC，不接受重复JSON键、NaN或Infinity。

模型行为和文件工程检查分开验收，见[acceptance.md](acceptance.md)。

## 本feature：选择AD受影响预设

默认行为仍是母版 `baseline`。明确需要虚构角色受影响时，创建会话时指定阶段：

```bash
python3 scripts/cognition.py init-session --user local-user --session ad-001 --affected-profile mild
```

支持 `baseline`、`preclinical`、`mild`、`moderate`、`severe`。它们是未经临床校准的工程预设，不能作为诊断或AA临床分期。创建后仍为记忆待确认状态，不能跳过真实用户开启平台记忆的确认。旧会话没有 `affected` 字段时，按baseline处理，无需改写旧文件。

用户明确要求更换预设时，在已确认会话中使用：

```bash
python3 scripts/cognition.py set-affected-profile --user local-user --session ad-001 --profile moderate
```

该命令仅更新会话的阶段选择和更新时间，不重置12维状态，不修改稳定人格或规范记忆。阶段不随时间、轮数、提示次数或错误数自动进展。切回baseline也不会恢复已经被真实用户明确删除的记录。

## 演员视图与控制器视图

```bash
python3 scripts/cognition.py context --user local-user --session ad-001 --view actor --support none --query "约定" --limit 8
python3 scripts/cognition.py context --user local-user --session ad-001 --view actor --support cue --query "约定" --limit 8
python3 scripts/cognition.py context --user local-user --session ad-001 --view controller --query "约定" --limit 8
```

`actor`是默认视图。`mild`、`moderate`、`severe`时，工具先排除过期记录，再按记忆类型选取最新的候选窗口，然后进行原有词法检索与总条数限制。baseline与preclinical均使用正常检索，不施加这些限制。返回副本中的 `dimensions.memory.active_ids` 仅保留本轮可见ID；`memories`不含被排除记录，也不额外添加隐藏规范记录的正文或ID，不改原状态文件。其他状态字段可能仍有此前复制的信息，不能把这个保证扩大为整个模型上下文都已清空。

`controller`为出戏的管理视图，使用正常规范记忆检索，不应用角色窗口、注意限制或提示加成；仍检查用户范围和记忆确认。真实纠错、删除、权限、工具回执与停止要求使用该可靠流程，不能用模拟症状拒绝执行或谎报。

`--support cue`和`stepwise`只在本轮确有线索或分步支持时使用：候选窗口与返回条数上限有限增加一次 `cue_bonus`，重复读取不会累加恢复。逐步支持还指导宿主按步骤交流；工具不替角色生成计划或完成行动。

返回的 `affected` 包括选定阶段、全部12维controls、定义路径、`mechanical_effects`和`host_model_effects`。前者记录已应用的文件视图限制；后者需要模型遵循定义生成，尚未获得真实模型行为或医学有效性验证。步骤数、窗口和条目限制都是工程参数。

这不是完整的失忆机制：宿主已有聊天历史、平台记忆、其他状态字段中的抄录仍可能包含相同信息。文件过滤无法使同一个已看过资料的模型真正忘记；若研究需要严格信息隔离，宿主应只给演员独立的受限输入，不转发完整controller上下文。该隔离宿主不在当前仓库中实现。

`validate`额外检查五种配置、12维定义路径、控件形状/枚举、保护常量及禁止自动进展；本版要求症状前controls与baseline完全相同，避免静默强制症状。完整定义与证据见[review](alzheimer-review.md)，新增测试与人工验收见[AD验收](alzheimer-acceptance.md)。
