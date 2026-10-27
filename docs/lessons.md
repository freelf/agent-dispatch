# 教训单

调度、脚本层面踩过的坑。格式：日期 · 现象 · 原因 · 改了什么。

- 2026-10-26 · 执行器第一次测试能提交，但 sandbox 本应拦住 · `~/.codex/rules/default.rules` 里有 `git commit` 放行规则，命中后命令在 sandbox 外执行 · Codex 执行器加 `--ignore-rules`；改用 Pi 后由自写的 sandbox-exec 规则控制写权限。
- 2026-10-26 · codex exec 后台运行卡住 · prompt 走参数且 stdin 不是终端时，codex 会等 stdin 的 EOF · 改为 prompt 走 stdin / stdin 接 /dev/null。
- 2026-10-26 · 执行器把 stderr 噪音当成命令失败而中止 · starship 写不了 `~/.cache` 日志往 stderr 报错 · 卡的执行规则写明以退出码判断成败。
- 2026-10-26 · 合并脚本 `unbound variable` · 变量名后紧跟全角括号被 shell 当成变量名的一部分 · 全角标点前的变量一律写成 `${var}`。
- 2026-10-26 · `git branch -d` 误报未合并 · 它对照主仓库当前 HEAD，不是对照 base · 自己用 `merge-base --is-ancestor` 确认后用 `-D`。
- 2026-10-26 · sandbox 越权测试"没拦住" · 测试仓库放在 /tmp，而临时目录本来就可写 · 隔离测试一律放在 /tmp 和 $TMPDIR 之外。
- 2026-10-26 · Pi 连不上网关却以 0 退出 · Pi 把 Connection error 记在最后一条回复的 stopReason 里 · agent-run 检查 stopReason，error/aborted/缺失都判失败。
- 2026-10-27 · 第一张真实卡（eve-debug-tools/pkg-ext-filter）：项目规则没进执行器的 prompt · 项目只有入库的 CLAUDE.md、没有 AGENTS.md，调度层只拼 AGENTS.md，Pi 又带 `--no-context-files` · 临时在卡正文写"先读 CLAUDE.md"；待定：没有 AGENTS.md 时退而拼 CLAUDE.md（注意 12KB 上限）。
- 2026-10-27 · 执行器在 sandbox 里无法编译和测试 · worktree 里没有被忽略的依赖目录（node_modules），sandbox 又禁网、禁写 home，装不了 · 主脑手动把主仓库的 node_modules 软链接进 worktree（确认被 .gitignore 覆盖），合并前删掉；待定：agent-worktree 按需链接依赖目录。
- 2026-10-27 · 一张 S 卡跑了 4 轮、记分 rounds=4 · 后 3 轮是用户中途补需求、主脑改结构，不是执行器失败，但只能走修复轮，且吃掉了全部修复轮次（修满后再要改就得先问 Advisor）· 记分 note 里写明原因；待定：区分"修复轮"和"补充需求轮"，或补充需求另开新卡。
- 2026-10-27 · 卡里写 `npx tsc` 会在 sandbox 里失败 · npx 要写 `~/.npm` 缓存 · 卡里写 `./node_modules/.bin/<工具>`。
- 2026-10-27 · 项目没声明门禁时，"自查说明"成了唯一的编译测试证据 · 门禁 SKIPPED 后要主脑自己跑 · 主脑每轮都在 worktree 里跑 tsc、单测、build，再用构建出的 CLI 做端到端打包；这比执行器自报多抓出了软链接被跳过这类行为变化。
- 2026-10-27 · 项目 AGENTS.md 拼进 prompt 会撑爆 12KB 上限 · eve 的 AGENTS.md 有 6KB，第一张卡修复轮 prompt 已到 6.5KB，两者相加超过 12288 · 改为 Pi 自己读项目规则（去掉 `--no-context-files`），调度层不再拼 AGENTS.md，去掉运行时 12KB 检查；`agent-run` 打印 `RUN: rules`。
