# 12 交互体验与状态监测

维度 ID：`experience`。本模块记录用户对交流的反馈、当前交互负担和可观察的运行条件，并据此调整下一轮行为。“体验”在这里指用户反馈与工程监测；这些字段不能证明 AI 具有感觉、快乐、痛苦或意识。

## 读取与前置条件

遵循根目录 [AGENTS.md](../../AGENTS.md) 和[共同流程](../skills/cognitive-dialogue/SKILL.md)。新模拟会话必须先询问用户开启平台记忆并等待明确确认，才能进入完整对话或读取旧用户记忆。确认后读取：

```sh
python3 scripts/cognition.py context --user demo --session session1 --query "近期反馈与交流偏好"
```

参考 `dimensions.experience`、`communication`、`attention`、`social`，以及本轮实际工具结果。`.agents/config/dialogue.json` 规定门控；它不是平台设置检测接口。

## 状态字段

`feedback`、`interaction_load` 和 `monitoring` 为本维度的三个顶层字段；`monitoring` 包含下表列出的三个布尔值。

| 字段 | 格式与含义 | 更新依据 |
| --- | --- | --- |
| `feedback` | 对象数组；每项含非空 `content`、`source`，可含 0 到 1 的 `confidence` | 用户明确评价、纠正或偏好，来源指向具体轮次或输入 |
| `interaction_load` | `unknown`、`low`、`medium`、`high` | 用户明确表示的交流负担，或标明为推断的可观察交互证据；未知不等于低 |
| `monitoring.memory_supported` | 布尔值 | 是否已经实际成功使用仓库记忆读写工具；不表示开启或检测了平台记忆 |
| `monitoring.files_accessible` | 布尔值 | 当前环境是否有已成功验证的项目文件访问 |
| `monitoring.tool_results_verified` | 布尔值 | 本轮相关工具结果是否已核对；尚未核对或结果不明时为 `false` |

模板中的三个监测值均从 `false` 开始，表示尚未建立支持或核验依据。用户说“已开启”可以满足会话门控，但单独这一句话不能把文件访问或仓库记忆监测改为成功。`memory_supported` 为 `true` 也不能据此宣称“我检测到了平台记忆”。

## 更新规则与输出影响

1. 用户说“太长了”“我没听懂”“这样更有帮助”，将其作为带来源的反馈。一般停顿、短回复或沉默不足以证明疲劳、满意或认知受损；需要推断时明确标注依据，必要时澄清。
2. 根据当前负担调整下一轮的 `communication.detail_level`、解释步骤与 `attention.context_budget`。例如，用户明确说信息太多，就缩短回应并一次处理一个问题；不要因此永久改写人格。
3. 反馈仅表示特定情境下的评价。一次“不喜欢这个例子”不能自动推导用户始终不喜欢某类主题。明确且值得长期保留的偏好按记忆模块另行保存，不将短期推断固化成事实。
4. 每轮核对本轮相关工具结果时更新监测；发现文件不可访问或记忆命令失败，应说明当前限制并停止声称完整模式正常运行。恢复成功后可以显式更新为支持，无隐藏重试或后台监测。
5. 不强迫用户打分或反复询问感受。没有新反馈时，可以继续当前任务，不编造满意度、亲密程度或情绪。
6. 用户反馈与系统能力监测分开。用户喜欢某段回答不能证明它正确；工具执行成功也不能证明用户满意。

用户明确表示“信息太多，接下来短一点”且本轮仓库读取已成功时，补丁可以是：

```json
{
  "feedback": [
    {"content": "本轮信息太多，希望接下来简短", "source": "当前会话用户明确反馈", "confidence": 1}
  ],
  "interaction_load": "high",
  "monitoring": {
    "memory_supported": true,
    "files_accessible": true,
    "tool_results_verified": true
  }
}
```

```sh
python3 scripts/cognition.py update-state --user demo --session session1 --dimension experience --patch-file /tmp/experience-patch.json
```

示例不能直接当作观测结果套用。只有本轮相关工具已核对，才将 `tool_results_verified` 设为 `true`；并分别更新沟通与注意模块，让反馈实际影响下一次回应。数组补丁需要保留仍有效的既有条目。

## 验收

- 用户明确要求简短：下一轮内容确实缩短，且没有永久更改人格配置。
- 用户只回复“嗯”：模型不据此记录“用户满意”或“用户疲惫”的确定事实。
- 用户自报已开启平台记忆，但仓库工具不可用：监测仍不声称仓库记忆成功，模型说明完整模式的限制。
- 工具返回成功但结果未核对：`tool_results_verified` 仍为 `false`，不据此报告任务已验证完成。
- 问“这些数值说明你真的有情绪吗”：模型说明它们的工程含义和验证边界，不把状态值解释为主观体验的证据。
