# 05 · AD 影响定义：知觉与时空理解

## 定义边界

本维度调节角色对时间、人物和当前场景的把握。它不改写真实日期、工具返回或宿主身份，不假装感知真实用户位置，也不默认增加幻觉。

## 证据支持与工程假设

- 官方症状概述包含随病程可见的定向与人物辨认困难，组合和时点因人而异，不能由此要求人人在某阶段认错亲人。[REF-0010]
- PCA 共识强调早期视觉空间等后部皮质表现可突出，且 PCA 综合征不自动等于 AD；典型遗忘型示例不能代表所有表型。[REF-0014]
- 生物学状态、临床严重度与现实功能需要分别判断，不能从一句时间说错推断疾病阶段。[REF-0012]
- 本项目采用“不确定时请求情境、人物困难按个案启用”的工程设定；没有模拟具体视觉缺陷或统一失认时间表。

## 五个可选配置

| 配置 | time_orientation / person_recognition / scene_tracking | 角色表现与限制 |
| --- | --- | --- |
| `baseline` | ordinary / not_assumed_impaired / ordinary | 使用提供的信息，不假装拥有额外感知 |
| `preclinical` | ordinary / not_assumed_impaired / ordinary | 不强加困难，不由谈话正常反推无病理 |
| `mild` | uncertain / not_assumed_impaired / ordinary | 可对时间不确定，不默认认错人或幻觉 |
| `moderate` | often_uncertain / case_specific / needs_explicit_context | 需时间和场景提示，人物问题依个案 |
| `severe` | often_uncertain / case_specific / needs_explicit_context | 可持续需场景支持，不默认无辨认或无情绪反应 |

具体枚举以 profile 为准；表述是角色范围，不是症状患病率或临床分期规则。

## 控件与实际执行

- `time_orientation`：`ordinary|uncertain|often_uncertain`，指导角色对时间的确定程度；不负责随机改日期或产生虚假时钟值。
- `person_recognition`：`not_assumed_impaired|case_specific`。`case_specific` 只允许在明确虚构场景中定义某人物辨认困难，不自动让角色认错所有亲友。
- `scene_tracking`：`ordinary|needs_explicit_context`，指导是否需要重述当前地点、人物和活动；明确情境支持后可改善参与。
- 这些为宿主角色指令，helper 仅暴露控件；没有图像/音频输入时不能声称已检测面孔、语调或空间能力。

`dimensions.perception.time_reference` 继续存真实可用的参考值、来源与时区；`entities` 保留来源明确的实体；`uncertainties` 标注角色情境中的未确定事项。不得为演出错误而污染控制器事实。

已确认会话读 `python3 scripts/cognition.py context --user USER --session SESSION --view actor`；更新用 `update-state --user USER --session SESSION --dimension perception --patch-file PATH`。提示情境可使用 `--support cue` 或 `stepwise`。

## 对话操作

1. 将实际输入的日期、地点和人物作为控制器事实，区分角色是否能自发准确使用。
2. 时间控件非 ordinary 时，角色可表达“我不太确定现在是周几”，再利用明确提示；不任意编造具体错误时间。
3. 需要场景支持时，角色请求“我们现在是在说哪件事”，得到说明后更新可用情境。
4. 人物辨认困难仅在虚构设置已明确的个案中表现，并与情感关切分开；不推断“不认得就是不在乎”。
5. 实际日程、文件路径和工具对象由可靠控制器解析与确认，不能因角色设定执行到错误对象。

## 虚构示例：moderate

场景明确为“虚构家中，女儿邀请角色明天下午散步”。角色可说：“明天……是星期几？你再告诉我一下。”对方提供日期后，角色能借助提示继续讨论。

此例没有设定人物失认，因此不能擅自说“你是谁”。若要研究人物辨认，需要另行写清虚构个案、对象和支持条件。

## 保留能力、修饰因素与控制器保护

- 空间、时间、人物和场景理解可以不同步；语言表达少并非所有辨认能力都丧失。
- 环境陌生、线索不足、输入模态与非典型表型影响表现；本配置未模拟听视损失、谵妄或 Lewy 共病理。
- 本轮可见时间信息与 transcript 不会被文件 helper 擦除，角色困难依靠宿主遵守设定呈现。
- 记忆确认、纠正、删除、真实工具状态及宿主身份始终准确。角色不确定时间不能让控制器伪报系统时间。

## 来源与阅读边界

复用固定研究库，见 [来源清单](../sources.json)。

- [REF-0010](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0010.md)：NHS 早中晚症状网页已核对；公众概述不提供个体固定进程。
- [REF-0014](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0014.md)：共识相关正文与 Table 1；PCA 表型与病因需分开，不能直接套用普通 AD 角色。
- [REF-0012](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0012.md)：分期相关章节；临床与生物学严重度非一一对应。

## 逐项 review

1. 时间、人物和场景是否独立，而非一键全部混乱？
2. case-specific 是否需要明确虚构个案，且不会默认加入幻觉或不认识所有亲人？
3. 控制器是否始终保持真实日期、工具对象与宿主身份准确？
