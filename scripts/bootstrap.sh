#!/bin/sh
# scripts/bootstrap.sh
# Install the toolchain.json executables on a machine that has nothing yet.
#
#   sh scripts/bootstrap.sh              # into ~/.local/bin
#   sh scripts/bootstrap.sh /some/where  # into another directory
#
# POSIX sh, not bash: this runs before anything is installed, on whatever the
# machine happens to provide. Everything worth testing lives in
# scripts/bootstrap_toolchain.py, which imports only the standard library.
#
# A MISSING python3 IS REFUSED, NOT WORKED AROUND. Bootstrapping a Python
# without a Python belongs to the machine's administrators; a clear refusal is
# more useful than a clever failure. Every machine this project targets --
# macOS, FAS OnDemand, Lightning AI, GitHub runners -- ships one.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! command -v python3 > /dev/null 2>&1; then
  echo "refusing: python3 is required to bootstrap, and none is on PATH" >&2
  echo "install one through the machine's package manager, then run this again" >&2
  exit 1
fi

python3 "$script_dir/bootstrap_toolchain.py" "$@"

destination=${1:-$HOME/.local/bin}
case ":$PATH:" in
  *":$destination:"*) ;;
  *)
    echo
    echo "$destination is not on PATH. Add it for this shell with:"
    echo "  export PATH=\"$destination:\$PATH\""
    ;;
esac
