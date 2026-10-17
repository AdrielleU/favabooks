#!/bin/sh
# Favabooks container start: create the books on first run, then run Fava.
#
#   LEDGERS            space-separated main.beancount files (default:
#                      /books/main.beancount)
#   FAVABOOKS_STARTER  what to create when the first ledger doesn't exist:
#                      "blank" (default: a starter chart of accounts),
#                      "demo" (the fictional Sample Studio LLC) or "none"
#   FAVABOOKS_COMPANY  company name for a blank starter
set -eu

LEDGERS="${LEDGERS:-/books/main.beancount}"
first="${LEDGERS%% *}"

if [ ! -e "$first" ]; then
  dir="$(dirname "$first")"
  case "${FAVABOOKS_STARTER:-blank}" in
    blank) source=/opt/favabooks/ledger-starter ;;
    demo) source=/opt/favabooks/ledger-template ;;
    *)
      echo "No ledger at $first (and FAVABOOKS_STARTER=none)." >&2
      exit 1
      ;;
  esac
  if ! mkdir -p "$dir" 2>/dev/null || [ ! -w "$dir" ]; then
    echo "Can't write to $dir. Create the books folder first and give it to" >&2
    echo "user id $(id -u), e.g.: mkdir books && sudo chown $(id -u) books" >&2
    exit 1
  fi
  cp -R "$source"/. "$dir"/
  if [ "$(basename "$first")" != main.beancount ]; then
    mv "$dir/main.beancount" "$first"
  fi
  if [ "${FAVABOOKS_STARTER:-blank}" = blank ] && [ -n "${FAVABOOKS_COMPANY:-}" ]; then
    # Quotes and backslashes can't go in a Beancount string; / and & are
    # special to sed.
    escaped="$(printf '%s' "$FAVABOOKS_COMPANY" | tr -d '"\\' | sed 's/[\/&]/\\&/g')"
    sed -i "s/\"My Company LLC\"/\"$escaped\"/" "$first"
  fi
  echo "Created new books in $dir (${FAVABOOKS_STARTER:-blank})."
fi

# shellcheck disable=SC2086 # LEDGERS is a list of files
exec fava $LEDGERS
