#!/bin/bash
# Thin VTune wrapper. Hardware collects re-exec under sudo when not root.
set -euo pipefail

find_vtune() {
  if command -v vtune >/dev/null 2>&1; then
    command -v vtune
    return
  fi
  local vars bin
  for vars in /opt/intel/oneapi/vtune/latest/vtune-vars.sh /opt/intel/oneapi/vtune/*/vtune-vars.sh; do
    [ -f "$vars" ] || continue
    # shellcheck disable=SC1090
    set +u
    # ponytail: vtune-vars.sh is Intel's env file and references unset vars
    . "$vars" >/dev/null
    set -u
    break
  done
  command -v vtune 2>/dev/null || true
}

bin=$(find_vtune || true)
if [ -z "${bin:-}" ]; then
  echo "vtune not installed. Run scripts/install_vtune.sh" >&2
  exit 1
fi

if [ "${1:-}" = "check" ]; then
  "$bin" --version
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n "$0" "$@"
fi
exec "$bin" "$@"
