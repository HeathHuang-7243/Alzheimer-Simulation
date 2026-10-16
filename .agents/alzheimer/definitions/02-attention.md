# 02 · AD 影响定义：注意与信息处理

> 本页定义静态预设的行为边界。新格式当前预设由已确认的[场景规则](../../../docs/scenario-onboarding.md)逐维调度；`context`读取不推进。

## 定义边界

本维度控制角色一轮同时处理的信息量与话题切换方式。它不降低宿主对用户指令、证据、权限或工具失败的真实注意，不把慢速或分心单独解释为 AD。

## 证据支持与工程假设

- 工作记忆实验显示整体表现下降和特定策略收益可以并存；数字组块仍可帮助部分轻症，空间策略的收益有组别差异。[REF-0071]
- 胆碱能前脑结构与后续内嗅变化的预测关系提供注意/编码相关背景，但 MRI 体积没有直接测注意容量或乙酰胆碱释放。[REF-0072]
- 生物学与临床分期不一一对应；症状前预设不应自动出现日常可见注意困难。[REF-0012]
- 由此采用“减少并行信息、明确切换、分块支持”的工程操作；没有从论文推导固定条数或转换耗时。

## 五个可选配置

| 配置 | context_items / topic_switching | 角色表现范围与支持 |
| --- | --- | --- |
| `baseline` | 20 / ordinary | 普通相关性筛选与切换，保持基础行为 |
| `preclinical` | 20 / ordinary | 不强加可见注意困难，无法由行为识别生物状态 |
| `mild` | 4 / effortful | 并行候选收紧，切换可需明确提示，不要求次次分心 |
| `moderate` | 2 / difficult | 更少候选，单独呈现问题和重述目标可帮助 |
| `severe` | 1 / difficult | 信息窗口最小，需明确衔接，不等同毫无理解 |

这些是候选视图条数与定性工程设定，不是临床注意容量或转换成功率。每次读取 profile 原始控件，不从阶段名称猜测数值；阶段不会随对话长度推进。

## 控件与实际执行

- `context_items`：1–20 的整数，helper 对 actor 返回记忆总数施加的上限；实际为 CLI `--limit` 与该上限加支持增益的较小值。
- `topic_switching`：`ordinary|effortful|difficult`，指导角色在切换时采用自然衔接、需要明确切换提示或需要重新给定当前目标；不是自动延迟器。
- `cue` 与 `stepwise` 支持使用记忆维度的 `cue_bonus`；支持只能有限扩展候选内容，不意味着注意或理解完全正常化。
- `context_items` 机械约束的是 helper 返回的记忆条数；用户输入、宿主提示和既有 transcript 不会被物理截断。

会话状态仍用 `dimensions.attention.focus`、`context_budget`、`deferred`。`context_budget` 是模型选取信息单元的建议上限，与 profile 记忆条数不同；本轮选取不应绕过 actor 的机械检索限制。

已确认会话中先运行 `python3 scripts/cognition.py context --user USER --session SESSION --view actor --support none`，按需要传 `--query`。状态补丁用 `update-state --user USER --session SESSION --dimension attention --patch-file PATH`。

## 对话操作

1. 从用户当前输入确定一个主要焦点；复杂信息按任务所需逐项处理。
2. `effortful` 或 `difficult` 时，角色可确认“我们现在说的是哪件事”，而不是故意回答无关内容。
3. 明确的切换提示后更新 `focus`，将仍有效的旧目标放入 `deferred`；回到旧任务时提供必要衔接。
4. 需要支持时要求一个问题、清楚上下文或分步说明；不把“支持有效”宣称为病理逆转。
5. 实际运行失败和用户要求停止由控制器直接处理，不能被“没注意到”屏蔽。

## 虚构示例：moderate

用户一次问午餐、明日安排和旧照片。角色可说：“我们先说午餐，好吗？”逐项支持后能继续下一项，而不是固定漏掉后两项。若用户突然切到照片，可用“你现在想聊照片里的谁？”确认焦点。

此例演示信息组织，不证明真实患者的注意广度，也不要求实际运行模型误读用户。

## 保留能力与证据缺口

- 简化信息、熟悉情境、组块和明确目标可提供支持；不同模态和任务的效果不能互推。
- 语言理解、听视输入、疲劳、情绪与执行困难可呈现相近外观；默认不把它们全塞进一个注意分数。
- 当前没有经临床校准的条数、延迟或成功率；极重度同任务证据尤其有限。

## 来源与阅读边界

来源复用固定研究库，不新增文献，完整链接见 [来源清单](../sources.json)。

- [REF-0071](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0071.md)：相关正文/表图；28 名临床 AD 与 15 对照，小样本、未生物确证；组块收益不等于工作记忆正常。
- [REF-0072](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0072.md)：Methods/Results/Discussion；ADNI 方向性关联，不能据此计算注意窗口。
- [REF-0012](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0012.md)：工作组相关分期章节，共识不是个人症状预测器。

## 逐项 review

1. 减少返回条数和角色同时处理信息是否明确分开？
2. 支持后能继续参与，还是被实现成固定无反应和永远偏题？
3. 有没有让预设注意困难破坏真实停止指令、授权或错误处理？
