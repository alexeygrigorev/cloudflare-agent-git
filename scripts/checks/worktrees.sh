#!/bin/sh
# Worktree and branch health report. Report only: exit 0 unless --strict and findings exist.
strict=0
[ "$1" = "--strict" ] && strict=1
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
findings=0
note() { echo "worktrees: $*"; findings=$((findings + 1)); }

base=origin/main
git rev-parse --verify -q "$base" >/dev/null || base=main
main_top=$(git worktree list --porcelain | sed -n '1s/^worktree //p')

path=""; branch=""; prunable=0
check() {
  [ -n "$path" ] || return
  if [ "$path" != "$main_top" ]; then
    if [ "$prunable" = 1 ] || [ ! -d "$path" ]; then
      note "stale (directory missing, prune it): $path"
    else
      case "$branch" in
        "") note "detached worktree: $path" ;;
        refs/heads/history) ;;
        refs/heads/main) note "worktree on main: $path" ;;
        *) note "worktree on branch ${branch#refs/heads/}: $path" ;;
      esac
    fi
  fi
}
for line in $(git worktree list --porcelain | tr ' ' '\037') ""; do
  line=$(printf '%s' "$line" | tr '\037' ' ')
  case "$line" in
    "worktree "*) check; path=${line#worktree }; branch=""; prunable=0 ;;
    "branch "*) branch=${line#branch } ;;
    prunable*) prunable=1 ;;
    "") ;;
  esac
done
check

for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do
  case "$b" in main|history) continue ;; esac
  if git merge-base --is-ancestor "$b" "$base" 2>/dev/null; then
    note "local branch merged into $base (safe to delete): $b"
  else
    note "local branch with unmerged work (keep, find its owner): $b"
  fi
done

[ "$findings" = 0 ] && echo "worktrees: clean"
[ "$strict" = 1 ] && [ "$findings" -gt 0 ] && exit 1
exit 0
