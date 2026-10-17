from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from fava import qb_inbox
from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient

IMPORT_LEDGER = Path(__file__).parent / "qb_data" / "import-ledger"
CSV = "Chase1234_Activity.csv"


@pytest.fixture
def books(tmp_path: Path) -> Path:
    """A copy of the import test ledger, with a documents folder."""
    books = tmp_path / "books"
    shutil.copytree(IMPORT_LEDGER, books)
    main = books / "main.beancount"
    main.write_text(main.read_text() + 'option "documents" "documents"\n')
    (books / "inbox" / ".gitkeep").write_text("")
    (books / "inbox" / "receipts").mkdir()
    (books / "inbox" / "receipts" / "adobe.pdf").write_text("%PDF")
    return books


def client(main: Path) -> FlaskClient:
    app = create_app([main], load=True)
    app.testing = True
    return app.test_client()


def get_inbox(main: Path) -> dict[str, object]:
    slug = "qb-import"
    response = client(main).get(f"/{slug}/api/qb_inbox")
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]  # type: ignore[no-any-return]


def test_inbox_endpoint(books: Path) -> None:
    data = get_inbox(books / "main.beancount")
    assert data == {
        "inbox": str(books / "inbox"),
        "relative": None,
        "docker": False,
        "files": [CSV, "receipts/adobe.pdf"],
        "file_count": 2,
        "documents": 0,
        "transactions": 0,
    }


