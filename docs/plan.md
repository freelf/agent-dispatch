# 多 Agent 调度方案（全局体系）

> 2026-10-23 起草，2026-10-26 实现第一版并用自测仓库跑通全程。
> 参考：《将军赶路不追小兔》（260809）第三层及附录 03–07、《Context 与 Loop》（261004）、magpie 文档。
> 仓库：`~/Documents/project/agent-dispatch`（本地 git，未提交、未推远端）。坑记在 `docs/lessons.md`。

## 1. 目标与原则

按 260809 第三层搭「主脑 + 调度层 + 执行层 + 门禁」：

- 主脑只做方案设计、拆卡、副本管理、验收、合并、复盘；执行器拿卡干活；门禁全绿才能合并。
- 能用脚本保证的事不靠提示词（选组、额度、渲染卡、门禁、隔离、清理都是脚本）。
- 体系按需长出来；每次踩坑记进 `docs/lessons.md`，记分卡用来修正路由。

## 2. 架构

```
你        提需求、定方向                                        同意合并、从基线建 MR、发版
          │                                                          ▲
主脑层    ① 拆卡 ──▶ ② 副本管理 ─────┐               ⑥ 验收 · 记分 ──▶ ⑦ 合并 ──▶ ⑧ 复盘
(Claude Code,          (排顺序、建 worktree)│                  ▲
 Opus 5.5 经 magpie)                       ▼                  │
调度层                      ③ agent-dispatch：查表选组 → 额度水位 → 渲染卡 → 派发
(脚本 + magpie)                            │                  │
                                           ▼                  │
执行层                      ④ Pi 无头（sandbox 内），magpie 路由组选模型
                                           │ 提交             │
                                           ▼                  │
门禁                        ⑤ agent-gate：编译 + 测试 ──绿──────┘
                                └──红──▶ 主脑写修复说明 → 回到 ③（最多修 3 轮，之后找 Advisor）
```

| 决定 | 谁 |
|---|---|
| 派不派、怎么拆、task_type、级别 | 主脑 |
| 哪些卡并行、从哪个基线拉、什么时候合、冲突怎么解 | 主脑（`agent-worktree` / `agent-merge` 执行） |
| 用哪个组、推理强度、额度够不够派 | 调度层查表（`routing.tsv` + `magpie quota`） |
| 组里具体哪个模型接、额度不够降级给谁 | magpie（`routing=order` + `stays=session`） |
| 能不能合并 | 门禁 + 主脑验收 + 你点头 |
| 失败后升级 | 主脑：记 escalated，提一级、用新卡 id 重派 |

`context-coupled` 的卡（要用当前对话上下文）不走调度层，主脑直接派 Claude Code 原生子代理。
Claude 不跑无头、不进执行器路由组（订阅条款风险）。

## 3. 组件

| 组件 | 位置 | 说明 |
|---|---|---|
| `agent-worktree <id> [base]` | bin/ | 从基线拉 `card/<id>`，worktree 在 `<仓库同级>/<仓库名>-cards/<id>`；把被忽略的 `AGENTS.md`、`CLAUDE.md`、`.codex/skills`、`.serena/*.yml` 软链接进去（只链主仓库有、worktree 没有、且被忽略的） |
| `agent-dispatch <wt> <card> [fix-notes]` | bin/ | 调度层入口。解析卡头 → 查 `routing.tsv` → 查组内订阅额度（缺省水位 90%）→ 渲染 prompt（角色声明 + 执行规则 + 基线 AGENTS.md + 卡正文 [+ 上轮门禁输出 + 修复说明]，≤12KB）→ `agent-run` → `agent-gate` → 从 `magpie usage` 按会话号查实际模型 → 写 `dispatch.json`。退出码 0 绿 / 1 红 / 2 错误 / 3 需主脑处理（修满 3 轮、额度过线） |
| `agent-run [--read-only] <wt> <prompt> <group> <effort> <label>` | bin/ | 在 sandbox 里跑 Pi，见第 5 节。检查 Pi 最后回复的 `stopReason`，`error/aborted` 判失败（Pi 出错也可能以 0 退出） |
| `agent-gate <wt> <base>` | bin/ | 门禁，见第 6 节 |
| `agent-advise <wt> <question>` | bin/ | Advisor：`advisor` 组、只读 sandbox、空白上下文；材料 = 卡 + 各轮门禁结论 + 改动概况 + 主脑的问题，不给执行器对话历史 |
| `agent-score <id> <outcome> <scope> <taste> <note>` | bin/ | 记分卡，字段沿用 06；组、模型、轮次、耗时从运行记录自动填；note 必填 |
| `agent-merge <id> <base>` | bin/ | 门禁再跑一次，绿了在基线所在工作区 `merge --no-ff`；冲突 abort 并保留 worktree；成功后删 worktree 和卡分支 |
| `routing.tsv` | 根目录 | (task_type, 级别) → 组 + 推理强度 |
| `skills/dispatch/SKILL.md` | → `~/.claude/skills/dispatch` | 主脑侧规则：分级、写卡、副本管理、修复、Advisor、验收打分、合并、接入新项目、复盘 |
| `skills/dispatch/card-template.md` | 同上 | 卡模板：卡头 id/type/level/base/depends + 目标/非目标/修改边界/完成条件 |
| `install.sh` | 根目录 | bin/ → `~/.local/bin`，skills/ → `~/.claude/skills`，可重复执行 |

