#!/usr/bin/env bash
# install-hooks.sh — 把 githooks/ 里的 hook 安装到 .git/hooks/
#
# 用法：./githooks/install-hooks.sh
# 效果：githooks/pre-commit → .git/hooks/pre-commit（可执行）

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_SRC="$REPO_ROOT/githooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_SRC" ]; then
    echo "❌ 无 githooks/ 目录: $HOOKS_SRC"
    exit 1
fi

for hook in "$HOOKS_SRC"/*; do
    name="$(basename "$hook")"
    dst="$HOOKS_DST/$name"
    cp "$hook" "$dst"
    chmod +x "$dst"
    echo "✅ 安装: $dst"
done

echo ""
echo "下一步：新机器 clone 后跑一次 ./githooks/install-hooks.sh 即可"