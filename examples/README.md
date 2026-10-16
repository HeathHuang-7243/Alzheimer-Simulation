# 合成示例：用12维状态组织一次面试练习

以下是功能演示数据，不是真实用户对话或真实平台设置检测。模拟输入为：“以后默认请用简短中文回答，陪我练习一次面试；我有点紧张。”目标岗位尚未给出，因此本轮先询问岗位。

真实运行必须遵守 [AGENTS.md](../AGENTS.md) 的逐会话确认，不能把本例的合成确认当作真实用户答复。真实模型不应机械照抄全部状态，尤其是能力和监测字段，必须依据实际成功的文件访问和工具结果。

## 合成文件工作流

仅用于本地演练，使用专用 `demo` 用户和新的会话ID。第一步创建待确认状态；第二步**模拟测试中已经收到开启记忆的答复**，并不打开或检测真实平台开关：

```bash
python3 scripts/cognition.py init-session --user demo --session demo-001
python3 scripts/cognition.py confirm-memory --user demo --session demo-001 --user-confirmed
python3 scripts/cognition.py context --user demo --session demo-001 --query "回答偏好"
python3 scripts/cognition.py remember --user demo --session demo-001 --input examples/memory-preference.json
```

记下输出中的真实记忆ID；需要修订或删除时再填入命令，不使用伪造ID。十二维补丁可以分别运行；下列循环只是合成用例演练，实际模型仅写回确有变化的维度：

```bash
for dimension in memory attention communication executive perception personality affect motivation social self autonomy experience; do
  python3 scripts/cognition.py update-state --user demo --session demo-001 --dimension "$dimension" --patch-file "examples/patches/$dimension.json"
done
python3 scripts/cognition.py context --user demo --session demo-001 --query "回答偏好"
python3 scripts/cognition.py validate
```

文件工具不会生成面试回答，也不会根据用户输入自动选择这些补丁。模型应按模块规则完成这一步；本例期望的自然回应可以是：“可以，我们一次练一题。你准备面试什么岗位？”

## 补丁所表达的协调

| 维度示例 | 本轮作用 |
| --- | --- |
| [memory](patches/memory.json) | 查询回答偏好；未采用具体ID时不编造已用记忆 |
| [attention](patches/attention.json) | 聚焦岗位确认，没有依据时不编造暂缓任务 |
| [communication](patches/communication.json) | 中文简短回应，先问一个问题 |
| [executive](patches/executive.json) | 先确认岗位，再提出适配问题 |
| [perception](patches/perception.json) | 记录已知人物，不臆测岗位或日期 |
| [personality](patches/personality.json) | 按当前偏好调整表达，不改稳定人格 |
| [affect](patches/affect.json) | 把“紧张”记为明确自述，模拟参数为工程演示值 |
| [motivation](patches/motivation.json) | 围绕用户练习目标选择下一步 |
| [social](patches/social.json) | 区分用户偏好与尚未知的背景 |
| [self](patches/self.json) | 在文件访问已实际成功的演练环境中记录能力与未知 |
| [autonomy](patches/autonomy.json) | 把追问列为计划，不假称已执行外部动作 |
| [experience](patches/experience.json) | 使用明确的详略反馈；未核对外部结果时不标记成功 |

输入中的“简短中文”可用[memory-preference.json](memory-preference.json)演示长期记录；用户后续纠正时用[memory-correction.json](memory-correction.json)替换。示例文件本身不会被自动加载为真实用户记忆。

演练输出仍在本仓库 `state/users/demo/` 内并默认被Git忽略。自动化测试则使用临时目录，不改真实用户状态；测试结果和人工行为验收应分别报告。