运行记录：`~/.local/state/agent-dispatch/runs/<仓库名>/<卡id>/<时间戳>-<exec|fix-N|advise>/`
（prompt.md、card.md、events.jsonl、stderr.log、last.md、session、sandbox.sb、gate.txt、gate/、dispatch.json）。
记分卡：`~/.local/state/agent-dispatch/scorecard.jsonl`。

## 4. 选模型

magpie 路由组（都是 `routing=order` + `stays=session`）：

| 组 | 成员（按顺序） | 用途 |
|---|---|---|
| `exec-light` | codex/gpt-6-luna → codex/gpt-6.1-sol | 脚手架、S 级补测试文档 |
| `exec-main` | codex/gpt-6.1-sol → codex/gpt-6-astra | 主力执行 |
| `advisor` | codex/gpt-6-astra | Advisor，只读 |

映射表见 `routing.tsv`，初始值是拍的，靠记分卡修正。以后接入第二家模型（DeepSeek、Kimi 等），只往组里加成员，脚本和映射表不用动。

已验证（2026-10-26）：
- Pi 用 `--model magpie/group/<id>` 选组；Pi 的会话号 = `magpie usage --csv` 的 `session`，`served_model` 是实际模型。magpie 把 Pi 的请求记成 agent=OpenAI，不影响按会话查。
- `stays=session` 下同一会话的请求固定在一个模型；`stays=off` 时逐个交替（对照组）。
- `routing=order` 下首选被 pause 时由第二个成员接。**真实额度耗尽时的降级还没验证**。
- 组名写错时 magpie 返回 404，执行器失败退出，不会静默退回默认模型。

## 5. 执行器：Pi + sandbox

- Pi 0.73.0（`npm i -g @mariozechner/pi-coding-agent`），`magpie pi` 已写好 `~/.pi/agent/models.json`。
- 每次运行给 Pi 一份临时配置目录（只含 models.json + 关遥测的 settings），`PI_OFFLINE=1`；`--no-session --no-skills --no-extensions --no-context-files`，工具 `read,bash,edit,write`（Advisor 为 `read,grep,find,ls,bash`）。
- 规则底座不靠 Pi 自己发现，由 `agent-dispatch` 从**基线**取 AGENTS.md 拼进 prompt（避免 AGENTS.md / CLAUDE.md 重复注入，也避免读到卡分支里被改过的版本）。
- 首轮输入约 4.5k token（Codex 为 14k–21k）。
- 隔离（`sandbox-exec`，规则写在每次运行的 `sandbox.sb`）：
  - 写：worktree、它的 gitdir、`objects/`、`refs/heads/card/`、`logs/refs/heads/card/`、临时目录；`--read-only` 时去掉 worktree 和 git 路径。
  - 网：只允许 localhost（magpie），外网拦截。
  - 已验证：卡分支能提交；移动 main、写 home、访问外网都被拦；只读模式下写 worktree 和提交被拦。
- 已知无害噪音：提交后打印 `packed-refs.lock: Operation not permitted`（清理临时 ref 时触发，提交已成功）。执行器不能用 `git stash`。
- 限制：执行器在 sandbox 里自查编译测试时，需要写 home 缓存或联网的构建工具（Gradle、CocoaPods、hvigor 等）会失败；门禁在 sandbox 外跑，不受影响。

## 6. 门禁

通过标准只有两条：**编译通过、测试通过**。

- 前提：工作区全部提交、相对基线有新提交、卡分支没改 AGENTS.md。
- 命令由项目在 AGENTS.md 里声明（框架统一在 `agent-gate`，项目只声明参数，对应 07 的"一行引用继承全套检查"）：
  ````
  ```agent-gate
  build <命令>
  test  <路径前缀/> <命令>     # 只在改到该前缀时跑
  test  none                  # 显式声明没有
  ```
  ````
