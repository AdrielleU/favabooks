#!/bin/sh
# Package check: are our pinned packages current and free of known
# vulnerabilities? For the Upstream workflow, or by hand:
#
#   sh contrib/check_packages.sh [--ci] [REPORT] [GITHUB_OUTPUT]
#
#   - uv.lock matches pyproject.toml (it's what the Docker image installs)
#   - Python and npm updates past the 7-day wait `make update` uses
#   - known vulnerabilities: pip-audit on uv.lock, npm audit
#
# Writes a Markdown report (default: stdout) and appends
# action_needed=true|false to GITHUB_OUTPUT. Needs uv, npm and
# frontend/node_modules (`make frontend/node_modules`).
#
# --ci (CI on every push and pull request, so a package update is checked
# before it lands): skip the "updates due" part, which changes with every
# release elsewhere, and exit 1 on a stale uv.lock or a vulnerability.
set -u
ci=false
if [ "${1:-}" = --ci ]; then
  ci=true
  shift
fi
cd "$(dirname "$0")/.." || exit 1
report=${1:-/dev/stdout}
output=${2:-/dev/null}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
needed=false

{
  echo "## Packages"
  echo
  if uv lock --check >/dev/null 2>&1; then
    echo "- uv.lock matches pyproject.toml."
  else
    echo "- **uv.lock is out of date with pyproject.toml**: run \`uv lock\`."
    needed=true
  fi

  if [ "$ci" = true ]; then
    : # updates due: weekly, in the Upstream workflow
  elif ! uv lock --upgrade --dry-run >"$tmp/uv" 2>&1; then
    echo "- **Python check failed**: $(tail -1 "$tmp/uv")"
    needed=true
  elif grep '^Update' "$tmp/uv" >"$tmp/python"; then
    echo "- **Python updates** (run \`make update-constraints\`):"
    sed 's/^Update /  - /' "$tmp/python"
    needed=true
  else
    echo "- Python packages in uv.lock are up to date."
  fi

  if [ "$ci" = true ]; then
    :
  elif ! npm --prefix frontend update --dry-run --min-release-age 7 \
    >"$tmp/npm-update" 2>&1; then
    echo "- **npm check failed**:"
    echo
    echo '```'
    tail -5 "$tmp/npm-update"
    echo '```'
    needed=true
  elif grep -E '^(added|changed|removed) [0-9]+ package' "$tmp/npm-update" \
    >"$tmp/npm"; then
    echo "- **npm updates**: $(cat "$tmp/npm") (run \`make update-frontend-deps\`)."
    needed=true
  else
    echo "- npm packages are up to date."
  fi
  echo

  echo "### Known vulnerabilities"
  echo
  uv export --frozen --all-groups --all-extras --no-emit-project --quiet \
    --output-file "$tmp/requirements.txt"
  if uvx --quiet pip-audit==2.10.1 -r "$tmp/requirements.txt" \
    --require-hashes --disable-pip --progress-spinner off --format markdown \
    >"$tmp/pip-audit" 2>"$tmp/pip-audit.err"; then
    echo "- Python: none (pip-audit)."
  else
    echo "- **Python** (pip-audit):"
    echo
    cat "$tmp/pip-audit" "$tmp/pip-audit.err" | grep -v '^WARNING:'
    needed=true
  fi
  if npm --prefix frontend audit --audit-level=low >"$tmp/npm-audit" 2>&1; then
    echo "- npm: none (npm audit)."
  else
    echo "- **npm** (npm audit; \`npm audit fix\` in frontend/):"
    echo
    echo '```'
    cat "$tmp/npm-audit"
    echo '```'
    needed=true
  fi
} >"$report"

echo "action_needed=$needed" >>"$output"
if [ "$ci" = true ] && [ "$needed" = true ]; then
  exit 1
fi
