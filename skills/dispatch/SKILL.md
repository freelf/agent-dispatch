---
name: dispatch
description: 主脑派活手册：把开发需求拆成任务卡，派给无头执行器（Pi + magpie 路由组），门禁、验收、记分、合并。用户要求"派给执行器 / 拆卡 / 调度 / dispatch"，或一个需求要改多个文件、适合交给执行器时使用。
---

# 派活手册（主脑专用）

体系：主脑（你）拆卡、管副本、验收、合并、复盘 → 调度层（`agent-dispatch`：查表选组、渲染卡、派发、自动门禁；额度和降级由 magpie 路由组自己调度）→ 执行层（Pi，在 sandbox 里干活）→ 门禁（编译 + 测试）。
命令都在 PATH 上，在目标仓库里运行。完整方案见 `~/Documents/project/agent-dispatch/docs/plan.md`。

## 1. 分级：派不派、怎么派

| 级别 | 标准 | 处理 |
|---|---|---|
| 不派 | 单行机械改动 | 你直接改 |
| S | ≤3 文件、无设计取舍、diff <200 行 | 写卡派发 |
| M | 4–10 文件或跨模块或 200–1000 行 | 写卡派发 |
| L | 要跨模块做设计取舍，或改公共接口/数据结构且调用方要一起改（>1000 行作参考） | 不进执行器，按下面「L 级怎么办」处理 |

纯机械的大改动（批量改名、按固定模式生成）不算 L：标 `scaffold-bulk` / M，太大就按目录分批。

怎么判断：是估，不是量。只有两条线要判对——派不派、是不是 L；S 和 M 判错代价很小（多数只差推理强度），拿不准就标 M，不要为了分 S/M 多看代码。
1. 不模拟实现：不读函数体、不写草稿代码、不估行数。
2. 侦察只做两件事：定位改动点、查它的引用方（`find_symbol` / `find_referencing_symbols` / `Grep`），几次搜索就停。范围大时派 Explore 子代理（`model: sonnet` 或 `haiku`），只要它回文件清单和引用方数量，不要文件内容。
3. 是不是 L 只看一个问题：要不要跨模块做设计取舍、改别的模块在调用的接口或数据结构。要就是 L。
4. 搜完还列不出修改边界，说明还没看懂，不派：再侦察一轮，或先问 Advisor。
5. 判错由流程兜底：执行器明显超出边界、修复轮不收敛，就记 escalated 提一级重派（见第 5 节）。

task_type 只能用：`scaffold-bulk` / `test-docs` / `backend-logic` / `refactor` / `frontend-ui` / `context-coupled`。
`context-coupled`（要用当前对话上下文或会话里的专属工具）不走调度层，走下面的「子代理路径」。
你不挑模型：组和推理强度由 `routing.tsv` 按 (task_type, 级别) 决定，组内模型由 magpie 决定。

### L 级怎么办（按顺序试，拿不准走哪条先问 Advisor）

1. **渐进替换，拆成 S/M**（改接口、改数据结构首选）：新接口与旧接口并存（一张卡）→ 调用方分批迁移（每批一张卡）→ 删旧接口（一张卡）。用 `depends` 串起来，每一步都能编译、测试通过。
2. **你先定骨架，再派填空**（设计决定集中在少数几处）：接口、类型、测试骨架作为一张卡走「子代理路径」，合进基线后，填实现的部分拆成 S/M 卡正常派。设计取舍留在你这边，执行器只做填空。
3. **不拆，整块走子代理路径**（高度耦合、必须一次改完）：用 Opus / Fable 子代理在 worktree 里做，门禁和合并照常。

### 子代理路径（context-coupled 卡、L 级的骨架或整块）

1. `wt=$(agent-worktree <id> <base>)`，卡照常按模板写。
2. 用 Agent 工具派 Claude 子代理（Opus / Fable）：给它卡正文和 worktree 路径，要求只在 `$wt` 里改、先写测试、小步提交、结束时工作区干净、不改 AGENTS.md、不 push。它不在 sandbox 里，权限和你一样，所以修改边界要写清楚。
3. 子代理结束后跑 `agent-gate "$wt" <base>`，然后按第 5 节验收、按第 6 节 `agent-merge`。
4. 不记分卡（记分卡用来校准路由组，这条路径不走路由）；值得记的坑写进复盘。

## 2. 写卡

