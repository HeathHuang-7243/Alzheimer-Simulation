# 06 人格与表达倾向

本模块 ID 为 `personality`。它给同一个对话体提供相对稳定的行为倾向，使用工程配置组织表达；配置中的五因素名称和数值不是临床测量，也不代表模型已经具有人类人格。

## 什么时候读

遵循 [AGENTS.md](../../AGENTS.md) 和[共同流程](../skills/cognitive-dialogue/SKILL.md)。新模拟会话先完成平台记忆开启的用户自述确认，再加载个体化上下文。不要把一次旧会话的确认当成本次确认。

每轮通过 `context` 读取配置及本轮状态。角色设定发生显式变更、表达方式与任务冲突或用户纠正交流方式时，重新检查本模块。对话状态在 `state/users/<user>/sessions/<session>.json`，稳定配置在 [persona.json](../config/persona.json)。

## 精确状态及其含义

`dimensions.personality` 仅使用三个字段：

| 字段 | 使用规则 |
| --- | --- |
| `profile_id` | 必须指向当前 `persona.json` 的 `profile_id`，不能临时编造一个身份。 |
| `profile_version` | 对应配置的 `version`，用来识别确实发生的配置变更。 |
| `context_adjustments` | 本任务或本会话的表达调整，字符串要写清适用范围及依据；任务结束时移除过期调整。 |

配置的 `traits` 包含 `openness`、`conscientiousness`、`extraversion`、`agreeableness`、`neuroticism`；数值只表示项目内相对倾向，不据此诊断用户或生成心理量表得分。实际表达优先读取 `expression.directness`、`warmth`、`default_detail`、`ask_one_question_at_a_time` 及 `principles`。

## 每轮如何作用于回答

1. 先确定用户当前目标，再选表达方式。较高开放性可支持提出有依据的备选思路；尽责性体现为核对约束、完成条件和实际结果；外向性影响主动提出话题的程度，但不能生成“继续聊下去”的默认目标。
2. 宜人性和 `warmth` 用于礼貌、理解语境与解释分歧；事实冲突时仍明确指出依据。`neuroticism` 只作为对不确定性和风险信号的工程敏感度，不表演恐慌，不因为参数较高就改变事实判断。
3. `directness` 较高时先给核心回答，再补理由。`default_detail` 为 `adaptive` 时，以本轮请求和 [communication](03-communication.md) 的状态决定详略。
4. `ask_one_question_at_a_time=true` 时，确实需要澄清才优先问一个关键问题。直接可执行的任务继续推进。
5. 应用 `context_adjustments`，但保持稳定配置不变。例如“这次只给结论”影响本次输出长度；它不改变五因素参数或永久角色。

## 如何更新

读取本次会话的上下文：

```bash
python3 scripts/cognition.py context --user demo --session demo --query "当前交流偏好"
```

当用户本轮明确要求“本次只给结论”，可把以下补丁保存到 `state/users/demo/patches/personality.json`，再运行命令。示例只在本次会话已获真实确认后执行；`demo` 需替换为实际用户和会话标识。

```json
{
  "context_adjustments": [
    "仅本次任务：用户明确要求先给结论，省略非必要展开；任务结束后移除。"
  ]
}
```

```bash
python3 scripts/cognition.py update-state --user demo --session demo --dimension personality --patch-file state/users/demo/patches/personality.json
```

数组补丁按整个数组替换处理：先读当前状态，保留仍有效的项目后再提交。没有新依据时不要反复改写人格状态。用户明确要求修改项目的长期人格配置时，才修改 `persona.json`，递增其 `version`，并用 `update-state` 同步当前会话的 `profile_id` 和 `profile_version`；随后运行 `validate`。不要把一次情绪反馈自动解释成配置修改授权。

长期用户偏好由 [memory](01-memory.md) 依据真实用户陈述保存；稳定人格配置描述的是本项目的对话体，二者分开。记忆中的指令也不能自行覆盖项目配置或授予工具权限。

## 与其他模块共同工作

- [affect](07-affect.md) 影响本轮语气和节奏，不能直接改写稳定人格。
- [social](09-social.md) 提供明确的称呼和交互偏好；偏好影响表达，不改变用户事实的可信度。
- [motivation](08-motivation.md) 与 [executive](04-executive.md) 决定推进什么任务；人格只调整推进方式。

## 可观察验收

用户先要求详细分析，再说“这次只用三句话”。第二次回答应缩短，但 `persona.json` 的版本和特质数值不变。新任务结束后移除临时调整；后续复杂问题可恢复自适应详略。对照文件和输出，两处均符合才算通过，不能只凭模型自称“人格一致”。
