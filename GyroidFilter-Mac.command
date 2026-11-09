#!/bin/sh
# Gyroid Filter launcher (macOS). First time only: right-click this file > Open (it is not signed).
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Gyroid Filter needs Python 3.8 or newer, and it was not found."
  echo "Install it from https://www.python.org/downloads/ (or let macOS install the Command Line Tools"
  echo "if it offers to), then double-click this file again."
  printf "Press Enter to close. "; read _ignored
  exit 1
fi
PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m gyroid_filter "$@"
status=$?
if [ $status -ne 0 ]; then
  echo "Gyroid Filter stopped with an error (code $status)."
  printf "Press Enter to close. "; read _ignored
fi
exit $status
