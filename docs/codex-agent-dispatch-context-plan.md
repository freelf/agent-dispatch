# 多 Agent 调度与上下文配置方案

日期：2026-10-28

状态：上下文组织已实现（2026-10-28）。本文中的门禁、合并及恢复机制是目标要求，既有实现问题仍按第 8 节单独处理。

共同规则由 `agent-dispatch` 仓库中的 `common.md` 统一维护。当前仅启用 Claude Code 主脑，编码执行器使用 Pi；保留 Codex 接入能力，待明确需要时再启用。通用规则常驻，专业知识按任务加载，项目约定由项目自己的 `AGENTS.md` 提供。

magpie 继续负责模型路由和额度，也可以继续管理 Skill、MCP 分发；不再使用 magpie 共享指令作为共同规则来源。

## 1. 规则源与文件结构

```text
agent-dispatch/
├── rules/
│   ├── common.md       # 跨角色、跨任务的少量通用规则
│   ├── brain.md        # 主脑职责、授权边界、调度入口
│   └── executor.md     # 编码执行器职责、编码规范、Pi 约束
├── skills/
│   └── dispatch/
│       ├── SKILL.md
│       ├── card-template.md
│       └── advise-template.md
├── routing.tsv
├── bin/
└── install.sh          # 扩充为统一安装、同步入口
```

`common.md`、`brain.md` 和安装脚本同步能力已实现；受管区块外的其他指令保留，修改前自动备份。

| 文件 | 内容 | 边界 |
|---|---|---|
| `rules/common.md` | 区分事实与假设、执行边界、结果说明等真正通用的约束 | 不放 Karpathy、测试优先、小步提交等编码规则，也不放主脑调度流程 |
| `rules/brain.md` | 调研、规划、拆卡、验收、复盘职责；授权边界；编程任务调用 dispatch 的入口 | 不放完整调度手册或完整专业 Skill |
| `rules/executor.md` | 按卡编码、不再派发、修改边界、小步提交、验证纪律、已吸收的 Karpathy 规范、Pi 使用约束 | 不放主脑调度和交付决策规则 |
| 目标项目 `AGENTS.md` | 项目结构、命名约定、构建测试命令、项目边界及详细文档索引 | 保持角色中立，不写“你是主脑”“继续派发任务” |
| 任务卡 | 本次目标、非目标、允许修改范围、设计约束、验收条件、必要参考材料 | 不重复整套全局规则，不复制全部 Skill 或整段主脑对话 |

`common.md` 的判断标准是：这条规则是否同时适用于生成图片、代码规划、代码执行等任务。两个角色都可能用到某项专业知识，不意味着它应当常驻。

## 2. 主脑上下文

Claude Code 使用以下主脑规则源；未来接入 Codex 时可复用：

```text
主脑常驻规则 = common.md + brain.md
```

由安装／同步脚本确定性拼接，写入对应客户端全局规则文件的受管区块，保留文件内其他指令。

