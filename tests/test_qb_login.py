"""docker/login.sh: the login in front of Favabooks (Caddy)."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

LOGIN = Path(__file__).parent.parent / "docker" / "login.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("sh") is None, reason="needs a POSIX shell"
)

#: Stands in for caddy: the "hash" holds the password, and "run" prints the
#: login it was started with.
FAKE_CADDY = """#!/bin/sh
if [ "$1" = hash-password ]; then
  echo "\\$2a\\$14\\$hash-of-$3"
else
  echo "caddy $* user=$FAVABOOKS_LOGIN_USER hash=$FAVABOOKS_LOGIN_HASH"
fi
"""


def run(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    if not bin_dir.exists():
        bin_dir.mkdir()
        caddy = bin_dir / "caddy"
        caddy.write_text(FAKE_CADDY)
        caddy.chmod(0o755)
    return subprocess.run(
        ["sh", str(LOGIN), str(tmp_path / ".env"), "/etc/caddy/Caddyfile"],  # noqa: S607
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_first_start_makes_a_login(tmp_path: Path) -> None:
    done = run(tmp_path)
    assert done.returncode == 0, done.stderr
    password = re.search(r"Password: (\S+)", done.stdout)
    assert password is not None
    assert re.fullmatch(r"[A-Za-z0-9]{20}", password[1])
    assert "Username: admin" in done.stdout
    env = tmp_path / ".env"
    assert env.read_text() == (
        "FAVABOOKS_LOGIN_USER=admin\n"
        f"FAVABOOKS_LOGIN_HASH='$2a$14$hash-of-{password[1]}'\n"
    )
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert done.stdout.splitlines()[-1] == (
        "caddy run --config /etc/caddy/Caddyfile --adapter caddyfile "
        f"user=admin hash=$2a$14$hash-of-{password[1]}"
    )

    # Started again: the same login, nothing printed.
    again = run(tmp_path)
    assert "Password" not in again.stdout
    assert again.stdout.splitlines() == done.stdout.splitlines()[-1:]


def test_keeps_the_rest_of_env(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('FAVABOOKS_PORT=17201\nFAVABOOKS_LOGIN_USER="owner"\n')
    done = run(tmp_path)
    assert "Username: owner" in done.stdout
    lines = env.read_text().splitlines()
    assert lines[:2] == ["FAVABOOKS_PORT=17201", "FAVABOOKS_LOGIN_USER=owner"]
    assert lines[2].startswith("FAVABOOKS_LOGIN_HASH='$2a$14$hash-of-")


def test_empty_env(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("")
    done = run(tmp_path)
    assert "Username: admin" in done.stdout


def test_existing_login(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    text = "FAVABOOKS_LOGIN_USER=me\nFAVABOOKS_LOGIN_HASH='$2a$14$mine'\n"
    env.write_text(text)
    done = run(tmp_path)
    assert done.stdout == (
        "caddy run --config /etc/caddy/Caddyfile --adapter caddyfile "
        "user=me hash=$2a$14$mine\n"
    )
    assert env.read_text() == text
