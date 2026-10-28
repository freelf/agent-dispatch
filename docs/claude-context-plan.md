# 主脑与执行器的上下文组织（定稿）

2026-10-28 定稿，尚未落地。回"改"后按第 8 节执行。

依据（博客仓库）：
- 261004：`content/posts/261004-context-and-loop/index.md`，第二节"静态 Context"（63–187 行）。
- 260809：`content/posts/260809-multi-agent-scheduling-architecture/index.md` 及 `references/01–07`。

## 一句话

规则只有一份底稿，放在 `agent-dispatch/rules/`，进 git，按角色拼接：主脑拿「共用 + 主脑专属」，执行器拿「共用 + 执行器段 + 任务卡」。skill 和 MCP 只配给主脑，执行器一样都不带（261004:129–139）。

## 1. 底稿：三个文件

| 文件 | 内容 | 谁带 | 大小 |
|---|---|---|---|
| `rules/common.md` | 共用底座：中文回复、不用 emoji、不截断重要输出；提交格式、提交前看 diff、不 force-push | 主脑 + 执行器 | 约 0.3KB |
| `rules/brain.md` | 主脑专属：角色声明、改代码走 dispatch skill、自己改代码前先加载 karpathy-guidelines | 主脑 | 约 0.4KB |
| `rules/executor.md` | 执行器段：角色声明、8 条执行规则、写代码规范（karpathy 全文） | 执行器 | 约 3.7KB |

主脑每个会话常驻的规则不到 1KB，写代码规范不在里面。

`rules/common.md`（内容取自 magpie 里生成的那段，改由本仓库维护）：

```markdown
# Global Configuration

## 1. Defaults

- Reply in **Chinese** unless I explicitly ask for English.
- No emojis.
- Do not truncate important outputs (logs, diffs, stack traces, critical reasoning).

## 2. Git
- Commit format: `<type>(<scope>): <description>`
- `git diff` before commit to confirm scope; never force-push to main/master
```

`rules/brain.md`（现在 `~/.claude/CLAUDE.md` 的内容，加最后一句）：

```markdown
# 主脑

你是主脑：只做调研、规划、拆任务卡、验收、合并、复盘，不直接写代码（单行机械小改、或用户明确要求你直接改的除外）。
要改代码的需求，用 dispatch skill 判断派不派、怎么拆，再派发。
自己动手改代码前（单行机械小改除外），先加载 karpathy-guidelines skill。
```

`rules/executor.md`：只改第 2 条，删掉和 common 重复的提交格式。
- 现在："提交信息按项目规则的约定，没有约定就用 `<type>(<scope>): <description>`。"
- 改为："提交信息按项目规则的约定，没有约定就按上面共用规则里的格式。"

## 2. 主脑（Claude Code）开场时读到的

1. Claude Code 自带的系统提示，不动。
2. `~/.claude/CLAUDE.md` = common + brain，由 `install.sh` 生成，超过 24KB 拒绝生成。
3. 项目根目录的 `AGENTS.md`。项目里不放 CLAUDE.md：Claude Code 在没有 CLAUDE.md 时直接读 AGENTS.md（261004:141）；Pi 在同一目录先取 AGENTS.md，两者并存时执行器读不到 CLAUDE.md 里的内容。
4. Skill：常驻的只有简介，用到才读全文。
   - 全局 `dispatch`：派活时加载，主脑专属的流程细节（分级、写卡、验收、合并、复盘）都在这里。
   - 全局 `karpathy-guidelines`：主脑自己动手改代码时加载。
   - 项目 `.claude/skills/` 里的：只有这个项目用的。
5. MCP：只有当前项目开了的，见第 4 节。
6. Memory：Claude Code 自带的。只有一个主脑客户端，够用（261004:155–163）。

## 3. 执行器（Pi）派活时读到的

1. Pi 自带的精简系统提示。
2. 项目根目录的 `AGENTS.md`：Pi 自己读，只读一次。不拼进 prompt，避免重复注入，也不占 12KB。
3. 任务消息 = common + executor + 任务卡；修复轮再加上一轮的门禁输出和修复说明。common + executor 超过 12KB 拒绝派发。
4. 不带 skill（`--no-skills`）、MCP（sandbox 禁外网，Pi 0.73 也没有 MCP）、Memory。临时配置目录里没有全局 AGENTS.md，magpie Library 的勾选影响不到执行器。
5. 卡里要用到的资料（比如某个 API 的用法）由主脑用 skill 或 MCP 查好写进卡。文章没有直接写这一句，是本方案的做法。要用主脑会话里专属工具或上下文的活不进执行器，走子代理路径（260809:157，dispatch SKILL 第 1 节）。