| 主脑客户端 | 默认全局规则入口 |
|---|---|
| Claude Code | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` |

以上为默认配置目录。接入使用自定义配置目录的客户端时，安装脚本需要写入其实际加载入口。Codex 的全局覆盖文件也应在接入检查中确认，避免 `AGENTS.override.md` 覆盖共同规则入口。

主脑的完整上下文为：

```text
客户端默认提示
＋ common.md 和 brain.md 的同步结果
＋ 当前项目 AGENTS.md
＋ 当前用户对话
＋ 当前任务需要的 Skill 正文和工具结果
```

主脑负责获取资料、判断方案和拆分任务。任务卡写清已确定的接口、约束和验收标准，具体局部编码由执行器完成。生成图片等非编码任务使用对应 Skill 和工具，不经过 Pi 编码执行器。

主脑规则只在仓库源文件中维护。修改后运行同步，再验证新会话加载结果；不在多个客户端的生成区块中分别修改同一条规则。

## 3. Skill 与 MCP

### 3.1 Skill

少量高频通用 Skill 放全局，其他 Skill 按项目提供。主脑按需读取 Skill 正文；全局可发现的 Skill 简介仍有上下文成本，因此也要控制全局清单。

| 内容 | 加载方式 |
|---|---|
| dispatch | 主脑可发现，处理编程调度任务时读取 |
| 图片 Skill | 生成或编辑图片时读取 |
| Karpathy | 主脑进行代码规划、审查、重构判断时按需读取 |
| 项目专用 Skill | 仅在相关项目提供，按任务读取 |

客户端的本地 Skill 入口：

| 客户端 | 用户级入口 | 项目级入口 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `<项目>/.claude/skills/` |
| Codex | `~/.agents/skills/` | `<项目>/.agents/skills/` |

`dispatch` 的源文件保留在仓库中，通过客户端支持的软链接或安装方式接入。其公共流程共用一份，Claude 与 Codex 的子代理调用方式在手册中分别说明，模板路径相对于 Skill 目录定位。

### 3.2 MCP

MCP 默认按项目配置，由需要它的主脑会话调用；跨项目确实高频使用的服务可以保留用户级配置。

| 客户端 | 项目配置方式 |
|---|---|
| Claude Code | 共享配置使用项目 `.mcp.json`；个人项目限定配置使用 `local` scope |
| Codex | 使用受信任项目的 `.codex/config.toml` |

Claude 的 `local` scope 配置实际保存在 `~/.claude.json` 的对应项目条目中。Codex 用户级 MCP 配置在 `~/.codex/config.toml`。配置文件里存在服务定义之后，还要验证当前会话能够连接并调用。

模型通过 magpie 路由，不会自动把主脑的 Skill 或 MCP 传给 Pi。当前 Pi 执行器默认不接入 MCP：

- 可以预先查清的资料，由主脑提供相关事实、版本、来源和参考文件。
- 必须实时操作 MCP 的任务，交给已经配置相应工具的子代理。

### 3.3 Karpathy 的归属

Karpathy 不进入 `common.md`。

- 主脑：完整 Skill 按任务读取，图片等无关任务不加载其正文。
- 编码执行器：保留已吸收到 `executor.md` 的编码规范，每次派发都注入。

执行器的编码规范由仓库维护，不依赖 magpie 的 Pi Skill 勾选，也不依赖执行器自行触发 Skill。

## 4. 编码执行器上下文

每次派发由脚本直接读取规则源，组装一个独立的执行包：

```text
Pi 默认提示
＋ common.md
＋ executor.md
＋ 项目 AGENTS.md
＋ 本张任务卡
＋ 必要的修复证据和说明
```

`common.md`、`executor.md`、任务卡和修复材料由派发层明确提供；项目 `AGENTS.md` 由 Pi 读取一次，派发层不再重复拼入。common + executor 合计上限 12KB；Advisor 的 common + 顾问角色同样上限 12KB。

运行记录中的 `context.json` 分别记录注入规则、任务材料和项目规则的字节数。项目规则不计入 12KB 自有规则预算，但仍占模型上下文；统计不包含 Pi 默认提示和工具描述，不是模型完整 token 数。

每轮使用新会话和独立临时配置，保留：

```text
--no-skills --no-extensions
--tools read,bash,edit,write
```

执行器不继承主脑整段对话、全局 Skill 清单和个人记忆。需要更多项目细节时，通过任务卡和项目规则提供的入口读取文档、代码及脚本。

由于执行器使用独立临时配置，共同规则必须由派发脚本显式注入，不能指望它读取个人 Pi 配置目录。

文件和网络权限由沙箱限制，编码规范由验证和验收检查。任务卡中的文件修改边界需要单独检查，不能把“整个 worktree 可写”等同于“只能修改卡内允许的文件”。

## 5. Advisor 与修复循环

Advisor 使用独立、只读的上下文：共同规则、顾问角色、项目材料、任务卡、门禁结果、改动情况和三栏请教卡。

请教卡包含机械事实、主脑判断、主脑希望听到的答案。不给 Advisor 整段失败对话；需要具体证据时由其读取代码和指定材料。

执行器失败后，主脑提供相关失败证据和修复说明，再开新一轮执行。轮次限制、连续出现新问题等机械信号触发 Advisor。咨询后的继续、换方案、放弃应有明确的后续操作，避免停止后没有恢复入口。

## 6. 调度与验收流程

```text
用户提出目标
→ 主脑按需使用 Skill 和 MCP 调研
→ 明确方案，拆任务卡和修改边界
→ 创建 worktree，按路由派给 Pi
→ 执行器编码、提交、返回结果
→ 门禁验证
→ 主脑验收、记分
→ 按授权合并
→ 日志与教训回流
```

职责划分：

| 事项 | 负责方 |
|---|---|
| 目标理解、设计取舍、拆卡、并行关系、最终验收 | 主脑 |
| 任务类型和复杂度到路由组的映射 | `routing.tsv` 与调度脚本 |
| 组内模型选择、额度、降级 | magpie |
| 按卡实现、提交、自查、结果报告 | Pi 编码执行器 |
| 构建测试和机械检查 | 门禁脚本 |
| 高价值判断与停手判断 | 主脑、Advisor，以及需要拍板时的用户 |

门禁必须验证实际待合并版本，通过后才更新基线并清理工作区。未执行验证、异常退出或未知状态不能当作通过。项目未声明门禁时，明确标记未验证，并按已定的人工验收路径处理。

## 7. 从 Claude 主脑切换到 Codex 主脑

当前未启用 Codex 主脑。未来明确需要接入时：

1. 将同一份 `common.md + brain.md` 同步到 Codex 的实际全局规则入口。
2. 安装同一份 dispatch Skill，并完成手册中子代理调用方式和路径的客户端适配。
3. 为 Codex 配置当前项目需要的 Skill、MCP，验证实际可用性。
4. 验证派发命令、状态目录写入和内层沙箱在 Codex 运行环境中可执行。
5. 用一张小卡验证派发、执行、验收全过程。

接入完成后，切换主脑只需在同一项目打开新会话，并交接目标、已定方案、卡 ID、worktree 路径、当前结果和下一步。正在进行的卡明确交给一个主脑负责。

两种主脑共用同一套 Pi 执行器、任务卡、门禁、路由和运行记录；客户端之间不自动共享对话历史。

## 8. 安装、同步与验收

日常入口（在 agent-dispatch 仓库执行）：

```sh
./install.sh --client claude        # 默认；规则 + dispatch Skill + 命令
./install.sh --client claude --check # 只检查；缺失／过期返回 1，配置错误返回 2
agent-selftest --check-install      # 离线集成验证，并检查当前 Claude 主脑安装
```

- 主脑底稿更新后重跑安装；新会话使用更新后的规则。执行器和 Advisor 每次派发直接读源文件。
- `--claude-dir`、`--codex-dir`、`--codex-skills-dir` 可指定实际客户端目录；默认识别 `CLAUDE_CONFIG_DIR`、`CODEX_HOME`。`AGENT_BIN_DIR` 保留；旧的 `AGENT_SKILL_DIR` 只用于单客户端安装。
- 标记 `<!-- agent-dispatch:begin -->` 与 `<!-- agent-dispatch:end -->` 之间由脚本生成，其他内容原样保留。生成后的整个全局文件（含保留内容）不得超过 24KB；这是本项目预算，不是客户端模型上下文上限。
- 更新已有文件前保留 `.bak-agent-dispatch-*` 备份；重复执行无变化时不再生成备份。非空 Codex `AGENTS.override.md`、损坏的区块标记、同名非软链接安装目标会报错，不静默覆盖。
- 停用 Magpie 共享指令分发，只清理核实过的旧区块。安装脚本本身不删除其他工具的规则，也不更改模型路由、MCP 或 Skill 的 Magpie 分发选择。
- MCP 默认按项目配置，已有跨项目高频服务可保留；新增服务后检查会话实际可调用。Claude 原生 Memory 可以继续使用，但换主脑时以仓库事实和显式任务交接为准。
- Claude 项目 AGENTS.md 自动加载须核对版本和当前设置，以及祖先目录的 CLAUDE.md / CLAUDE.local.md；必要时通过项目 CLAUDE.md 的 `@AGENTS.md` 引用兼容。在新会话使用 `/memory` 或 `/context` 检查。

验收至少包括：

- Claude 新会话加载共同规则和主脑规则，各出现一次；Codex 等未来接入时再验收。
- 修改 `common.md` 并同步后，新主脑会话与下一次执行器派发都使用新内容。
- 图片任务不加载 Karpathy 正文。
- 每轮 Pi 编码执行都包含共同规则和编码规范，项目规则没有重复注入。
- 执行器没有主脑的调度 Skill 清单或整段历史对话。
- 所需 Skill 能被发现，所需 MCP 能实际调用。
- 未来启用 Codex 时，再验证切换主脑后能完成同一套派发和验收流程。
- 检查使用已知缺失规则或错误配置作为对照，确认确实能够判失败。

此前审查发现的实现问题仍需独立修复：实际合并版本未验证、空门禁命令误放行、未知门禁退出码误判成功、跨卡分支写权限、同名仓库状态混用、日志变化误判新问题，以及 Advisor 后缺少恢复入口。本文不把这些问题视为已解决。

## 9. 方案依据

- [将军赶路不追小兔](../../zj1123581321.github.io/content/posts/260809-multi-agent-scheduling-architecture/index.md)及同目录 [references](../../zj1123581321.github.io/content/posts/260809-multi-agent-scheduling-architecture/references/) 中的 01–07：角色分工、任务卡、路由、项目规则、记分与门禁。
- [Context 与 Loop](../../zj1123581321.github.io/content/posts/261004-context-and-loop/index.md)：上下文分层、主脑和执行器分别构建、Skill 按需加载、项目级工具、干净的 Advisor 上下文以及验证闭环。
- [Claude Code Skill 文档](https://code.claude.com/docs/en/skills)与 [MCP 文档](https://code.claude.com/docs/en/mcp)：客户端 Skill 目录和 MCP 作用域。
- [Codex 指令文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、[Skill 文档](https://learn.chatgpt.com/docs/build-skills)与 [MCP 文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)：全局规则、Skill 和 MCP 的加载入口。

- [Claude Code 指令加载说明](https://code.claude.com/docs/en/memory#agentsmd)：AGENTS.md 的版本、祖先目录与配置前提。
