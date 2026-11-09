#!/bin/sh
# Gyroid Filter launcher (Linux). Double-click it and choose "Run" (or "Run in Terminal").
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
cd "$(dirname "$0")" || exit 1

# No terminal attached (started by double-click)? Reopen inside one so messages stay visible.
if [ ! -t 1 ] && [ -z "$GYROID_IN_TERM" ]; then
  for t in x-terminal-emulator gnome-terminal konsole xfce4-terminal mate-terminal xterm; do
    if command -v "$t" >/dev/null 2>&1; then
      export GYROID_IN_TERM=1
      case "$t" in
        gnome-terminal|mate-terminal) exec "$t" -- sh "$0" "$@" ;;
        *) exec "$t" -e sh "$0" "$@" ;;
      esac
    fi
  done
fi

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Gyroid Filter needs Python 3.8 or newer, and it was not found."
  echo "Install it, then run this file again:"
  echo "  Linux Mint / Ubuntu / Debian:  sudo apt install python3"
  echo "  Fedora / Bazzite:              sudo dnf install python3   (Bazzite already has it)"
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