模板：`~/.claude/skills/dispatch/card-template.md`。卡写到仓库外（如 `$TMPDIR/cards/<id>.md`），不要放进 worktree。
- 只填内容：目标、非目标、修改边界、完成条件。角色声明、执行规则、写代码规范（magpie Library 里全部 skill 的正文，即共用底座）由调度层渲染时加上；项目根目录的 AGENTS.md 由执行器（Pi）自己读。这些都不用写进卡。
- 完成条件写成执行器要落成的测试用例，门禁跑项目测试时自然覆盖。
- 卡正文写得很长，说明该拆卡了。
- 派发输出的 `RUN: rules` 是执行器读到的项目规则文件。显示"无"而项目有 AGENTS.md，多半是 AGENTS.md 既没入库也没被忽略，worktree 里没有它。

## 3. 副本管理（你决定，脚本执行）

- 修改边界不重叠、且没有 depends 的卡才能并行；有依赖的卡等前一张合进基线后再建。
- 建副本：`wt=$(agent-worktree <id> <base>)`。不要手动 `git worktree add`。

## 4. 派发与修复

```
agent-dispatch "$wt" card.md                 # 第一次
agent-dispatch "$wt" card.md fix-notes.md    # 门禁红后的修复轮，fix-notes 写你判断的问题和修法
```
退出码：0 执行完且门禁绿 → 去验收；1 红 → 读输出写修复说明再派；2 用法/环境错误 → 修环境；3 需要你处理（修满 3 轮）；4 执行完但项目没声明门禁 → 按第 5 节"门禁已跳过"验收，不通过就写修复说明再派。

Advisor（机械信号触发，不靠感觉）：退出码 3、门禁连续两轮报出不同的新问题、定方向前没把握。
- `agent-advise "$wt" question.md`：只读、空白上下文、`advisor` 组。question 写你卡在哪、在几个方案间犹豫什么。
- 你主动请教设计问题，也可以派 Claude 子代理（Fable / Opus），只给它必要材料，不给失败历史。
Advisor 说放弃就放弃，记分 `abandoned`。

## 5. 验收（门禁绿，或门禁已跳过之后）

门禁绿：编译和测试已验证，你只看命令验证不了的（下面 1–3）。
门禁已跳过（项目没声明门禁，dispatch 退出码 4）：编译和测试没人独立验证过。除了 1–3，还要：
- 读执行器的自查说明（跑了哪些命令、哪些在 sandbox 里跑不了），不把自报当结论；
- 能在本机跑的测试你自己在 worktree 里跑一遍；跑不了的（要真机、要 IDE 的构建）在给用户的验收结论里写明"未验证编译/测试"。


1. `git -C "$wt" diff <base>...HEAD`：是否只改了修改边界内的文件，有没有多余的东西。
2. 目标是否真正达成；完成条件是否真的被测试覆盖（不是空测试）。
3. 写法：有没有过度设计、重复代码。

记分（每张卡都记，好坏都记，必须写理由）：
```
agent-score <id> <accepted|escalated|abandoned> <scope 0-3> <taste 0-3> "<理由，引用 commit/文件>"
```
- scope_discipline：3 严守边界 / 2 轻微越界不用返工 / 1 明显过度设计要砍 / 0 大面积自作主张
- taste：3 拿来即用 / 2 合格 / 1 能跑但丑 / 0 想重写
- 升级（escalated）：质量不行要重做时，记一条 escalated，然后提高一级（S→M）用新 id 重新建卡派发，不在原卡上继续修。

## 6. 合并

试点阶段：先把验收结论和 diff 摘要给用户，用户同意后再合。
```
agent-merge <id> <base>     # 门禁再跑一次，绿了 merge --no-ff，清理 worktree 和卡分支
```
冲突时脚本会 abort 并保留 worktree，由你解决或重新拆卡。只合进基线（feature 分支），不 push，不建 MR。

## 7. 接入新项目

项目 AGENTS.md 里有门禁声明才走编译测试门禁；没有就跳过（只查全部提交、有新提交、没改 AGENTS.md），改动直接交给你验收。需要时再加声明：
````
```agent-gate
build <编译命令>
test  <测试命令>
```
````
路径前缀（以 / 结尾）可限定只在改到时跑：`test project/Eve_Core/ <命令>`；没有这一项写 `test none`。命令要从项目真实配置核实。

## 8. 复盘

调度、脚本层面踩的坑，收工时追加到 `~/Documents/project/agent-dispatch/docs/lessons.md`（日期、现象、原因、改了什么）。
记分卡在 `~/.local/state/agent-dispatch/scorecard.jsonl`，攒够一批后按「组 × task_type」看通过率和升级率，据此改 `routing.tsv` 或 magpie 组成员。
