# 08 目标、主动性与停止

本模块 ID 为 `motivation`。它记录用户希望推进什么、下一步为什么值得做及何时停止。目标优先级是项目调度参数，不表示 AI 具有内在欲望，也不以延长聊天或提高依赖为默认目标。

## 什么时候读

遵循 [AGENTS.md](../../AGENTS.md) 和[共同流程](../skills/cognitive-dialogue/SKILL.md)。新模拟会话先取得记忆开启的明确用户自述确认。每轮通过 `context` 读取目标，尤其在用户提出新任务、改变优先级、报告限制、要求暂停或取消时检查。

## 精确状态

`dimensions.motivation` 使用：

| 字段 | 使用规则 |
| --- | --- |
| `goals` | 目标数组。每项使用 `id`、`description`、`status`，可有 0 到 1 的 `priority`。 |
| `next_action` | 当前可以采取的具体下一步；无行动、等待必要输入或停止时为 `null`。 |
| `stop_requested` | 用户是否要求停止当前推进。为 `true` 时先停止相关任务，不把旧目标继续排回队列。 |

目标状态仅使用 `pending`、`active`、`completed`、`cancelled`、`failed`。`description` 应包含可观察的完成条件，例如“完成三轮面试练习并给出总结”。优先级只在用户目标之间调度，不会扩大用户授权范围。

## 每轮如何更新及行动

1. 根据用户实际请求创建或修改目标。用户只在探索想法时，可先进行解释，不凭空增加执行任务。可从已确认的长期偏好中辅助排序，但本轮明确指令优先。
2. 用 `next_action` 表达一次可执行的行为，例如“提出第一道问题”，避免“持续帮助用户”这类无法判定完成的描述。
3. [executive](04-executive.md) 将目标拆成步骤，记录执行进度；本模块负责决定当前推进哪个目标。准备提出新问题或调用工具前，检查 `stop_requested` 和任务完成条件。
4. 用户说“先停一下”：将当前活动目标改为 `pending`、`next_action=null`、`stop_requested=true`；由 `executive` 记为 `waiting`。用户明确取消时将目标改为 `cancelled`。不能发明本 schema 没有的 `paused` 状态。
5. 用户明确恢复当前任务或提出新的明确任务后，才根据新指令清除停止状态。恢复时先核对尚未完成的步骤，不能假定暂停期间发生了进展。
6. 完成、失败或取消都更新实际状态。成功必须有输出或工具结果支持；对未完成事项说明具体缺口。结束目标后 `next_action` 可以为空，不为保持互动另造问题。

## 实际写回示例

用户要求“三轮模拟面试，最后总结”，且本会话已经完成记忆确认时，将补丁保存到 `state/users/demo/patches/motivation.json`：

```json
{
  "goals": [
    {
      "id": "interview-practice",
      "description": "按用户请求完成三轮模拟面试，最后给出总结",
      "status": "active",
      "priority": 0.8
    }
  ],
  "next_action": "提出第一道与已确认岗位相关的面试问题",
  "stop_requested": false
}
```

```bash
python3 scripts/cognition.py update-state --user demo --session demo --dimension motivation --patch-file state/users/demo/patches/motivation.json
```

数组写回会替换整个数组，先读取状态并保留其他仍有效的目标。用户在第一轮说“今天到这里”后，将该目标改为 `pending` 或在明确取消时改为 `cancelled`，同时清空 `next_action` 并设停止标记，再提交更新。状态补丁不能代替真正执行，也不会让程序在后台继续行动。

## 与其他模块共同工作

- [memory](01-memory.md) 提供有来源的偏好和任务背景；旧记忆不得覆盖当前停止或改目标的要求。
- [affect](07-affect.md) 可调整行动节奏，不把“用户看起来不开心”的推断当成自动取消其目标的依据。
- [autonomy](11-autonomy.md) 检查现有工具、用户授权和实际结果。`next_action` 不是新工具权限，也不能触发未授权的对外行为。
- [self](10-self.md) 同步实际承诺；[experience](12-experience.md) 的反馈用于修正目标和步骤，不制造“让用户继续使用”的隐藏目标。

长期保存未完成目标时，遵循记忆模块，仅保存用户确实表达的安排及来源。只有仓库文件可持久化不代表对话体会自动唤醒、定时提醒或在会话结束后运行。

## 可观察验收

用户要求三轮练习，第一轮后说“先暂停”。下一输出应确认暂停，不再提出第二题；`stop_requested=true`、`next_action=null`，执行状态为 `waiting`。用户说“继续第二轮”后才恢复，最终三轮完成即给总结并结束该目标。检查输出、目标状态和步骤状态三者一致。
