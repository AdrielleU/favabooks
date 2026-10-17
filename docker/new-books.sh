#!/bin/sh
# Create new Favabooks books for a company (or personal money).
#
#   new-books.sh FOLDER [KIND] [NAME]
#
#   FOLDER  where the books go; FOLDER/main.beancount is created. A path
#           ending in .beancount names the main file instead.
#   KIND    business (a small-business chart of accounts), personal
#           (household money), demo (the fictional Sample Studio LLC) or
#           auto (the default: personal if the folder is named like
#           personal, household or family, business otherwise)
#   NAME    the title shown in Favabooks; default: from the folder name,
#           e.g. second-llc -> "Second LLC"
#
# Examples (in Docker the script is called favabooks-new):
#   new-books.sh ~/books/second-llc
#   new-books.sh ~/books/personal personal "Our household"
#
# It never overwrites anything: it stops with an error if the folder
# already has books in it.
set -eu

fail() {
  echo "new-books: $*" >&2
  exit 1
}

[ $# -ge 1 ] && [ $# -le 3 ] || fail "usage: new-books.sh FOLDER [business|personal|demo|auto] [NAME]"
target=$1
kind=${2:-auto}
name=${3:-}

case "$target" in
  *.beancount) main=$target ;;
  *) main="${target%/}/main.beancount" ;;
esac
dir=$(dirname "$main")
folder=$(basename "$dir")

# The starters: next to this script in a source checkout, /opt/favabooks in
# the Docker image.
if [ -z "${FAVABOOKS_STARTERS:-}" ]; then
  FAVABOOKS_STARTERS=$(cd "$(dirname "$0")/.." && pwd)
  [ -d "$FAVABOOKS_STARTERS/ledger-starter" ] || FAVABOOKS_STARTERS=/opt/favabooks
fi

if [ "$kind" = auto ]; then
  case "$(printf '%s' "$folder" | tr 'A-Z' 'a-z')" in
    *personal* | *household* | *family*) kind=personal ;;
    *) kind=business ;;
  esac
fi
case "$kind" in
  business) source="$FAVABOOKS_STARTERS/ledger-starter" ;;
  personal) source="$FAVABOOKS_STARTERS/ledger-personal" ;;
  demo) source="$FAVABOOKS_STARTERS/ledger-template" ;;
  *) fail "unknown kind '$kind': use business, personal, demo or auto" ;;
esac
[ -d "$source" ] || fail "the starter books aren't at $source"

[ -e "$main" ] && fail "$main already exists; pick another folder for new books"
for item in "$source"/*; do
  if [ -e "$dir/$(basename "$item")" ]; then
    fail "$dir already has $(basename "$item"); new books need their own (empty) folder"
  fi
done
if ! mkdir -p "$dir" 2>/dev/null || [ ! -w "$dir" ]; then
  fail "can't write to $dir. Create it first and give it to user id $(id -u), e.g.: mkdir -p $dir && sudo chown $(id -u) $dir"
fi

# A title from the folder name: second-llc -> Second LLC.
if [ -z "$name" ] && [ "$kind" != demo ]; then
  case "$folder" in
    books | . | /) [ "$kind" = personal ] && name=Personal || name="My Company LLC" ;;
    *)
      name=$(printf '%s' "$folder" | tr '_-' '  ' | awk '{
        for (i = 1; i <= NF; i++) {
          w = tolower($i)
          if (w ~ /^(llc|pllc|llp|lp|inc|ltd|dba)$/) $i = toupper(w)
          else $i = toupper(substr(w, 1, 1)) substr(w, 2)
        }
        print
      }')
      ;;
  esac
fi

cp -R "$source"/. "$dir"/
if [ "$(basename "$main")" != main.beancount ]; then
  mv "$dir/main.beancount" "$main"
fi
if [ -n "$name" ]; then
  # Quotes and backslashes can't go in a Beancount string; / and & are
  # special to sed.
  clean=$(printf '%s' "$name" | tr -d '"\\')
  escaped=$(printf '%s' "$clean" | sed 's/[\/&]/\\&/g')
  # (No sed -i: it differs between GNU and macOS.)
  sed "s/^option \"title\" \".*\"\$/option \"title\" \"$escaped\"/" "$main" >"$main.tmp"
  mv "$main.tmp" "$main"
  echo "Created $kind books \"$clean\" in $dir."
else
  echo "Created $kind books in $dir."
fi
