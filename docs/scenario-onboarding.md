# 场景问卷与独立模拟

新模拟使用 `scripts/simulation.py`，由仓库里的agents说明宿主如何调用。它不调用模型API，也不是聊天服务器。问卷定义在[questionnaire.json](../.agents/scenario/questionnaire.json)，工程默认值在[defaults.json](../.agents/scenario/defaults.json)。旧 `cognition.py` 保留用于兼容实验；不要在同一次新格式模拟中混用两套状态。

## 开始前怎样问

先问新建还是继续，再问角色是否以认识的人为原型。认识时，可描述病前性格、说话习惯、关系、兴趣、经历和已观察到的变化；不认识时，可描述初遇场景及近期经历。再单独区分“用户认识原型”“角色原本认识对话者”和“角色现在认得对话者”。这些不能互相推断。

叙事问题均可跳过。补充十二维前，问：**“你想了解更多吗？”** 愿意时打开[十二维介绍网页](https://cognitive-twelve-dimensions.robustdegu4.chatgpt.site)；源码在[web/dimensions](../web/dimensions/)。用户可以只补充关心的部分，也可以直接跳过。网页用于阅读说明，不接收或保存角色资料。在线站点目前为私有；无访问权限时可按网页目录README本地预览，也可跳过阅读继续问卷。

跳过的背景使用仓库内的素材库随机生成。每个字段记录 `user_provided`、`generated_fiction` 或 `unknown` 来源；同时记录种子、配方版本、创建/更新时间和修订号。以真实认识的人为原型时，随机补充只能是明确的**虚构替代设定**，不能声称对那个人的真实经历、性格或病情已有了解。用户以后通过 `edit-background` 修改具体字段；未改字段保留原来源，原生成记录仍保留。

随后收集初始预设、进展模式、可变维度、最高预设、时钟和必要参数。叙事可随机生成，但不能替用户假造身份、同意、记忆开关确认或真实临床分期。默认值必须在确认卡中展示，由用户确认后才启动。

## 三种演变规则

| 模式 | 规则 | 必须说明的参数 |
| --- | --- | --- |
| 默认模式 `default` | 新的有效用户对话命中配置词条或有证据的关联后抽取；默认20%机会，变化后接下来3个有效对话轮次冷却；一次最多一个维度升一级 | 触发词、概率、冷却、可变维度、上限 |
| 缓慢发展 `slow` | 开始时只抽取一次首次起点，位于第N天±1天；接下来将变化分散到指定天数中，每个新对话最多执行一个已到期步骤 | N、逐步变化持续天数、可变维度、上限、时钟 |
| 固定状态 `fixed` | 不自动改变预设 | 初始预设 |

默认触发词是“记得、以前、昨天、刚才、回家、回去”，可在确认卡中修改；显式空词条列表表示没有自动命中。普通匹配为本地字面匹配；宿主可提交关联判断，但必须引用本条输入中实际存在的证据并指向已配置的触发ID，记录为推断，不冒充医学判断或语义模型验证。

默认可变维度为记忆、注意、沟通、执行；其余维度仍有完整状态和定义，可由用户明确纳入演变。不会因为随机触发就修改稳定人格文件、真实用户资料、实际工具权限或记忆确认。各维当前预设分别记录；它们是工程控制位置，不是十二种临床分期。

`baseline` 和 `preclinical` 的功能控制相同；进入 `preclinical` 不强制出现可见损伤。初始阶段不从聊天诊断。以上概率、上下限、天数和情境触发都是虚构实验参数，不能据此推断真实阿尔茨海默病的进展。情境引起的短暂表现变化与疾病生物进展也不能混同。

## 准备、确认、开始

从仓库根目录运行；以下 `demo` 和文件均为合成示例。

```bash
python3 scripts/simulation.py prepare --user demo --input examples/onboarding/default.json --seed 42
python3 scripts/simulation.py show-setup --user demo --simulation SIMULATION_ID
```

`prepare` 生成 `sim_<uuid>` 和完整设定卡，不读取旧个人记忆，也不清理旧运行。把卡片中的背景及来源、十二维补充、初始阶段、全部演变参数、时间基准和重置范围交给用户修改或确认。不要只展示一个ID便声称用户已经批准所有内容。

开始模拟前仍应发送：

> 开始前，请先在当前平台设置中开启记忆功能，开启后告诉我。我无法直接检测开关状态；本项目还会使用仓库内的文件记忆。

只有用户确认设定、并明确自述已开启后，才能运行：

```bash
python3 scripts/simulation.py start --user demo --simulation SIMULATION_ID --confirmed --user-confirmed-memory
```

平台记忆确认只记录用户自述；不代表工具检测到了开关。缺少任一确认则拒绝启动。宿主不能读取/持久写入仓库或平台不具备所需功能时，说明完整模拟不可用，仍可继续设置和项目讨论。

同一模拟换一次对话连接时，使用原ID，并取得新的平台记忆自述确认：

```bash
python3 scripts/simulation.py resume --user demo --simulation SIMULATION_ID --user-confirmed-memory
```

继续不清空状态。新的聊天窗口本身也不自动意味着新模拟。

## 每轮怎样调用

先处理停止、纠正、删除或设置要求。它们由可靠控制层执行，不因角色的预设而失效。新的角色对话输入才提交 `turn`；给同一个输入使用稳定的 `event_id`，重试时沿用它。

```json
{"event_id":"message_001","kind":"dialogue","text":"你记得刚才说的公园吗？"}
```

```bash
python3 scripts/simulation.py turn --user demo --simulation SIMULATION_ID --input /tmp/turn.json
python3 scripts/simulation.py context --user demo --simulation SIMULATION_ID --query 公园 --view actor
```

不要把工具调用、查看上下文、模型自己的回复或重试伪装成新的用户对话。`context` 只读，不推进时间表或随机抽取。`control` 事件也不计有效对话轮次。去重、命中证据、抽取结果、变化前后值及时间保存在该run中，能够核查，但不存模型隐藏的逐字推理。

`context --view actor` 返回按当前各维预设组合的约束和演员可见记忆。`--view controller` 用于核对和管理，不能偷偷帮角色回忆。实际给了提示后才使用 `--support cue` / `stepwise`。背景是明示的场景约束；它不证明模型真的忘记了什么。平台记忆、对话历史和状态副本仍可能影响宿主，文件过滤不能擦除模型知识。

暂停演变使用 `pause`，恢复使用 `resume-progression`；不改变当前资料。角色停止对话的要求也必须由宿主实际停止响应，暂停进展命令本身不等于停止整个聊天服务。

## 时间与重置

实际写入时间统一为UTC ISO 8601：`created_at`、`updated_at`、`recorded_at`。`event_at` 是内容所述经历发生的时间，可以未知；`event_time_note` / `time_note` 保存“上周”这类非精确说明。`simulation_at` 是本次运行的故事时钟。未知事件时间不能用编辑时间代填，也不能驱动缓慢发展。记忆的 `valid_until` 表示记录在真实UTC下的有效期，沿用文件检索器规则，不随手动故事时钟提前过期。

现实时间模式以实际启动时间为基准。手动模式必须明确 `clock.start_at`，每条新事件提供不倒退的 `simulation_at`。没有后台定时器；离线期间不反复触发变化。即使多个缓慢步骤已到期，每条新对话也最多执行一个，因此实际完成可以晚于设定结束日。

```text
state/users/USER/simulations/
  drafts/SIMULATION_ID.json
  active.json
  runs/SIMULATION_ID/
    run.json
    background.json
    memory.json
    dimensions/memory.json … experience.json（共12份）
```

十二份源文件的每份封装模拟ID、维度ID、时间戳、修订号、来源和具体状态 `value`。记忆记录同样有模拟ID和实际/事件/模拟时间。

**确认开始新的模拟后**，先构建完整新运行并切换活跃指针，再清理同一用户上一活跃新格式run（含旧十二维、记忆和背景）。不自动归档旧run；新run不继承旧记忆。准备草稿不清理，继续不清理，重复启动同一ID会拒绝。旧版 `memory.json` / `sessions`、别的用户、定义文件、代码、`main`、archive分支和平台记忆不在这次清理范围。文件操作采用锁和逐文件原子替换；不宣称多文件数据库事务或独立身份认证。

## 修改与验证

新格式的 `remember` / `correct` / `forget` 只操作当前模拟的规范记忆；纠正和删除不受角色严重度影响。输入来源支持 `user_statement`、`tool_result`、`generated_fiction`、`user_inferred`，不能把生成或推测改称已证实的事实。删除不自动擦除平台、历史消息或外部副本，应检查已知引用并准确说明范围。

`update-state --dimension DIM --patch-file FILE` 更新封装中的 `value`；补丁仍按原维度schema校验。`edit-background --input FILE` 输入只包含需修改的 `character`、`scene` 或 `dimension_notes` 字段。成功写入后才能声称保存成功。

```bash
python3 scripts/simulation.py validate
python3 scripts/cognition.py validate
python3 -m unittest discover -s tests -v
```

运行数据被Git忽略。网页仅部署公共说明性源码和合成示例，不上传任何真实用户背景、草稿、记忆、凭证或状态文件。