- AGENTS.md 从基线读：入库的读 `<base>:AGENTS.md`，被忽略的读主仓库根目录那份。
- **项目没声明（没有 AGENTS.md 或没有代码块）就跳过**（2026-10-27 定）：只做前提检查，返回 3（SKIPPED，不算绿）；`agent-dispatch` 返回 4，改动直接交给主脑验收；`agent-merge` 允许合并，但会打印"没有编译测试验证"。公司仓库先不加声明，需要时再加。
- 判红：有代码块但 build/test 没声明、本次改动没有任何 build/test 覆盖、命令失败、超时（`AGENT_GATE_TIMEOUT` 缺省 1800s）。声明了就必须真跑，"没跑"不算通过。
- build 全过才跑 test；以退出码判定；每条命令的完整输出写进运行记录的 `gate/`。
- 触发点：`agent-dispatch` 跑完执行器后自动跑；`agent-merge` 合并前强制再跑。门禁在本机跑，不是公司 CI：卡分支不推远端，公司仓库也不能加个人 CI。

AI 审查、规则式审查（OCR）、改动量、格式检查不在门禁里：编译和测试之外的判断由主脑验收负责。

## 7. 已定决策

1. 主脑 = Claude Code 交互会话；执行器 = Pi 无头（2026-10-26 由 Codex 改为 Pi）；Advisor 机械触发走 `agent-advise`，主脑主动请教可派 Claude 子代理。
2. 分级标准写死在 SKILL.md：不派 / S / M / L（L 必须拆）。
3. 分支：`master` ← 你建 MR；基线（如 `zdp/feature/v2.0.0`）← 卡分支本地 `merge --no-ff`，不推远端。
4. 调度体系全局化，项目里只放项目自己的东西（AGENTS.md 里的门禁声明）。
5. 门禁 = 编译 + 测试，命令在项目 AGENTS.md 声明。
6. 副本管理由主脑决策、脚本执行；以后并发多了再考虑把依赖做成卡字段交给调度层排队。
7. 修复：同一 worktree、每轮新会话，最多修 3 轮，之后必须先找 Advisor。升级用新卡 id 重派。
8. 试点阶段每张卡合并前要你点头。
9. 公司代码可以交给外部模型；ChatGPT 订阅可以给 Pi 用（2026-10-27 确认）。
10. 公司仓库暂不声明门禁：执行器改完直接交主脑验收；主脑在验收结论里写明哪些编译测试没验证。

## 8. 自测结果（2026-10-26，临时仓库，未用公司代码）

一张 backend-logic / S 的卡：`agent-worktree` → `agent-dispatch`（exec-main / medium，实际 gpt-6.1-sol，执行器先写测试再实现、两次小步提交，1 分 24 秒）→ 门禁 GREEN → 人工注入 bug 后门禁 RED → 带修复说明派 fix-1 → GREEN → 修满 3 轮时 dispatch 返回 3 → `agent-advise`（astra / xhigh，只读）给出结论 → `agent-score` → `agent-merge` 合并并清理。
另测：dispatch 的 9 个错误用例、门禁的 4 个判红用例（改 AGENTS.md、无代码块、改动未覆盖、超时）、score 的 2 个错误用例，均符合预期。测试数据已清理。

## 9. TODO

**下一步**

1. ~~合规确认~~ 已确认可以（见第 7 节第 9 条）。
2. ~~mobileai_sdk 加门禁声明~~ 暂不加，走"门禁已跳过 → 主脑验收"（2026-10-27 已在 mobileai_sdk 上验证读的是被忽略的 AGENTS.md、返回 SKIPPED）。以后要加时：命令从项目真实配置核实；`Eve_Core/tests/scheduling` 编译失败（`eve_lua_task_bootstrap.h` 在 `b1be88cc` 被删）。
3. 挑一张真实的 S 级卡试跑，验收后打分。注意 mobileai_sdk 的 AGENTS.md 约 6.5KB，拼进 prompt 后卡正文只剩约 4KB。

**以后按需做**

4. 真实额度耗尽时的组内降级（等碰到再看 `magpie usage` 的 `handed_on/tries`）。
5. "门禁连续两轮报出新问题"这个 Advisor 信号目前靠主脑判断，没有自动化。
6. 执行器运行没有超时上限；并发上限（暂定 3）由主脑自管。
7. 执行器 sandbox 按需放开构建缓存目录（如 `~/.gradle`），让执行器能在 sandbox 里自查。
8. `agent-gate` 不带 `AGENT_GATE_LOG_DIR` 时（`agent-merge` 调用）日志留在临时目录，可改为写进运行记录。
9. 写一个自测脚本，把第 8 节的流程固化下来；升级 Pi / magpie 后先跑自测（261004 的教训：版本钉住了行为没钉住）。
10. 第二家执行器模型（DeepSeek 等）接入后：加进组、考虑 OCR 规则审查。
11. 你自己的仓库（如博客）把 AGENTS.md 里的验证命令改写成 `agent-gate` 代码块。
12. agent-dispatch 仓库首次提交；是否推到远端（私有）。
13. Claude Code 会话记录永久保留（`cleanupPeriodDays`）。
