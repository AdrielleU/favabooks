"""The Docker scripts that create books: docker/new-books.sh, entrypoint.sh."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from beancount import loader

ROOT = Path(__file__).parent.parent
DOCKER = ROOT / "docker"

pytestmark = pytest.mark.skipif(
    shutil.which("sh") is None, reason="needs a POSIX shell"
)


def run(
    tmp_path: Path, script: str, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    """Run a script as in the image: favabooks-new on PATH, a fake fava."""
    bin_dir = tmp_path / "bin"
    if not bin_dir.exists():
        bin_dir.mkdir()
        (bin_dir / "favabooks-new").symlink_to(DOCKER / "new-books.sh")
        fava = bin_dir / "fava"
        fava.write_text('#!/bin/sh\necho "fava $*"\n')
        fava.chmod(0o755)
    environ = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAVABOOKS_STARTERS": str(ROOT),
        **env,
    }
    return subprocess.run(
        ["sh", str(DOCKER / script), *args],  # noqa: S607
        env=environ,
        capture_output=True,
        text=True,
        check=False,
    )


def title(main: Path) -> str:
    _, errors, options = loader.load_file(str(main))
    assert errors == []
    return str(options["title"])


def test_new_books(tmp_path: Path) -> None:
    books = tmp_path / "books"
    done = run(tmp_path, "new-books.sh", str(books / "second-llc"))
    assert done.returncode == 0, done.stderr
    assert 'business books "Second LLC"' in done.stdout
    assert title(books / "second-llc" / "main.beancount") == "Second LLC"

    done = run(tmp_path, "new-books.sh", str(books / "Family_Money"))
    assert "personal books" in done.stdout
    main = books / "Family_Money" / "main.beancount"
    assert title(main) == "Family Money"
    assert (
        "Expenses:Groceries"
        in (main.parent / "accounts.beancount").read_text()
    )

    done = run(
        tmp_path,
        "new-books.sh",
        str(books / "x" / "acme.beancount"),
        "business",
        'Acme "R&D" / Labs',
    )
    assert title(books / "x" / "acme.beancount") == "Acme R&D / Labs"
    assert not (books / "x" / "main.beancount").exists()

    done = run(tmp_path, "new-books.sh", str(books / "demo"), "demo")
    assert done.stdout == f"Created demo books in {books / 'demo'}.\n"
    assert title(books / "demo" / "main.beancount") == "Sample Studio LLC"

    done = run(tmp_path, "new-books.sh", str(tmp_path / "books"))
    assert title(books / "main.beancount") == "My Company LLC"
    done = run(
        tmp_path, "new-books.sh", str(tmp_path / "p" / "books"), "personal"
    )
    assert title(tmp_path / "p" / "books" / "main.beancount") == "Personal"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((), "usage:"),
        (("{t}/a", "shop"), "unknown kind 'shop'"),
        (("{t}/has-main",), "already exists; pick another folder"),
        (("{t}/has-accounts",), "already has accounts.beancount"),
        (("{t}/file/sub",), "can't write to {t}/file/sub"),
    ],
)
def test_new_books_errors(
    tmp_path: Path, args: tuple[str, ...], message: str
) -> None:
    (tmp_path / "has-main").mkdir()
    (tmp_path / "has-main" / "main.beancount").write_text("")
    (tmp_path / "has-accounts").mkdir()
    (tmp_path / "has-accounts" / "accounts.beancount").write_text("")
    (tmp_path / "file").write_text("")
    t = str(tmp_path)
    done = run(tmp_path, "new-books.sh", *(a.format(t=t) for a in args))
    assert done.returncode == 1
    assert message.format(t=t) in done.stderr


def test_new_books_missing_starters(tmp_path: Path) -> None:
    done = run(
        tmp_path,
        "new-books.sh",
        str(tmp_path / "a"),
        FAVABOOKS_STARTERS=str(tmp_path),
    )
    assert "the starter books aren't at" in done.stderr


def test_entrypoint_creates_every_company(tmp_path: Path) -> None:
    books = tmp_path / "books"
    ledgers = [
        books / "main.beancount",
        books / "second-llc" / "main.beancount",
        books / "personal" / "main.beancount",
    ]
    env = {
        "LEDGERS": " ".join(map(str, ledgers)),
        "FAVABOOKS_COMPANY": "Acme LLC",
    }
    done = run(tmp_path, "entrypoint.sh", **env)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines()[-1] == "fava " + env["LEDGERS"]
    assert [title(m) for m in ledgers] == [
        "Acme LLC",
        "Second LLC",
        "Personal",
    ]

    # A second start creates nothing and keeps the books.
    (books / "transactions.beancount").write_text("; mine\n")
    done = run(tmp_path, "entrypoint.sh", **env)
    assert done.stdout == "fava " + env["LEDGERS"] + "\n"
    assert (books / "transactions.beancount").read_text() == "; mine\n"


def test_entrypoint_demo_and_default(tmp_path: Path) -> None:
    books = tmp_path / "books"
    env = {
        "LEDGERS": f"{books}/main.beancount {books}/llc-two/main.beancount",
        "FAVABOOKS_STARTER": "demo",
    }
    done = run(tmp_path, "entrypoint.sh", **env)
    assert done.returncode == 0, done.stderr
    assert title(books / "main.beancount") == "Sample Studio LLC"
    assert title(books / "llc-two" / "main.beancount") == "LLC Two"


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"FAVABOOKS_STARTER": "empty"}, "use blank, demo or none"),
        ({"LEDGERS": "  "}, "LEDGERS is empty"),
        ({"LEDGERS": "{t}/books"}, "did you mean {t}/books/main.beancount"),
        ({"LEDGERS": "{t}/a.beancount {t}/a.beancount"}, "listed twice"),
        (
            {"LEDGERS": "{t}/a.beancount", "FAVABOOKS_STARTER": "none"},
            "no books at {t}/a.beancount",
        ),
        (
            {"LEDGERS": "{t}/a.beancount {t}/b.beancount"},
            "share the folder {t}; give each its own folder",
        ),
        (
            {"LEDGERS": "{t}/same.beancount {t}/x/main.beancount"},
            '{t}/same.beancount and {t}/x/main.beancount are both called "X"',
        ),
    ],
)
def test_entrypoint_errors(
    tmp_path: Path, env: dict[str, str], message: str
) -> None:
    (tmp_path / "same.beancount").write_text('option "title" "x"\n')
    t = str(tmp_path)
    done = run(
        tmp_path,
        "entrypoint.sh",
        **{k: v.format(t=t) for k, v in env.items()},
    )
    assert done.returncode == 1, done.stdout
    assert message.format(t=t) in done.stderr
    assert "fava" not in done.stdout
