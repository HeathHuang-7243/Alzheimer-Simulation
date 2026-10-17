# Alzheimer-Simulation

> **专有项目 · All rights reserved**
>
> Copyright © 2026 Heath Huang（GitHub：HeathHuang-7243）。[许可与版权条款](LICENSE)。
>
> 公开可见不等于开源授权。除适用法律、平台条款或既有有效授权允许的范围外，使用、运行、复制、修改、分发或商业利用本项目须取得事先书面许可。以下运行说明面向已获授权的使用者。第三方材料与不可受版权保护的内容不据此归本项目所有。

一个由 `AGENTS.md` 指导模型使用的文件式对话认知原型，覆盖记忆、注意、沟通、执行、知觉、人格、情绪、动机、社会认知、自我认知、自主性及交互体验12个维度。

规则、配置、模板及实际运行状态都放在本仓库目录内，使用 Markdown 和 JSON；不使用数据库、向量服务或外部记忆后端。模型负责理解和对话，文件工具负责校验与保存。当前没有独立聊天界面或自动调用大模型的服务。

## 开始使用

1. 在具备文件读写工具的模型/agent宿主中打开本仓库，明确让模型读取根目录 [AGENTS.md](AGENTS.md)。不同宿主的自动发现规则不同；仅创建 `.agents/` 不保证自动加载。
2. 要开始模拟对话时，模型会先请用户在当前平台开启记忆功能，并等待确认；它无法直接检测或修改平台开关。
3. 确认后，模型按[完整工作流](.agents/skills/cognitive-dialogue/SKILL.md)读取状态、检索记忆、协调各维、对话并写回。新会话重新确认；同一会话不每轮重复询问。

平台记忆与仓库文件记忆分别运行。开启平台记忆不会自动读取、上传或同步仓库；没有平台记忆功能或文件读写能力的宿主，不能声称已启动本项目完整模式。

## 文件入口

| 内容 | 位置 |
| --- | --- |
| 模型总入口 | [AGENTS.md](AGENTS.md) |
| 12维清单 | [manifest.json](.agents/manifest.json) |
| 稳定人格与对话配置 | [persona.json](.agents/config/persona.json) · [dialogue.json](.agents/config/dialogue.json) |
| 每轮流程 | [cognitive-dialogue](.agents/skills/cognitive-dialogue/SKILL.md) |
| 状态与记忆模板 | [session.json](.agents/templates/session.json) · [memory.json](.agents/templates/memory.json) |
| 架构与模块联系 | [architecture.md](docs/architecture.md) |
| 文件工具命令 | [protocol.md](docs/protocol.md) |
| 可运行示例 | [examples](examples/README.md) |
| 行为与工程验收 | [acceptance.md](docs/acceptance.md) |
| 实际数据位置 | [state](state/README.md) |

## 本地检查

需要 Python 3.10+ 和支持文件锁的 Linux/macOS（Windows可用WSL），只用标准库，无需安装依赖或设置API密钥：

```bash
python3 scripts/cognition.py validate
python3 -m unittest discover -s tests -v
```

校验与测试不等于已开启真实用户的记忆设置。自动化测试使用临时目录和合成输入；模型行为还需按验收场景在实际宿主中检查。

## 设计边界

这些模块是基于认知研究提出的工程类比，不是经过临床验证的阿尔茨海默病模拟器。默认不模拟疾病、记忆退化或人格损伤，也不据状态变量宣称AI具有情绪体验或意识。相关理论资料见 [Alzheimer研究仓库](https://github.com/HeathHuang-7243/Alzheimer)。

动态数据仍保存在本仓库的 `state/users/` 下，默认不自动提交真实对话到Git。实际文件持久性由宿主环境决定；模型没有成功读写时，应明确说明，而不能声称已经记住。
