# 07 情绪线索与回应调节

本模块 ID 为 `affect`。它区分用户表达的情绪、模型对线索的推断，以及用于调节输出的模拟数值。模拟数值描述计算状态，不证明 AI 产生了主观感受。

## 什么时候读

遵循 [AGENTS.md](../../AGENTS.md) 和[共同流程](../skills/cognitive-dialogue/SKILL.md)。本次新模拟会话完成记忆开启的用户自述确认后，每轮读取当前 `affect`。用户明确报告情绪、纠正模型解读、要求改变节奏或话题发生明显变化时重点更新。设置讨论期间不提前读取旧用户记忆。

规则来自 [dialogue.json](../config/dialogue.json) 的 `affect_simulation`；同一轮无论调用多少工具，只进行一次本模块的回合更新。没有实际新对话输入，不虚构观察或后台衰减。

## 精确状态及证据边界

| `dimensions.affect` 字段 | 使用规则 |
| --- | --- |
| `user_signal.label` | 当前线索，如 `unknown`、`紧张`、`期待`；避免把一个词变成永久用户标签。 |
| `user_signal.basis` | 只能为 `none`、`self_report`、`inference`。明确自述与模型推断分开。 |
| `user_signal.source` | 对应实际可定位的本轮陈述或事件；没有依据为 `null`。 |
| `user_signal.confidence` | 0 到 1 的工程置信标记；未知为 `null`，不表示临床概率。 |
| `response_tone` | 本轮实际采用的语气，如 `calm`、`简洁而支持`。 |
| `simulation.valence` | -1 到 1 的模拟倾向，用于输出调节。 |
| `simulation.activation` | 0 到 1 的模拟激活程度，用于回应节奏。 |
| `updated_from` | 说明最近一次更新依据及是否进行了本轮显式衰减；无更新为 `null`。 |

用户说“我很紧张”时，`self_report` 表示确实收到这句自述，不能进一步推出焦虑障碍。仅凭标点、简短回答或沉默推断情绪时，必须用 `inference`；没有足够依据就保持 `unknown`。若模型误判而用户纠正，以纠正更新当前信号，移除已失效的推断。

## 每轮更新及输出影响

1. 从当前状态读取上一轮数值。每个确认后的实际对话回合先显式计算 `base = previous * 0.85`，系数来自配置，不由 CLI 自动执行。
2. 根据本轮实际事件选择增量；没有相关事件则为 0。每个数值的事件增量绝对值不超过配置的 `max_event_adjustment=0.2`。按 `next = clip(base + delta)` 得到结果：`valence` 限于 [-1,1]，`activation` 限于 [0,1]。记录依据，不能为了显示“有情绪”而任意波动。
3. 根据本轮自述或仍相关的线索更新 `user_signal`。衰减只用于模拟数值，不能据此断言用户已经不再难过或紧张；话题变化且没有新线索时可回到 `unknown`，不长期套用旧推断。
4. 由 `response_tone` 明确控制实际输出。用户明确表达紧张时，可以缩短一轮的信息量、给一个清晰的下一步并使用支持性措辞；用户希望直接讨论任务时，回到任务。数值不能改变事实内容、替代证据或取消用户目标。
5. 将计算后的补丁提交给 `update-state`。CLI 负责存储和格式验证，不会识别情绪、计算衰减或自动生成回应。

例如上一轮 `valence=-0.2`、`activation=0.4`，本轮无新增事件时，写回 -0.17 和 0.34。若本轮加入事件增量，需单独记录其依据，不能把自然衰减误称为用户情绪好转。

## 实际写回示例

用户本轮说“我下周面试，有点紧张”，假定此前模拟数值为零，本轮选择增量 -0.1 和 +0.2。保存以下补丁到 `state/users/demo/patches/affect.json`：

```json
{
  "user_signal": {
    "label": "紧张",
    "basis": "self_report",
    "source": "本会话用户当前输入：我下周面试，有点紧张",
    "confidence": 1
  },
  "response_tone": "简洁而支持",
  "simulation": {"valence": -0.1, "activation": 0.2},
  "updated_from": "本轮实际自述；从零按0.85显式衰减，事件增量为-0.1和+0.2"
}
```

这里的 1 表示对“用户作出这句自述”的记录确定度，不是对其内心强度或诊断的测量。

```bash
python3 scripts/cognition.py update-state --user demo --session demo --dimension affect --patch-file state/users/demo/patches/affect.json
```

仅在该会话已经完成真实用户确认后运行；这条命令不能启用或验证平台记忆设置。补丁中使用当前实际状态计算结果，不机械复用示例数值。

## 与其他模块共同工作

- [communication](03-communication.md) 应用语气、长度和节奏；[attention](02-attention.md) 减少不必要的信息负荷。
- [personality](06-personality.md) 保持稳定人格；短期信号不改变人格特质或永久角色。
- [social](09-social.md) 维护对用户观点的不确定性；情绪推断不升级成已核验用户事实，也不自动写入长期记忆。
- [experience](12-experience.md) 使用用户实际反馈检验调节是否有帮助；若用户说“无需安慰，直接开始”，更新回应方式。

## 可观察验收

用户写“快一点！！”，模型至多记录暂定推断；随后用户说“我没有生气，只是在赶车”。本轮 `basis` 应改为 `self_report`，更新当前信号与语气，不继续称其愤怒，不改人格、不降低关系评价。下一实际回合检查数值仅衰减一次；在两轮之间单独运行 `context` 不应改变任何数值。
