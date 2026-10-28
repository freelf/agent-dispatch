# 教训单

调度、脚本层面踩过的坑。格式：日期 · 现象 · 原因 · 改了什么 · 状态。

关单标准（261004）：只问一句"这个坑现在还踩得到吗"。固化成脚本、闸门或测试，机制上不可能再发生，才写"已关闭"并注明机制；只写进规则、SKILL 或卡的写法，算"未关闭"。

- 2026-10-26 · 执行器第一次测试能提交，但 sandbox 本应拦住 · `~/.codex/rules/default.rules` 里有 `git commit` 放行规则，命中后命令在 sandbox 外执行 · Codex 执行器加 `--ignore-rules`；改用 Pi 后由自写的 sandbox-exec 规则控制写权限 · 已关闭（机制：执行器换成 Pi，写权限只由 `agent-run` 生成的 sandbox.sb 决定）。
- 2026-10-26 · codex exec 后台运行卡住 · prompt 走参数且 stdin 不是终端时，codex 会等 stdin 的 EOF · 改为 prompt 走 stdin / stdin 接 /dev/null · 已关闭（机制：`agent-run` 启动 Pi 时 stdin 固定接 /dev/null）。
- 2026-10-26 · 执行器把 stderr 噪音当成命令失败而中止 · starship 写不了 `~/.cache` 日志往 stderr 报错 · 卡的执行规则写明以退出码判断成败 · 未关闭（只写进了执行规则第 4 条）。
- 2026-10-26 · 合并脚本 `unbound variable` · 变量名后紧跟全角括号被 shell 当成变量名的一部分 · 全角标点前的变量一律写成 `${var}` · 已关闭（机制：`agent-selftest` 第 0 节按字节扫 bin/ 和 install.sh，`$name` 后面紧跟非 ASCII 就判红；2026-10-28 植入 bug 反证时，这一条又在自检脚本自己身上踩到一次，扫描已带对照样本）。
- 2026-10-26 · `git branch -d` 误报未合并 · 它对照主仓库当前 HEAD，不是对照 base · 自己用 `merge-base --is-ancestor` 确认后用 `-D` · 已关闭（机制：`agent-merge`）。
- 2026-10-26 · sandbox 越权测试"没拦住" · 测试仓库放在 /tmp，而临时目录本来就可写 · 隔离测试一律放在 /tmp 和 $TMPDIR 之外 · 已关闭（机制：`agent-selftest` 固定把测试仓库建在状态目录下）。
- 2026-10-26 · Pi 连不上网关却以 0 退出 · Pi 把 Connection error 记在最后一条回复的 stopReason 里 · agent-run 检查 stopReason，error/aborted/缺失都判失败 · 已关闭（机制：`agent-run`）。
- 2026-10-27 · 第一张真实卡（eve-debug-tools/pkg-ext-filter）：项目规则没进执行器的 prompt · 项目只有入库的 CLAUDE.md、没有 AGENTS.md，调度层只拼 AGENTS.md，Pi 又带 `--no-context-files` · 改为 Pi 自己读项目规则（AGENTS.md，没有就读 CLAUDE.md），`agent-run` 打印 `RUN: rules` · 已关闭（机制：Pi 原生读规则文件；`agent-selftest` 检查系统提示里规则只出现一次）。
- 2026-10-27 · 执行器在 sandbox 里无法编译和测试 · worktree 里没有被忽略的依赖目录（node_modules），sandbox 又禁网、禁写 home，装不了 · `agent-worktree` 把每一层被忽略的 node_modules 链接进 worktree；`node_modules/` 这类只匹配目录的忽略规则管不到链接，改为建真目录再逐项链接 · 已关闭（机制：`agent-worktree`；`agent-selftest` 检查链接后工作区干净、删 worktree 不动主仓库）。
- 2026-10-27 · 一张 S 卡跑了 4 轮、记分 rounds=4 · 后 3 轮是用户中途补需求、主脑改结构，不是执行器失败，但只能走修复轮，且吃掉了全部修复轮次（修满后再要改就得先问 Advisor）· 记分 note 里写明原因；dispatch SKILL 规定补需求另开新卡 · 未关闭（只写进了 SKILL）。
- 2026-10-27 · 卡里写 `npx tsc` 会在 sandbox 里失败 · npx 要写 `~/.npm` 缓存 · 卡里写 `./node_modules/.bin/<工具>` · 未关闭（只写在卡的写法里）。
- 2026-10-27 · 项目没声明门禁时，"自查说明"成了唯一的编译测试证据 · 门禁 SKIPPED 后要主脑自己跑 · 主脑每轮都在 worktree 里跑 tsc、单测、build，再用构建出的 CLI 做端到端打包；这比执行器自报多抓出了软链接被跳过这类行为变化 · 未关闭（`agent-dispatch` 返回 4 让它不会被当成绿，但主脑自己跑测试只写在 SKILL 里）。
- 2026-10-27 · 项目 AGENTS.md 拼进 prompt 会撑爆 12KB 上限 · eve 的 AGENTS.md 有 6KB，第一张卡修复轮 prompt 已到 6.5KB，两者相加超过 12288 · 改为 Pi 自己读项目规则，调度层不再拼 AGENTS.md；12KB 只管 `rules/executor.md` · 已关闭（机制：`agent-dispatch` 只检查规则文件大小）。
- 2026-10-27 · magpie Library 里 karpathy-guidelines 的 pi 勾掉了一次，执行器悄悄就没了写代码规范 · 当时执行器的规范来自"勾了 pi 的 skill"，勾选一变就静默失效 · 执行器不再加载 skill，写代码规范吸收进 `rules/executor.md` · 已关闭（机制：执行器规则只来自仓库里的 `rules/executor.md`，和 Library 勾选无关）。
- 2026-10-27 · 本机抓包测试后服务进程没停 · `python3` 是 pyenv 的壳，`$!` 拿到的是壳的进程号，kill 它不会停掉真正的服务 · 服务进程自己把进程号写进文件，按文件里的号停 · 已关闭（机制：`agent-selftest`）。
- 2026-10-28 · 执行器没拿到会话号时，`dispatch.json` 的实际模型可能张冠李戴 · 按会话号查 `magpie usage`，会话号为空时会匹配上所有会话字段为空的用量行 · 会话号为空就不查 · 已关闭（机制：`agent-dispatch` 查用量前先判会话号非空）。
