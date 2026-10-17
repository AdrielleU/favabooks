#!/bin/sh
# Favabooks container start: create any missing books, then run Fava.
#
#   LEDGERS            space-separated main.beancount files, one per company
#                      (default: /books/main.beancount). Each one that doesn't
#                      exist yet is created on start, in its own folder.
#   FAVABOOKS_STARTER  what to create: "blank" (default: a business chart of
#                      accounts, or personal accounts for a folder named
#                      like personal, household or family), "demo" (the
#                      fictional Sample Studio LLC as the first company) or
#                      "none" (create nothing)
#   FAVABOOKS_COMPANY  name of the first company when it's created; the
#                      others are named after their folders
#                      (/books/second-llc -> "Second LLC")
set -eu

fail() {
  echo "favabooks: $*" >&2
  exit 1
}

LEDGERS="${LEDGERS:-/books/main.beancount}"
starter="${FAVABOOKS_STARTER:-blank}"
case "$starter" in
  blank | demo | none) ;;
  *) fail "FAVABOOKS_STARTER is '$starter'; use blank, demo or none" ;;
esac
[ -n "$(printf '%s' "$LEDGERS" | tr -d ' ')" ] || fail "LEDGERS is empty; list your main.beancount files"

# Check the list before creating anything: each company needs its own file
# and new books need their own folder.
seen=" "
new_dirs=" "
for ledger in $LEDGERS; do
  case "$ledger" in
    *.beancount) ;;
    *) fail "'$ledger' in LEDGERS isn't a .beancount file (did you mean $ledger/main.beancount?)" ;;
  esac
  case "$seen" in
    *" $ledger "*) fail "$ledger is listed twice in LEDGERS" ;;
  esac
  seen="$seen$ledger "
  if [ ! -e "$ledger" ]; then
    [ "$starter" = none ] && fail "no books at $ledger (and FAVABOOKS_STARTER=none). Create them or fix LEDGERS."
    dir=$(dirname "$ledger")
    case "$new_dirs" in
      *" $dir "*) fail "two new companies in LEDGERS share the folder $dir; give each its own folder, e.g. $dir/second-llc/main.beancount" ;;
    esac
    new_dirs="$new_dirs$dir "
  fi
done

first=1
for ledger in $LEDGERS; do
  if [ ! -e "$ledger" ]; then
    if [ "$first" = 1 ] && [ "$starter" = demo ]; then
      favabooks-new "$ledger" demo
    elif [ "$first" = 1 ] && [ -n "${FAVABOOKS_COMPANY:-}" ]; then
      favabooks-new "$ledger" auto "$FAVABOOKS_COMPANY"
    else
      favabooks-new "$ledger" auto
    fi
  fi
  first=0
done

# Two companies with the same name would get the same address in Fava.
titles=""
for ledger in $LEDGERS; do
  title=$(sed -n 's/^option "title" "\(.*\)"[[:space:]]*$/\1/p' "$ledger" | head -n 1)
  [ -n "$title" ] || continue
  key=$(printf '%s' "$title" | tr 'A-Z' 'a-z')
  other=$(printf '%s' "$titles" | awk -F '\t' -v k="$key" '$1 == k { print $2; exit }')
  [ -z "$other" ] || fail "$other and $ledger are both called \"$title\"; rename one (option \"title\" in the file)"
  titles="$titles$key	$ledger
"
done

# shellcheck disable=SC2086 # LEDGERS is a list of files
exec fava $LEDGERS
