# 教训单

调度、脚本层面踩过的坑。格式：日期 · 现象 · 原因 · 改了什么。

- 2026-10-26 · 执行器第一次测试能提交，但 sandbox 本应拦住 · `~/.codex/rules/default.rules` 里有 `git commit` 放行规则，命中后命令在 sandbox 外执行 · Codex 执行器加 `--ignore-rules`；改用 Pi 后由自写的 sandbox-exec 规则控制写权限。
- 2026-10-26 · codex exec 后台运行卡住 · prompt 走参数且 stdin 不是终端时，codex 会等 stdin 的 EOF · 改为 prompt 走 stdin / stdin 接 /dev/null。
- 2026-10-26 · 执行器把 stderr 噪音当成命令失败而中止 · starship 写不了 `~/.cache` 日志往 stderr 报错 · 卡的执行规则写明以退出码判断成败。
- 2026-10-26 · 合并脚本 `unbound variable` · 变量名后紧跟全角括号被 shell 当成变量名的一部分 · 全角标点前的变量一律写成 `${var}`。
- 2026-10-26 · `git branch -d` 误报未合并 · 它对照主仓库当前 HEAD，不是对照 base · 自己用 `merge-base --is-ancestor` 确认后用 `-D`。
- 2026-10-26 · sandbox 越权测试"没拦住" · 测试仓库放在 /tmp，而临时目录本来就可写 · 隔离测试一律放在 /tmp 和 $TMPDIR 之外。
- 2026-10-26 · Pi 连不上网关却以 0 退出 · Pi 把 Connection error 记在最后一条回复的 stopReason 里 · agent-run 检查 stopReason，error/aborted/缺失都判失败。