## 4. 以后加东西往哪放

| 要加的 | 放哪 | 谁读到 |
|---|---|---|
| 内容短，所有工具、所有角色都要用 | `rules/common.md` | 主脑 + 执行器 |
| 只有主脑用，每个会话都要 | `rules/brain.md` | 主脑 |
| 只有执行器用 | `rules/executor.md` | 执行器 |
| 主脑某个流程才用，内容长 | 全局 skill，`~/.claude/skills/` | 主脑，按需 |
| 某个项目的约定、命令、门禁 | 项目根目录 `AGENTS.md` | 主脑 + 执行器 |
| 只有某个项目用的 skill | 项目 `.claude/skills/` | 主脑，按需 |
| 别人分享的 skill | 先吸收进上面对应的文件；不行再装成项目 skill；全局最后考虑（261004:185） | — |
| MCP | 全局不开；哪个项目要用，就在那个项目目录里 `claude mcp add`（默认 local：只对你、只对这个项目生效）；有命令行工具就不用 MCP（261004:169） | 主脑 |

上限是硬的：主脑 24KB、执行器 12KB（261004:139）。加一条之前，先想清楚删哪条。

## 5. magpie 管什么

- 路由组、组内模型、额度、降级：照旧，调度层不管。
- Library 的 skill：karpathy-guidelines 照旧勾给 Claude、Codex、Cursor、Pi。勾 Pi 只影响手动开的 Pi。
- Library 的 MCP：context7、deepwiki、exa 停掉给 Claude 的下发；Codex、Cursor 不动。
- 共享指令：不用，不勾给任何工具。`~/.agents/AGENTS.md` 不再维护，以 `rules/common.md` 为准。

## 6. 用脚本拦住的（不靠提示词）

- `agent-run`：sandbox 只允许执行器写 worktree、只允许连本机网络。
- `agent-gate`：编译和测试通过、改动全部提交、没改 AGENTS.md，才算绿。
- 大小上限：`install.sh` 管主脑 24KB，`agent-dispatch` 管执行器 12KB。
- `agent-selftest`：抓包检查执行器实际收到的上下文；检查 CLAUDE.md 是否等于 common + brain。

对应 260809:106"能用脚本保证的事情，就不要只靠提示词"。

## 7. 为什么这样定

1. **执行器不带 skill 和 MCP**：261004:135"Pi 执行器启动时直接关掉 Skill"，执行器只需要把这张卡干完。
2. **karpathy 不进 common**：主脑还要生成图片、写文章，写代码规范在这些会话里用不上。只有特定流程才需要的内容放按需加载的 skill（261004:139）。执行器每张卡都写代码，所以它在 executor.md 里常驻。
3. **common 只放短的、所有角色都用的**：每样常驻的东西都要答得上"它凭什么在这里"（261004:187）。
4. **common.md 自己维护，不用 magpie 共享指令**：2026-10-28 定。放在本仓库进 git（261004:92），主脑和执行器从同一个文件拼，改一处两边生效。
5. **项目规则由 Pi 自己读**：拼进 prompt 会算进 12KB，还可能重复注入（`docs/plan.md` 决策 13）。
6. **MCP 放项目级**：每个 MCP 都带一份不短的说明书（261004:86、165–169）；本机 deepwiki 的说明里就有一大段用不上的 devin_* 工具。

## 8. 落地改动

1. 新建 `rules/common.md`、`rules/brain.md`（内容见第 1 节）；`rules/executor.md` 改第 2 条。
2. `install.sh`：生成 `~/.claude/CLAUDE.md` = common + brain，超过 24KB 拒绝；生成前备份原文件。若自动权限检查拦住覆盖，由你执行 `! ~/Documents/project/agent-dispatch/install.sh`。
3. `agent-dispatch`：prompt 改为 common + executor + 卡；12KB 上限把 common 也算进去。
4. `agent-selftest`：抓包检查改为"用户消息以 common 开头，接着 executor"；新增"CLAUDE.md 等于 common + brain，且不超过 24KB"，改了底稿忘了重跑 `install.sh` 会报出来。
5. magpie：三个 MCP 各执行一次 `magpie library mcp agents <name> codex,cursor`。
6. 文档：`docs/plan.md`（组件表、第 5 节、决策 12–14）、`skills/dispatch/SKILL.md` 第 2 节。
7. 跑 `agent-selftest`，通过后提交。

不变：`routing.tsv`、magpie 路由组、worktree、门禁、合并、记分、Advisor。
