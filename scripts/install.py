#!/usr/bin/env python3
"""Install links and a managed common + brain block without replacing user rules."""
import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BEGIN = "<!-- agent-dispatch:begin -->"
END = "<!-- agent-dispatch:end -->"
LIMIT = 24 * 1024


def render(old, body):
    block = f"{BEGIN}\n{body}{END}\n"
    if BEGIN not in old and END not in old:
        return old + ("\n\n" if old and not old.endswith("\n") else "\n" if old else "") + block
    pattern = re.compile(r"^" + re.escape(BEGIN) + r"\n.*?^" + re.escape(END) + r"(?:\n|$)", re.M | re.S)
    if old.count(BEGIN) != 1 or old.count(END) != 1 or not pattern.search(old):
        raise ValueError("受管区块标记缺失、重复或格式不正确，请先修复；未覆盖文件")
    return pattern.sub(lambda _: block, old, count=1)


def write_rules(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        fd, backup = tempfile.mkstemp(prefix=path.name + ".bak-agent-dispatch-", dir=path.parent)
        os.close(fd)
        shutil.copy2(path, backup)
        print(f"INSTALL: backup {backup}")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
            out.write(content)
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("claude", "codex", "all"), default="claude")
    parser.add_argument("--check", action="store_true", help="只检查同步状态，不写文件；过期返回 1")
    parser.add_argument("--claude-dir", type=Path, default=Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")))
    parser.add_argument("--codex-dir", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--codex-skills-dir", type=Path, default=Path.home() / ".agents/skills")
    args = parser.parse_args()
    if args.client == "all" and os.environ.get("AGENT_SKILL_DIR"):
        raise ValueError("AGENT_SKILL_DIR 只用于单客户端安装，--client all 请使用客户端目录参数")
    clients = ("claude", "codex") if args.client == "all" else (args.client,)
    body = "\n\n".join((ROOT / "rules" / name).read_text(encoding="utf-8").rstrip() for name in ("common.md", "brain.md")) + "\n"
    if len(body.encode("utf-8")) > LIMIT:
        raise ValueError(f"主脑规则超过上限 {LIMIT} 字节")
    rules = []
    links = [(src, Path(os.environ.get("AGENT_BIN_DIR", Path.home() / ".local/bin")) / src.name) for src in sorted((ROOT / "bin").iterdir()) if src.is_file()]
    for client in clients:
        directory = args.claude_dir if client == "claude" else args.codex_dir
        target = directory / ("CLAUDE.md" if client == "claude" else "AGENTS.md")
        override = directory / "AGENTS.override.md"
        if client == "codex" and override.exists() and override.read_text(encoding="utf-8").strip():
            raise ValueError(f"{override} 会遮蔽 AGENTS.md，请先整合其中规则；未修改该文件")
        if target.is_symlink():
            raise ValueError(f"{target} 是软链接，请指定真实配置目录；未替换链接")
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        new = render(old, body)
        if len(new.encode("utf-8")) > LIMIT:
            raise ValueError(f"{target} 含保留内容共 {len(new.encode('utf-8'))} 字节，超过上限 {LIMIT}")
        rules.append((target, old, new))
        default_skills = args.claude_dir / "skills" if client == "claude" else args.codex_skills_dir
        skill_dir = Path(os.environ.get("AGENT_SKILL_DIR", default_skills))
        links.extend((src, skill_dir / src.name) for src in sorted((ROOT / "skills").iterdir()) if src.is_dir())
    # 所有目标先检查；目标冲突时不先安装一部分。
    for src, dst in links:
        if dst.exists() and not dst.is_symlink():
            raise ValueError(f"{dst} 已存在且不是软链接；未覆盖")
    stale = []
    for target, old, new in rules:
        if old != new:
            stale.append(str(target))
            if not args.check:
                write_rules(target, new)
        print(f"{'CHECK' if args.check else 'INSTALL'}: {target} ({len(new.encode('utf-8'))} bytes)")
    for src, dst in links:
        if dst.is_symlink() and dst.resolve() == src.resolve():
            continue
        stale.append(str(dst))
        if not args.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_symlink():
                dst.unlink()
            dst.symlink_to(src)
            print(f"INSTALL: {dst} -> {src}")
    if args.check and stale:
        print("CHECK STALE: 请重新运行 install.sh 同步：\n" + "\n".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"INSTALL ERROR: {error}", file=sys.stderr)
        sys.exit(2)
