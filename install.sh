#!/bin/sh
# 安装命令、dispatch Skill 和 common + brain 受管区块，保留已有其他指令。
# 默认 Claude；--client codex / all；--check 只检查是否同步，不写文件。
# AGENT_BIN_DIR / AGENT_SKILL_DIR 保留兼容（后者只用于单客户端）。
set -eu
root=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)
exec python3 -I "$root/scripts/install.py" "$@"
