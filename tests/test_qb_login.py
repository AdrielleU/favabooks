"""docker-compose-login.yml: the official Caddy login in front of Favabooks."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
COMPOSE = (ROOT / "docker-compose-login.yml").read_text()
CADDYFILE = (ROOT / "docker" / "Caddyfile").read_text()
EXAMPLE = (ROOT / ".env.example").read_text()


def service(name: str) -> str:
    """The lines of one service in the compose file."""
    match = re.search(
        rf"^  {name}:\n((?:    .*\n|\s*\n)+)", COMPOSE, re.MULTILINE
    )
    assert match is not None, name
    return match[1]


def test_login_comes_from_env_and_is_required() -> None:
    login = service("favabooks-login")
    for name in ("FAVABOOKS_LOGIN_USER", "FAVABOOKS_LOGIN_HASH"):
        assert f"{name}: ${{{name}:?" in login
        assert f"{{${name}}}" in CADDYFILE
        assert re.search(rf"^{name}=", EXAMPLE, re.MULTILINE)


def test_caddy_is_official_and_gets_only_its_caddyfile() -> None:
    login = service("favabooks-login")
    assert "image: docker.io/library/caddy:" in login
    assert "entrypoint" not in login
    mounts = re.findall(
        r"^      - (\S+)$", login.split("volumes:")[1], re.MULTILINE
    )
    assert mounts[0] == "./docker/Caddyfile:/etc/caddy/Caddyfile:ro"
    assert "/books" not in login


def test_caddy_is_locked_down() -> None:
    login = service("favabooks-login")
    assert "read_only: true" in login
    assert "cap_drop: [ALL]" in login
    assert "cap_add: [NET_BIND_SERVICE]" in login
    assert '"no-new-privileges:true"' in login


def test_favabooks_itself_is_not_published() -> None:
    assert "ports:" not in service("favabooks")
