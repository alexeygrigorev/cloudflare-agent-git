#!/bin/bash
# Repo hygiene: where files may live. Looks only at paths ADDED (or renamed to) in the scope, so
# legacy files never block; `--all` audits every tracked file. Never reads document text.
# Scope comes from run-all.sh (CHECK_MODE, CHECK_RANGE) or defaults to the staged diff.
# Override: PRINCIPAL_OVERRIDE=<reason> (exported by run-all.sh; also honoured when run directly).
set -u
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
. scripts/checks/lib.sh
. scripts/checks/lib/principal-override.sh
check_parse_args "$@"

# Root files that may be added. Everything else belongs in a directory.
ROOT_ALLOW=" AGENTS.md README.md LICENSE .gitignore "
# Directories whose docs are not repo documentation. Each needs a reason.
DOC_EXEMPT=(
  "website/"      # the published site: page content and templates
  ".agents/"      # agent skill definitions (SKILL.md and references)
  ".claude/"      # agent tool configuration
  ".github/"      # issue and PR templates
  "tests/"        # test fixtures
)
# Where a dated file name is legitimate.
DATED_OK=(
  "_docs/founder-journal/"   # one YYYY-MM-DD.md per day
  "website/content/daily/"   # the one daily report per day
  "tests/"                   # fixtures
)

has_prefix() { local p=$1; shift; for d in "$@"; do [[ $p == "$d"* ]] && return 0; done; return 1; }

bad=0
report() { echo "hygiene: $1: $2"; bad=1; }

while IFS= read -r path; do
  [ -n "$path" ] || continue
  base=${path##*/}
  lower=$(printf '%s' "$base" | tr 'A-Z' 'a-z')
  stem=${lower%.*}

  if [[ $path != */* ]] && [[ $ROOT_ALLOW != *" $path "* ]]; then
    report "$path" "new file at repo root; put it in a directory (root allows only${ROOT_ALLOW% })"
  fi

  if [[ $path != website/* ]]; then
    case "$stem" in
      brief|brief-*|index|submission|submission-*) [[ $lower == *.md ]] && report "$path" "BRIEF/INDEX/SUBMISSION documents are not used" ;;
    esac
  fi
  [[ $lower == claude.md ]] && report "$path" "no CLAUDE.md; AGENTS.md is the single agent-instruction file"

  case "$lower" in
    *.md|*.rst|*.adoc)
      if ! has_prefix "$path" "${DOC_EXEMPT[@]}"; then
        if [[ $path != _docs/* && $path != AGENTS.md && $path != README.md && $base != README.md ]]; then
          report "$path" "documents live under _docs/ (only AGENTS.md and README.md may sit elsewhere)"
        fi
      fi
      if [[ $path == _docs/* ]] && ! [[ $base =~ ^[a-z0-9][a-z0-9._-]*$ ]]; then
        report "$path" "doc names are lowercase kebab-case"
      fi
      if [[ $path != _docs/* ]] && ! has_prefix "$path" "${DOC_EXEMPT[@]}" && [[ $base != "$lower" && $path != AGENTS.md && $path != README.md && $base != README.md ]]; then
        report "$path" "uppercase document name"
      fi ;;
  esac

  case "$lower" in
    *worklog*|*integration-log*|*.log|*.jsonl|*telemetry*)
      has_prefix "$path" "tests/" || report "$path" "no committed work logs, telemetry, logs or jsonl (keep them in git-ignored .local/)" ;;
  esac

  case "$lower" in
    *.md|*.txt|*.json|*.jsonl|*.log|*.csv)
      if [[ $base =~ (^|[^0-9])(20[0-9]{2}-?[0-9]{2}-?[0-9]{2})([^0-9]|$) ]] && ! has_prefix "$path" "${DATED_OK[@]}"; then
        report "$path" "dated report file; update the one living document instead"
      fi ;;
  esac
done < <(check_added_files)

if [ $bad -eq 1 ] && principal_override hygiene "${PRINCIPAL_OVERRIDE:+Principal-Override: $PRINCIPAL_OVERRIDE}"; then
  exit 0
fi
exit $bad
