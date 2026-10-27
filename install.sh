#!/bin/sh
# 安装：bin/ 下的命令软链接到 ~/.local/bin（AGENT_BIN_DIR 可覆盖），
#       skills/ 下的每个 Skill 软链接到 ~/.claude/skills（AGENT_SKILL_DIR 可覆盖）。可重复执行。
# 目标位置已有同名的非软链接文件或目录时报错退出，不覆盖。
set -eu

root=$(cd "$(dirname "$0")" && pwd -P)
bin_dir=${AGENT_BIN_DIR:-$HOME/.local/bin}
skill_dir=${AGENT_SKILL_DIR:-$HOME/.claude/skills}
mkdir -p "$bin_dir" "$skill_dir"

link() {
    if [ -e "$2" ] && [ ! -L "$2" ]; then
        echo "INSTALL ERROR: $2 已存在且不是软链接" >&2
        exit 2
    fi
    ln -sfn "$1" "$2"
    echo "INSTALL: $2 -> $1"
}

for src in "$root"/bin/*; do
    link "$src" "$bin_dir/$(basename "$src")"
done
for src in "$root"/skills/*/; do
    src=${src%/}
    link "$src" "$skill_dir/$(basename "$src")"
done
