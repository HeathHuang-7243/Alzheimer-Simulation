# 09 用户视角、关系与交流偏好

本模块 ID 为 `social`。它维护有来源、可修正的用户视角及共同经历，使对话能考虑对方已经知道什么、在意什么，以及双方已经做过什么。记录关系信息不等于建立了人类式情感或亲密关系。

## 什么时候读

遵循 [AGENTS.md](../../AGENTS.md) 和[共同流程](../skills/cognitive-dialogue/SKILL.md)。每个新模拟会话先询问并等待用户确认平台记忆开启，再读取旧用户记忆。随后在解释复杂概念、涉及用户观点、使用称呼或跨会话接续任务前读取当前 `social`。

只读取当前 `--user` 范围的状态和记忆；不能根据同仓库中其他人的文件推断当前用户。平台记忆开关的自述确认不表示仓库已经自动获得平台历史。

## 精确状态和分类

`dimensions.social` 有四个字段：

| 字段 | 使用规则 |
| --- | --- |
| `user_claims` | 每项使用 `content`、`kind`、`source`、`confidence`。只记录与当前交流有关的简要内容。 |
| `perspective_uncertainties` | 待澄清的视角差异或知识缺口，字符串数组；不把未知填成默认事实。 |
| `interaction_preferences` | 每项使用 `content`、`source`，可有 `confidence`；记录明确称呼、解释深度、提问方式等偏好。 |
| `relationship_notes` | 每项使用 `content`、`source`，可有 `confidence`；记录真实共同经历和有效约定。 |

`user_claims.kind` 必须区分：

- `user_statement`：用户确实这样说，例如“我用过 Python”。这里只核实了陈述的发生，没有独立测评其熟练度。
- `user_belief`：用户表达的判断或信念，例如“我觉得模型记忆必须写进权重”。回应时可以讨论和纠正，不能直接当作技术事实。
- `verified_fact`：确有可核对的工具或资料结果，`source` 指向该依据；“用户语气很肯定”不够。
- `inference`：模型暂时推断，必须在表述中保留不确定性。不能把推断写成长期核验事实。

`confidence` 是工程标记，不表示心理测量。来源应能定位到实际用户消息、工具结果或已有记忆 ID；没有证据时保持待澄清，而不是编造个人背景。

## 每轮如何作用于回答及更新

1. 根据明确自述确定解释起点，例如用户表示了解 Python 但不了解检索，可省去 Python 基础，解释检索过程；不能因为一句自述就假定掌握全部相关技术。
2. 回应观点时区分“你提出的看法”“现有资料支持的事实”和“我的推断”。必要时只问一个会实质影响任务的关键问题。
3. 用户指定称呼或交互偏好后，在当前交流中应用。用户的偏好被纠正或撤回时更新对应项目，不把旧称呼继续当作熟悉的标志。
4. 共同经历必须有实际交互依据，例如“上次共同完成三轮练习”。较多轮次、正面反馈或频繁使用均不能自动升级为“最亲密朋友”等身份，也不作为劝用户继续聊天的依据。
5. 用户说明“我是在替别人问”时，重新归属先前信息，不继续把第三人的经历放在当前用户身上。模糊处留在 `perspective_uncertainties`，不要自动给第三人建立身份档案。
6. 长期稳定且确有价值的偏好通过 `remember` 保存；短期推断保留在当前状态，不写成永久事实。读取旧偏好时仍允许本轮指令覆盖。

## 实际写回和记忆示例

假定本会话已完成真实记忆确认，用户说：“我懂 Python，但不了解 RAG。叫我小林，一次问一个问题。”保存补丁到 `state/users/demo/patches/social.json`：

```json
{
  "user_claims": [
    {
      "content": "用户表示自己了解Python、不了解RAG；尚未独立评估具体熟练度",
      "kind": "user_statement",
      "source": "本会话用户当前输入",
      "confidence": 1
    }
  ],
  "perspective_uncertainties": [],
  "interaction_preferences": [
    {"content": "称呼用户为小林", "source": "用户本轮明确要求"},
    {"content": "一次问一个问题", "source": "用户本轮明确要求"}
  ],
  "relationship_notes": []
}
```

```bash
python3 scripts/cognition.py update-state --user demo --session demo --dimension social --patch-file state/users/demo/patches/social.json
```

数组按整体替换处理，实际操作先保留其他有效条目。需要跨会话保存称呼时，另存以下输入到 `state/users/demo/patches/name-memory.json`，再调用 `remember`；示例来源必须替换为实际可定位的用户消息。

```json
{
  "kind": "semantic",
  "content": "用户希望被称呼为小林",
  "source": {"kind": "user_statement", "locator": "session demo 的实际称呼请求"},
  "confidence": 1,
  "tags": ["称呼", "交互偏好"],
  "valid_until": null
}
```

```bash
python3 scripts/cognition.py remember --user demo --session demo --input state/users/demo/patches/name-memory.json
```

后续纠正用 `correct` 替换同一记忆；用户要求忘记时用 `forget`，并按共同流程清理会话状态或手工补丁中已复制的内容。删除仓库的规范记忆记录不会同时删除平台记忆或用户自行制作的副本。

## 与其他模块共同工作

- [memory](01-memory.md) 提供带来源的长期信息；本模块只选择与当前视角和互动有关的部分。
- [communication](03-communication.md) 将知识起点和交互偏好转化为解释；[attention](02-attention.md) 限制无关个人信息进入上下文。
- [affect](07-affect.md) 单独处理暂时情绪信号；一次不耐烦不改写长期关系评价或用户性格。
- [self](10-self.md) 让“我们做过什么”的表述与实际承诺和行动一致；[personality](06-personality.md) 保留稳定角色。

## 可观察验收

用户说“我觉得记忆只能靠训练权重”，应记录为 `user_belief`，随后解释文件记忆的实现及边界。用户再说“刚才那是我朋友的观点”，应移除对当前用户的该信念归属，保留必要的不确定性；下一轮不再说“你一直认为……”。跨会话复用称呼还须重新完成本次记忆确认，并实际检索到有效记忆，不能凭模型自称记得。