def test_inbox_endpoint_in_docker(
    books: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAVABOOKS_DOCKER", "1")
    monkeypatch.setattr(qb_inbox, "DOCKER_BOOKS", books.parent)
    data = get_inbox(books / "main.beancount")
    assert data["relative"] == "books/books/inbox"
    assert data["inbox"] is None
    assert data["docker"] is True

    monkeypatch.setenv("FAVABOOKS_HOST_BOOKS", "/home/me/books/")
    assert get_inbox(books / "main.beancount")["inbox"] == (
        "/home/me/books/books/inbox"
    )


def test_inbox_endpoint_without_inbox(tmp_path: Path) -> None:
    main = tmp_path / "main.beancount"
    main.write_text('option "title" "QB Import"\n')
    data = get_inbox(main)
    assert data["inbox"] is None
    assert data["files"] == []
    assert data["file_count"] == 0


def test_host_path(monkeypatch: pytest.MonkeyPatch) -> None:
    inbox = Path("/books/second-llc/inbox")
    assert qb_inbox.host_path(inbox) == str(inbox)  # not in Docker
    monkeypatch.setenv("FAVABOOKS_DOCKER", "1")
    assert qb_inbox.host_path(inbox) is None  # unknown
    monkeypatch.setenv("FAVABOOKS_HOST_BOOKS", "/books")  # PWD was empty
    assert qb_inbox.host_path(inbox) is None
    monkeypatch.setenv("FAVABOOKS_HOST_BOOKS", "C:\\Users\\me\\books")
    assert (
        qb_inbox.host_path(inbox) == "C:\\Users\\me\\books\\second-llc\\inbox"
    )
    monkeypatch.setenv("FAVABOOKS_HOST_BOOKS", "/srv/books")
    assert qb_inbox.host_path(inbox) == "/srv/books/second-llc/inbox"
    assert qb_inbox.host_path(Path("/elsewhere/inbox")) is None


def test_inbox_files_missing_folder(tmp_path: Path) -> None:
    assert qb_inbox.inbox_files(None) == []
    assert qb_inbox.inbox_files(tmp_path / "nope") == []


def run(
    capsys: pytest.CaptureFixture[str], *args: str
) -> tuple[int, str, str]:
    code = qb_inbox.main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def test_cli_list(books: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, str(books / "main.beancount"))
    assert code == 0
    assert out.splitlines() == [
        str(books / "inbox" / CSV),
        (
            "  chase_checking:Assets:Bank:Chase: Assets:Bank:Chase, files as "
            f"'2026-10-14 {CSV}'"
        ),
        str(books / "inbox" / "receipts" / "adobe.pdf"),
        (
            "  no importer: a CSV needs its bank connected in Favabooks "
            "(Bank & card accounts); book anything else by hand and file it "
            "in documents/"
        ),
    ]

    shutil.rmtree(books / "inbox")
    (books / "inbox").mkdir()
    code, out, _ = run(capsys, str(books / "main.beancount"))
    assert out == f"The inbox is empty: {books / 'inbox'}\n"


def test_cli_errors(
    books: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = str(books / "main.beancount")
    code, _, err = run(capsys, str(tmp_path / "nope.beancount"))
    assert code == 1
    assert "nope.beancount isn't a file" in err

    no_inbox = tmp_path / "plain.beancount"
    no_inbox.write_text("")
    _, _, err = run(capsys, str(no_inbox))
    assert "the books have no inbox" in err

    csv = str(books / "inbox" / CSV)
    _, _, err = run(capsys, str(books / "missing-config.beancount"), csv)
    assert "Import config does not exist" in err

    _, _, err = run(capsys, main, str(books / "inbox"))
    assert "inbox isn't a file" in err

    pdf = str(books / "inbox" / "receipts" / "adobe.pdf")
    _, _, err = run(capsys, main, pdf)
    assert "no importer reads adobe.pdf; connect the account" in err

    _, _, err = run(capsys, main, csv, "--importer", "stripe")
    assert f"no importer reads {CSV} as stripe;" in err


def test_cli_without_import_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = tmp_path / "main.beancount"
    main.write_text('2020-01-01 custom "fava-option" "import-dirs" "inbox"\n')
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox" / "a.csv").write_text("")
    _, out, _ = run(capsys, str(main))
    assert "no importer" in out


def test_cli_import(books: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main = str(books / "main.beancount")
    csv = books / "inbox" / CSV
    saved = csv.read_text()

    code, out, err = run(capsys, main, str(csv))
    assert code == 0
    assert '2026-10-01 ! "MESA PROPERTIES RENT"' in out
    assert err == f"3 new entries from {CSV}\n"
    assert csv.exists()

    code, out, err = run(capsys, main, str(csv), "--save")
    assert code == 0
    filed = (
        books / "documents" / "Assets" / "Bank" / "Chase" / f"2026-10-14 {CSV}"
    )
    assert err.splitlines() == [
        f"3 new entries from {CSV}",
        "Added 3 entries.",
        f"Filed {CSV} as {filed}.",
    ]
    assert not csv.exists()
    assert filed.exists()
    assert "MESA PROPERTIES RENT" in (books / "main.beancount").read_text()

    # The same file again: already booked, and already filed.
    csv.write_text(saved)
    code, out, err = run(capsys, main, str(csv), "--save")
    assert "0 new entries from" in err
    assert "(3 already in the books, skipped)" in err
    assert "Nothing new to add." in err
    assert f"Left {csv} in place: {filed} already exists." in err


def test_cli_import_without_documents_folder(
    books: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = books / "main.beancount"
    main.write_text(main.read_text().replace('option "documents"', ";"))
    csv = books / "inbox" / CSV
    _, _, err = run(capsys, str(main), str(csv), "--save")
    assert f"Left {csv} in place: the books have no documents folder." in err


def test_cli_import_closed_books(
    books: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = books / "main.beancount"
    main.write_text(
        main.read_text() + '2026-10-05 custom "closed-books" "x"\n'
    )
    csv = str(books / "inbox" / CSV)
    code, _, err = run(capsys, str(main), csv)
    assert code == 0
    assert "Warning: 1 entries are dated on or before 2026-10-05" in err
    code, _, err = run(capsys, str(main), csv, "--save")
    assert code == 1
    assert "Error: 1 entries are dated on or before 2026-10-05" in err
    assert "MESA" not in main.read_text()


def test_cli_several_importers(
    books: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = books / "config.py"
    config.write_text(
        config.read_text().replace(
            "    Other(),",
            '    Other(),\n    BankCSV("chase_checking", "Assets:Stripe"),',
        )
    )
    csv = str(books / "inbox" / CSV)
    _, _, err = run(capsys, str(books / "main.beancount"), csv)
    assert "several importers read" in err
    assert "pick one with --importer" in err
    code, _, err = run(
        capsys,
        str(books / "main.beancount"),
        csv,
        "--importer",
        "chase_checking:Assets:Stripe",
    )
    assert code == 0
    assert "4 new entries" in err  # no Stripe transfers to skip


def test_cli_keeps_dated_names(
    books: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv = books / "inbox" / CSV
    csv.rename(books / "inbox" / "2026-10-20 chase.csv")
    _, out, _ = run(capsys, str(books / "main.beancount"))
    assert "files as '2026-10-20 chase.csv'" in out


def test_cli_runs_as_a_module(books: Path) -> None:
    """`python -m fava.qb_inbox` in a fresh interpreter (import order)."""
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "fava.qb_inbox",
            str(books / "main.beancount"),
            str(books / "inbox" / CSV),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "MESA PROPERTIES RENT" in done.stdout
