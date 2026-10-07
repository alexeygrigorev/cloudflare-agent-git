# Sourced helper (not executable). The principal may override a guard with env
# PRINCIPAL_OVERRIDE=<reason> or a commit trailer `Principal-Override: <reason>`.
# principal_override <guard> [text-with-trailers]: prints and logs the reason, returns 0 if active.
principal_override() {
  _po_reason="${PRINCIPAL_OVERRIDE:-}"
  if [ -z "$_po_reason" ] && [ -n "$2" ]; then
    _po_reason=$(printf '%s\n' "$2" | sed -n 's/^Principal-Override:[[:space:]]*//p' | sed -n '1p')
  fi
  [ -n "$_po_reason" ] || return 1
  echo "$1: principal override used: $_po_reason" >&2
  _po_dir=$(git rev-parse --git-common-dir 2>/dev/null) &&
    echo "$(date -u +%FT%TZ) $1 $_po_reason" >>"$_po_dir/principal-override.log"
  return 0
}
