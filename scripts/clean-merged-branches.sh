#!/usr/bin/env bash
# 清理已合入 master 的本地 feature 分支。
#
# 用法（仓库根目录）：
#   bash scripts/clean-merged-branches.sh            # 只列出，不删（预演）
#   bash scripts/clean-merged-branches.sh --apply    # 真的删
#
# 只删「已完全合入 master」且名字匹配白名单的分支——仓库里有些分支看着像
# feature 但另有用途，误删代价高于收益。要放开匹配范围改 PATTERNS。
set -euo pipefail

cd "$(dirname "$0")/.."

APPLY=0
if [ "${1:-}" = "--apply" ]; then
    APPLY=1
fi

# 只考虑这些前缀（bash 通配）
PATTERNS=("feat/practice-parsing-*" "feature/practice-parsing-*")
# 永不删除
PROTECT=("master" "main" "develop")

CURRENT=$(git rev-parse --abbrev-ref HEAD)

targets=()
while IFS= read -r raw; do
    name=$(echo "$raw" | sed 's/^[* ]*//' | xargs)
    [ -z "$name" ] && continue

    skip=0
    for p in "${PROTECT[@]}"; do
        [ "$name" = "$p" ] && skip=1
    done
    [ "$name" = "$CURRENT" ] && skip=1
    [ "$skip" -eq 1 ] && continue

    match=0
    for p in "${PATTERNS[@]}"; do
        # shellcheck disable=SC2053
        case "$name" in
            $p) match=1 ;;
        esac
    done
    [ "$match" -eq 1 ] && targets+=("$name")
done < <(git branch --merged master)

if [ "${#targets[@]}" -eq 0 ]; then
    echo "没有已合入 master 的可清理分支（当前在 $CURRENT）"
    exit 0
fi

echo "已合入 master 的候选分支："
for t in "${targets[@]}"; do
    echo "  - $t"
done

if [ "$APPLY" -ne 1 ]; then
    echo ""
    echo "这是预演。加 --apply 才会真的删除："
    echo "  bash scripts/clean-merged-branches.sh --apply"
    exit 0
fi

for t in "${targets[@]}"; do
    echo "删除 $t"
    # -d 只删已合并的；判断有误时 git 会拒绝，不会丢提交
    git branch -d "$t"
done

echo "完成。当前分支：$(git rev-parse --abbrev-ref HEAD)"
