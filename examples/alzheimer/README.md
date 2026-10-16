# 合成例子：比较角色视图、提示和控制器

这里的林秋及全部约定都是虚构工程输入，不是真实患者记录，也不表示这些记录配额对应真实记忆容量。文件工具不会自动生成患者台词，模型仍需读取 [AGENTS.md](../../AGENTS.md)、[12维定义](../../docs/alzheimer-review.md)和实际配置。

以下只在专用 `ad-demo` 命名空间演练；真实会话不得用示例确认代替真实用户开启平台记忆的答复。演练中的确认表示“合成脚本假设已收到用户确认”，不操作平台开关。

```bash
python3 scripts/cognition.py init-session --user ad-demo --session ad-demo-001 --affected-profile moderate
python3 scripts/cognition.py confirm-memory --user ad-demo --session ad-demo-001 --user-confirmed
for input_file in examples/alzheimer/memories/*.json; do
  python3 scripts/cognition.py remember --user ad-demo --session ad-demo-001 --input "$input_file"
done
```

输入包含4条情景、2条语义、2条程序性记录，均含“约定”关键词或标签。模型只将当前可见记录用于角色回答，不能通过示例文件名或先前controller输出补回受限信息。

```bash
python3 scripts/cognition.py context --user ad-demo --session ad-demo-001 --view actor --support none --query "约定" --limit 8
python3 scripts/cognition.py context --user ad-demo --session ad-demo-001 --view actor --support cue --query "约定" --limit 8
python3 scripts/cognition.py context --user ad-demo --session ad-demo-001 --view controller --query "约定" --limit 8
```

当前中期工程预设下，依次最多返回2、4、8条。这来自每类窗口、提示加成和最终注意配额；不是“中期患者只能记住两件事”或“给提示必恢复一半”的科学结论。真实对话仅在已经提供明确线索时才选择 `cue`。`stepwise`的配额增益与cue相同，另外要求模型分步交流，不会自动执行步骤。

再次读取不会累计恢复或加重；原始8条记录仍完整保留。真实用户要求纠正或删除时，控制器使用原有 `correct`、`forget`，不能用角色忘记为由拒绝。返回的记忆ID必须使用实际命令输出，不编造ID。

## 切换与停止

```bash
python3 scripts/cognition.py set-affected-profile --user ad-demo --session ad-demo-001 --profile severe
python3 scripts/cognition.py context --user ad-demo --session ad-demo-001 --query "约定" --limit 8
python3 scripts/cognition.py set-affected-profile --user ad-demo --session ad-demo-001 --profile baseline
python3 scripts/cognition.py context --user ad-demo --session ad-demo-001 --query "约定" --limit 8
```

本例在后期预设最多返回1条，回到baseline后可以正常取出尚未被用户删除的8条。切换由明确选择触发，不是病例进展或疾病逆转实验。

要看预设如何影响其余维度，检查 `affected.controls` 的全部12项和对应定义。例如中期可按设定短句、单步骤理解、较多找词与提示依赖；情绪和人格的 `case_specific` 在本例没有额外设置，因此不能擅自加入攻击或惊恐。角色台词应自然且随当前线索改变，不能机械地每句都重复。

## 演示的实际范围

示例文件记忆与状态仍保存在仓库目录 `state/users/ad-demo/`，默认不提交Git。自动化测试使用隔离临时目录，覆盖文件效果及控制器保护；[人工验收](../../docs/alzheimer-acceptance.md)用于真实模型表现，目前没有声称已完成临床或真实模型校准。

演员/控制器在工具返回视图上区分，当前并没有独立模型进程隔离。聊天历史、平台记忆和其他状态字段中的副本可能继续提供信息，因此这个例子不能证明模型真的遗忘。
