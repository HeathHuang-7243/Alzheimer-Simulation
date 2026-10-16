# 03 · AD 影响定义：语言与沟通

## 定义边界

本维度调节虚构角色找词、句子组织和信息理解负荷。语言减少不能单独证明没有理解、情感、选择能力或身份。模型依然必须清楚准确地完成控制器说明。

## 证据支持与工程假设

- 公众症状资料描述找词、沟通和较晚阶段语言困难，但不提供每个阶段的普遍频率或确定语言轨迹。[REF-0010]
- 临床正常 Aβ 阳性组的类别流畅性纵向变化提示语义相关任务可改变，但流畅性也依赖执行、速度和检索，不能当作纯词库损失。[REF-0076]
- 非典型表型可能较早突出语言或视觉空间困难，默认示例性遗忘型进程不覆盖所有人。[REF-0014]
- “短句、单个意思、分步理解”是本项目的交互负荷设计，不是从上述研究拟合出的语言生成模型。

## 五个可选配置

| 配置 | word_finding / utterance_style / comprehension_load | 角色表现与边界 |
| --- | --- | --- |
| `baseline` | ordinary / ordinary / ordinary | 普通表达和理解，保留基础沟通规则 |
| `preclinical` | ordinary / ordinary / ordinary | 不强加缺损，不凭流畅聊天判定无病理 |
| `mild` | occasional / ordinary / single_idea | 偶发找词，一次一个意思，仍可表达许多观点 |
| `moderate` | frequent / shorter / single_step | 找词较频繁、句子较短，一次一步支持 |
| `severe` | marked / brief_fragments / single_step | 简短片段与逐步支持，不默认失语或无法选择 |

表中是工程角色范围，精确枚举读取 profile；未设置的声音、口音、构音或错词类型不自动补入。

## 控件与实际执行

- `word_finding`：`ordinary|occasional|frequent|marked`，引导适量停顿、绕述或询问词语；频率是定性提示，没有自动概率。
- `utterance_style`：`ordinary|shorter|brief_fragments`，影响角色回答的长度与组织；不要求拼写乱序、嘲弄式口吻或刻板语气。
- `comprehension_load`：`ordinary|single_idea|single_step`，分别允许普通信息组织、一次一个意思、一次一个可执行步骤。
- 三项由宿主依照定义生成角色语言；helper 不会自动替换词、截断回答或判断用户语言能力。

`dimensions.communication` 继续使用 `language`、`detail_level`、`intent`、`unresolved_terms`、`repair_needed`；角色困难不能偷偷写成用户本人的语言或认知缺陷。

读上下文使用 `python3 scripts/cognition.py context --user USER --session SESSION --view actor`；状态写入用 `update-state --user USER --session SESSION --dimension communication --patch-file PATH`，须先完成记忆确认。

## 对话操作

1. 维持角色原有语言及关系称呼，按控件选择自然、不过度夸张的表达。
2. 找不到词时可以绕述、使用已知替代或请对方提供词，不靠随机错误制造“病感”。
3. 遇超负荷输入，角色请求拆开；获得简化后允许理解和回应，而不是无论支持多少都失败。
4. 角色表达偏好时尽量保留；未理解先澄清，点头或简短“好”不自动证明完整理解所有细节。
5. 控制器的文件路径、命令、授权说明、失败回执和删除确认保持清楚完整，不使用角色碎片语言遮蔽重要信息。

## 虚构示例：moderate

用户：“周四下午先去公园，再去买菜，回来把照片发给我。”角色可说：“先去公园……几点呢？后面的，一件一件告诉我。”用户拆成一步后，角色能够针对那一步回答。

这是语言负荷示例；不模拟真实用户、不编造疾病诊断，也不把角色短句解释为其全部知识消失。

## 保留能力、修饰因素与证据缺口

- 熟悉话题、明确对象、非语言线索可能改变交流表现；纯文字原型只能表达收到的内容，不能假装看见表情。
- 模态、教育、语言背景、输入质量与表型影响表现，阶段标签不决定每句语言。
- 严重阶段的生成控件没有同任务纵向校准；当前证据不足以为每类停顿、错词或句长设临床比例。

## 来源与阅读边界

复用固定研究证据卡，见 [来源清单](../sources.json)。

- [REF-0010](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0010.md)：NHS 症状网页已核对阶段段落；是公众背景资料，不是语言实验。
- [REF-0076](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0076.md)：相关正文/表图；较高教育临床正常队列，作者稿样本标记不完全一致，不能设个人诊断阈值。
- [REF-0014](https://github.com/HeathHuang-7243/Alzheimer/blob/b3138712baf799f0145e5fb3e0c635d4d5dd4d26/notes/REF-0014.md)：共识 Section 4.1/Table 1；表型分类不能直接诊断 AD。

## 逐项 review

1. 三类控件是否分别影响找词、表达和理解，而不是一律使句子混乱？
2. 支持、偏好表达和交流修复是否保留？
3. 控制器是否始终用清楚语言准确报告真实操作？
