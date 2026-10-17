#!/bin/sh
# Start Caddy with the Favabooks login (docker-compose-login.yml).
#
#   login.sh ENV_FILE CADDYFILE
#
# The login is FAVABOOKS_LOGIN_USER and FAVABOOKS_LOGIN_HASH (a bcrypt hash
# from `caddy hash-password`) in ENV_FILE, the .env next to the compose
# file. If there's no hash yet (first start: no .env, an empty one, or no
# hash line), this makes a random password, saves its hash and the
# username (admin unless set) to ENV_FILE, keeping its other lines, and
# prints the password once. Lost it? Delete the two lines from .env and
# restart: a new one is made.
set -eu

env_file=$1
caddyfile=$2

# The value of NAME in ENV_FILE, without quotes around it.
value() {
  [ -f "$env_file" ] || return 0
  sed -n "s/^$1=//p" "$env_file" | tail -n 1 |
    sed -e "s/^'\(.*\)'\$/\1/" -e 's/^"\(.*\)"$/\1/'
}

user=$(value FAVABOOKS_LOGIN_USER)
hash=$(value FAVABOOKS_LOGIN_HASH)
user=${user:-admin}

if [ -z "$hash" ]; then
  password=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)
  hash=$(caddy hash-password --plaintext "$password")
  tmp="$env_file.tmp"
  (
    umask 077 # only its owner can read the hash
    {
      if [ -f "$env_file" ]; then
        grep -v -e '^FAVABOOKS_LOGIN_USER=' -e '^FAVABOOKS_LOGIN_HASH=' \
          "$env_file" || true
      fi
      echo "FAVABOOKS_LOGIN_USER=$user"
      echo "FAVABOOKS_LOGIN_HASH='$hash'"
    } >"$tmp"
  )
  # Owned like the folder it's in, not by the container's root.
  chown "$(stat -c %u:%g "$(dirname "$env_file")")" "$tmp" 2>/dev/null || true
  mv "$tmp" "$env_file"
  cat <<EOF
==================================================================
 Favabooks login, made on first start. Save the password now: only
 its hash is kept (in .env), so it isn't shown again.

   Username: $user
   Password: $password

 To change it: delete the FAVABOOKS_LOGIN_ lines from .env and
 restart (docker compose up -d) for a new random one, or put your
 own hash there (caddy hash-password).
==================================================================
EOF
fi

export FAVABOOKS_LOGIN_USER="$user" FAVABOOKS_LOGIN_HASH="$hash"
exec caddy run --config "$caddyfile" --adapter caddyfile
