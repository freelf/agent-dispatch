# 多 Agent 调度方案（全局体系）

> 2026-10-23 起草，2026-10-26 实现第一版并用自测仓库跑通全程。
> 参考：《将军赶路不追小兔》（260809）第三层及附录 03–07、《Context 与 Loop》（261004）、magpie 文档。
> 仓库：`~/Documents/project/agent-dispatch`（本地 git，未提交、未推远端）。坑记在 `docs/lessons.md`。

## 1. 目标与原则

按 260809 第三层搭「主脑 + 调度层 + 执行层 + 门禁」：

- 主脑只做方案设计、拆卡、副本管理、验收、合并、复盘；执行器拿卡干活；门禁全绿才能合并。
- 能用脚本保证的事不靠提示词（选组、渲染卡、门禁、隔离、清理都是脚本；额度交给 magpie）。
- 体系按需长出来；每次踩坑记进 `docs/lessons.md`，记分卡用来修正路由。

## 2. 架构

```
你        提需求、定方向                                        同意合并、从基线建 MR、发版
          │                                                          ▲
主脑层    ① 拆卡 ──▶ ② 副本管理 ─────┐               ⑥ 验收 · 记分 ──▶ ⑦ 合并 ──▶ ⑧ 复盘
(Claude Code,          (排顺序、建 worktree)│                  ▲
 Opus 5.5 经 magpie)                       ▼                  │
调度层                      ③ agent-dispatch：查表选组 → 渲染卡 → 派发
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
| 用哪个组、推理强度 | 调度层查表（`routing.tsv`） |
| 组里具体哪个模型接、额度、降级 | magpie 自己调度（组成员、routing、stays 都在 magpie 里维护） |
| 能不能合并 | 门禁 + 主脑验收 + 你点头 |
| 失败后升级 | 主脑：记 escalated，提一级、用新卡 id 重派 |

`context-coupled` 的卡（要用当前对话上下文）和 L 级里拆不开的部分不走调度层，走「子代理路径」：照常 `agent-worktree` 建副本，主脑派 Claude Code 原生子代理（Opus / Fable）在 worktree 里做，之后照常 `agent-gate` → 验收 → `agent-merge`，不记分卡。
Claude 不跑无头、不进执行器路由组（订阅条款风险）。

## 3. 组件

| 组件 | 位置 | 说明 |
|---|---|---|
| `agent-worktree <id> [base]` | bin/ | 从基线拉 `card/<id>`，worktree 在 `<仓库同级>/<仓库名>-cards/<id>`；把被忽略的 `AGENTS.md`、`CLAUDE.md`、`.codex/skills`、`.serena/*.yml` 和每一层被忽略的 `node_modules` 软链接进去（只链主仓库有、worktree 没有、且被忽略的；`node_modules/` 这类只匹配目录的规则管不到链接，改为建真目录再逐项链接） |
| `agent-dispatch <wt> <card> [fix-notes]` | bin/ | 调度层入口。解析卡头 → 查 `routing.tsv` → 渲染 prompt（`rules/executor.md`（≤12KB）+ 卡正文 [+ 上轮门禁输出 + 修复说明]；项目 AGENTS.md 由 Pi 自己读）→ `agent-run` → `agent-gate` → 从 `magpie usage` 按会话号查实际模型 → 写 `dispatch.json`（含本轮新增提交、相对基线的文件数和增删行数）。退出码 0 绿 / 1 红 / 2 错误 / 3 先请教 Advisor（修满 3 轮，或最近三轮门禁都红且每轮报的都和上一轮不同）/ 4 项目未声明门禁 |
| `agent-run [--read-only] <wt> <prompt> <group> <effort> <label>` | bin/ | 在 sandbox 里跑 Pi，见第 5 节。检查 Pi 最后回复的 `stopReason`，`error/aborted` 判失败（Pi 出错也可能以 0 退出） |
| `agent-gate <wt> <base>` | bin/ | 门禁，见第 6 节 |
| `agent-advise <wt> <question>` | bin/ | Advisor：`advisor` 组、只读 sandbox、空白上下文；材料 = 卡 + 各轮门禁结论 + 改动概况 + 主脑的请教卡，不给执行器对话历史；请教卡三栏（机械事实 / 我的判断 / 我希望听到的答案），缺栏或没填拒绝 |
| `agent-score <id> <outcome> <scope> <taste> <note>` | bin/ | 记分卡，字段沿用 06；组、模型、轮次、耗时从运行记录自动填；note 必填 |
| `agent-merge <id> <base>` | bin/ | 门禁再跑一次，绿了在基线所在工作区 `merge --no-ff`；冲突 abort 并保留 worktree；成功后删 worktree 和卡分支。合并提交末尾写追溯字段 `Agent-Card/Executor/Group/Models/Rounds/Sessions`（取自运行记录） |
| `agent-stats [天数]` | bin/ | 记分卡交叉分析（附录 06）：按「组 × task_type × 级别」和实际模型出通过率、升级率、一次到位率、平均轮次、两项分数 |
| `agent-selftest [--real]` | bin/ | 自检，见第 8 节。缺省把执行器请求发到本机抓包服务，不花模型钱；`--real` 再用真模型派一张小卡 |
| `routing.tsv` | 根目录 | (task_type, 级别) → 组 + 推理强度 |
| `rules/executor.md` | rules/ | 执行器规则：角色声明 + 执行规则 + 写代码规范（吸收自 karpathy-guidelines），≤12KB |
| `skills/dispatch/SKILL.md` | → `~/.claude/skills/dispatch` | 主脑侧规则：分级、写卡、副本管理、修复、Advisor、验收打分、合并、接入新项目、复盘 |
| `skills/dispatch/card-template.md` | 同上 | 卡模板：卡头 id/type/level/base/depends + 目标/非目标/修改边界/完成条件 |
| `skills/dispatch/advise-template.md` | 同上 | 请教卡模板，三栏 |
| `install.sh` | 根目录 | bin/ → `~/.local/bin`，skills/ → `~/.claude/skills`，可重复执行 |

运行记录：`~/.local/state/agent-dispatch/runs/<仓库名>/<卡id>/<时间戳>-<exec|fix-N|advise>/`
（prompt.md、card.md、fix-notes.md、rules、events.jsonl、stderr.log、last.md、session、sandbox.sb、gate.txt、gate/、dispatch.json；advise 轮另有 question.md）。
记分卡：`~/.local/state/agent-dispatch/scorecard.jsonl`。

## 4. 选模型

分工：主脑给卡标 task_type 和级别 → `routing.tsv` 查出路由组和推理强度 → magpie 决定组内用哪个模型、额度、降级。
组成员、routing、stays 都在 magpie 里维护，以 `magpie group <id>` 为准，这里不抄。

| 组 | 用途 |
|---|---|
| `exec-light` | 脚手架、S 级补测试文档 |
| `exec-main` | 主力执行 |
| `advisor` | Advisor，只读 |

为什么要映射表（2026-10-27 定）：对应文章 04 的 chains（任务类型 → 链），链的内容交给 magpie，剩下"类型走哪个组"这层用表固定，不让主脑每次自己挑组（同类卡走同一组，记分卡才可比）。初始值是拍的，靠记分卡修正；换组或调强度只改表。

已验证（2026-10-26）：
- Pi 用 `--model magpie/group/<id>` 选组；Pi 的会话号 = `magpie usage --csv` 的 `session`，`served_model` 是实际模型。magpie 把 Pi 的请求记成 agent=OpenAI，不影响按会话查。
- `stays=session` 下同一会话的请求固定在一个模型；`stays=off` 时逐个交替（对照组）。
- `routing=order` 下首选被 pause 时由第二个成员接。额度耗尽时的降级由 magpie 负责，调度层不查额度。
- 组名写错时 magpie 返回 404，执行器失败退出，不会静默退回默认模型。
- 已知（2026-10-27，不改）：magpie 用量里 Pi 的请求显示为 agent=OpenAI。Pi 走 OpenAI JS SDK，User-Agent 是 `OpenAI/JS 6.26.0`，magpie 按 User-Agent 归属 agent（实测 `pi/0.73.0` 会记成 pi，但这是未文档化的行为，`magpie pi` 自己写的配置也不带标识）。不影响调度（按会话号查模型）；以后要按 agent 写 magpie 规则或单独统计执行器用量时，再向 magpie 反馈或试 `gateway-key`。

## 5. 执行器：Pi + sandbox

- Pi 0.73.0（`npm i -g @mariozechner/pi-coding-agent`），`magpie pi` 已写好 `~/.pi/agent/models.json`。
- 每次运行给 Pi 一份临时配置目录（只含 models.json + 关遥测的 settings），`PI_OFFLINE=1`；`--no-session --no-skills --no-extensions`，工具 `read,bash,edit,write`（Advisor 为 `read,grep,find,ls,bash`）。
- skill（2026-10-27 定稿）：执行器一律不加载 skill（`--no-skills`）。执行器规则是 `rules/executor.md` 一个文件（角色声明 + 执行规则 + 写代码规范，写代码规范吸收自 karpathy-guidelines），`agent-dispatch` 原样拼在卡前面；超过 12KB 就拒绝派发。
- MCP：执行器暂时用不了，有两处障碍。① 装的 `@mariozechner/pi-coding-agent` 0.73 没有 MCP，这个包名已停在 0.73.1，Pi 改到 `@earendil-works/pi-coding-agent`（1.4.0），据 pi-mcp-adapter 的 README，Pi 0.99 起自带 MCP；② sandbox 禁外网，context7、exa、deepwiki 都要联网，需要在 sandbox 外起一个本机 MCP 中转，执行器经 localhost 访问。现在由主脑用 MCP 查好、写进卡里。
- 项目规则（2026-10-27 改）：由 Pi 自己读。Pi 从 worktree 往上，每级目录只取第一个 AGENTS.md / CLAUDE.md 放进系统提示（0.73 `dist/core/resource-loader.js`），所以同一目录不会重复注入；临时配置目录里没有全局 AGENTS.md，worktree 的上级目录目前也没有。项目统一用根目录 AGENTS.md，必须入库或被 .gitignore 忽略（被忽略的由 `agent-worktree` 软链进去），否则 worktree 里没有，执行器读不到。`agent-run` 按同样的规则查一遍，打印 `RUN: rules <文件>`。这条依赖 Pi 的行为，升级 Pi 后要重新验证。
- 首轮输入约 4.5k token，不含项目 AGENTS.md（Codex 为 14k–21k）。
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
2. 分级标准写死在 SKILL.md：不派 / S / M / L。L 按"有没有跨模块设计取舍"判，不按行数；L 不进执行器，按顺序走：渐进替换拆成 S/M → 主脑先定骨架（走子代理路径）再派填空 → 整块走子代理路径（2026-10-27 定）。
3. 分支：`master` ← 你建 MR；基线（如 `zdp/feature/v2.0.0`）← 卡分支本地 `merge --no-ff`，不推远端。
4. 调度体系全局化，项目里只放项目自己的东西（AGENTS.md 里的门禁声明）。
5. 门禁 = 编译 + 测试，命令在项目 AGENTS.md 声明。
6. 副本管理由主脑决策、脚本执行；以后并发多了再考虑把依赖做成卡字段交给调度层排队。
7. 修复：同一 worktree、每轮新会话，最多修 3 轮，之后必须先找 Advisor。升级用新卡 id 重派。
8. 试点阶段每张卡合并前要你点头。
9. 公司代码可以交给外部模型；ChatGPT 订阅可以给 Pi 用（2026-10-27 确认）。
10. 公司仓库暂不声明门禁：执行器改完直接交主脑验收；主脑在验收结论里写明哪些编译测试没验证。
11. 主脑规则分两层（对应 261004 的"主脑专属常驻 + Skill 按需加载"）：常驻的角色声明写在全局 `~/.claude/CLAUDE.md`（两行：只调研规划拆卡验收、改代码的需求走 dispatch skill），流程细节都在 `skills/dispatch/SKILL.md`（2026-10-27 定）。
12. 执行器不加载任何 skill，规则在派活时现场渲染，照 261004:135："执行器这一侧，是派活那一刻现场渲染的：只拿共用底座里执行器用得上的部分，加上它那家工具的段落，再拼上任务卡和角色声明。Pi 执行器启动时直接关掉 Skill"。执行器规则只有一个文件 `rules/executor.md`（角色声明 + 执行规则 + 写代码规范），上限 12KB（261004:139），"加一条规则之前，就必须先想清楚要删哪条"。skill 照 261004 处理：别人的 skill "最优解是吸收内化到自己的工作流里"（185），karpathy-guidelines 已原文吸收进 `rules/executor.md`；Library 里的 skill 只给主脑和交互式工具按需加载，执行器不加载（2026-10-27 定稿，取代当天先后做过的"--skill 让执行器自己读"和"把 Library 的 skill 正文拼进 prompt"）。
13. 项目规则由 Pi 自己读，调度层只拼自己的角色声明、执行规则和卡（对应附录 05："Agent 进入项目前先读这个文件"）。原因：拼进 prompt 会把项目 AGENTS.md 算进 12KB 上限，eve 的 AGENTS.md 有 6KB，修复轮就会超；Pi 每级目录只取一个规则文件，不会重复注入。12KB 上限只管我们渲染的规则部分（第 12 条），不含项目 AGENTS.md 和卡。项目统一用 AGENTS.md（2026-10-27 定）。
14. 执行器要遵守的写代码习惯只改 `rules/executor.md` 这一处；Library 里的 skill 和 Instructions 都进不了执行器（`--no-skills`，临时配置目录也不带 `~/.pi/agent/AGENTS.md`）（2026-10-27 定）。
15. 2026-10-28 对照两篇文章补齐的机制：建 worktree 接上每一层 node_modules（261004「建工作目录…自动把每一层配置都接上」）；Advisor 请教卡三栏、「门禁连续两轮报出新问题」由脚本判（261004）；合并提交写追溯字段、`dispatch.json` 记提交和改动量（260809「每次提交都能追溯」）；`agent-stats` 交叉分析和一次到位率（附录 06、260809）；教训单按「这个坑现在还踩得到吗」关单（261004）；`agent-selftest` 每个检查都配已知该红的输入（261004「先喂一个已知答案为'否'的输入」「版本钉住了但行为没钉住」）；Claude Code 会话记录永久保留（261004 保留轨迹，`cleanupPeriodDays` 36500）。
    没做的和原因：门禁里的 AI 审查 / OCR / 格式检查（第 5 条，门禁只管编译和测试）；额度水位和降级链（magpie 负责）；定时分诊、架构扫描、周复盘（要常驻调度器，现在作为 SKILL 第 8 节的手动步骤）；跨 Agent 共享记忆（只有一个主脑）；前端录屏验收（目前没有前端卡）；`.env`、`local.properties` 不链进 worktree（可能有密钥，会随请求发给模型商）。

## 8. 自测结果（2026-10-26，临时仓库，未用公司代码）

一张 backend-logic / S 的卡：`agent-worktree` → `agent-dispatch`（exec-main / medium，实际 gpt-6.1-sol，执行器先写测试再实现、两次小步提交，1 分 24 秒）→ 门禁 GREEN → 人工注入 bug 后门禁 RED → 带修复说明派 fix-1 → GREEN → 修满 3 轮时 dispatch 返回 3 → `agent-advise`（astra / xhigh，只读）给出结论 → `agent-score` → `agent-merge` 合并并清理。
另测：dispatch 的 9 个错误用例、门禁的 4 个判红用例（改 AGENTS.md、无代码块、改动未覆盖、超时）、score 的 2 个错误用例，均符合预期。测试数据已清理。
2026-10-27 改成 Pi 自己读项目规则后复测（临时仓库，根目录同时放 AGENTS.md 和 CLAUDE.md）：本机抓包看 Pi 发出的请求，AGENTS.md 在系统提示里只出现 1 次，CLAUDE.md 没被读，prompt 里没有第二份；再派一张真实卡（exec-main / gpt-6.1-sol），`RUN: rules` 指向 worktree 的 AGENTS.md，提交信息按 AGENTS.md 的约定带上 `[selftest]` 前缀，门禁 GREEN。

2026-10-28 固化成 `agent-selftest`（测试仓库建在状态目录下，不碰真实记分卡；全部通过就删掉）。离线 54 项：脚本里变量名不直接贴中文；worktree 链接顶层和嵌套 node_modules 后工作区干净；门禁 5 种该红的输入都红、正常改动绿、没声明门禁返回 3；规则文件超 12KB 拒绝派发；抓包看执行器实际上下文（AGENTS.md 恰好一次、不读同目录 CLAUDE.md、没有 skill 清单、用户消息以 `rules/executor.md` 开头、卡正文一次）并用不带 `--no-skills` 的对照组确认 skill 检查判得了红；`dispatch.json` 新字段；sandbox 写权限 6 项和外网；Advisor 请教卡校验和只读；连续新问题 / 同一问题 / 修满 3 轮三种停止条件；合并追溯字段、删 worktree 不动主仓库。`--real` 另 5 项（真模型 exec-light，门禁绿、提交带 `[selftest]`、只改边界内文件、合并提交查到实际模型），共 59 项通过。
自检本身的反证：在仓库副本里分别植入 7 个 bug（去掉 `--no-skills`、不判连续新问题、合并不写追溯、链接不改真目录、sandbox 写权限全放开、请教卡不校验、变量贴中文），每个都让对应检查变红。这一步还查出自检脚本自己有一处 `$desc（` 在 `set -u` 下直接崩掉。

## 9. TODO

已完成：合规确认（第 7 节第 9 条）；mobileai_sdk 暂不加门禁声明、走"门禁已跳过 → 主脑验收"（已验证返回 SKIPPED）；额度和降级交给 magpie；L 级处理与子代理路径；主脑常驻规则；仓库首次提交 `87d7b40`。

**现阶段：跑通 workflow**

1. ~~提交 2026-10-27 的改动~~ `457ee6b`。
2. ~~DeepSeek 加进路由组~~ 已加在 `exec-light` / `exec-main` 末尾。
3. ~~第一张真实卡~~ 2026-10-27 在 eve-debug-tools 跑完 `pkg-ext-filter`（backend-logic / S，4 轮，全部 gpt-6.1-sol，执行器合计约 10 分钟、$0.49），主脑验收后合入本地 master `6b4b2c7`。坑见 `docs/lessons.md`。常驻规则是否生效还没在新会话里验证。
4. 修第一张卡暴露的问题：
   - ~~项目没有 AGENTS.md 时退而拼 CLAUDE.md~~ 改为 Pi 自己读项目规则（第 7 节第 13 条），项目统一用 AGENTS.md。
   - ~~`agent-worktree` 按需把依赖目录（如 `node_modules`）链接进 worktree~~ 每一层被忽略的 node_modules 自动链接（2026-10-28）。
   - ~~区分"修复轮"和"补充需求轮"~~ 补充需求另开新卡、`depends` 写当前卡（dispatch SKILL 第 4 节，2026-10-28）。

**跑通之后：调整任务和路由组**

5. 按记分卡调整 `routing.tsv` 的分法和 magpie 组成员（S/M 的推理强度、task_type 是否简化）。
6. ~~请教卡改成三栏~~ 已做，`agent-advise` 校验三栏（2026-10-28）。Advisor 不另建 Fable 子代理：`agent-advise` 已经是只读、空白上下文、更强模型；主脑主动请教时 SKILL 第 4 节已允许派 Claude 子代理。
7. Pi 里隐藏 Claude 模型（`magpie visible pi`），防止误选订阅模型跑无头。

**以后按需做**

8. ~~"门禁连续两轮报出新问题"自动化~~ `agent-dispatch` 返回 3（2026-10-28）。
9. 执行器运行没有超时上限；并发上限（暂定 3）由主脑自管。
10. 执行器 sandbox 按需放开构建缓存目录（如 `~/.gradle`），让执行器能在 sandbox 里自查。
11. `agent-merge` 调用门禁时日志留在临时目录，可改为写进运行记录。
12. ~~自测脚本~~ `agent-selftest`（2026-10-28），升级 Pi / magpie 或改脚本后先跑。
13. ~~`dispatch.json` 自动记实际改动的文件数和行数~~ 已记 `diff_vs_base` 和本轮 `commits`（2026-10-28）。
14. OCR 规则审查（文章推荐，可以配 DeepSeek Flash）；目前门禁只管编译和测试，要加先定放在哪一环。
15. 你自己的仓库（如博客）把 AGENTS.md 里的验证命令改写成 `agent-gate` 代码块。
16. 仓库提交作者是公司邮箱（`zhangdongpo@kuaishou.com`），个人仓库是否改成个人邮箱；是否推到私有远端。
17. ~~Claude Code 会话记录永久保留~~ `~/.claude/settings.json` 设 `cleanupPeriodDays: 36500`（2026-10-28，改前备份在 `~/.claude/settings.json.bak-agent-dispatch-20261027`）。
