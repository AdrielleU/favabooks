"""The inbox: files waiting to be imported (qb-fork).

- `get_qb_inbox` is what the "Add your files" popup shows: the inbox folder
  as the user's computer sees it, the files waiting there, and whether the
  books have any documents yet.
- The command line imports with the same importers as the Import page, for
  AI assistants or scripts:

      python -m fava.qb_inbox main.beancount              # files waiting
      python -m fava.qb_inbox main.beancount FILE         # entries FILE adds
      python -m fava.qb_inbox main.beancount FILE --save  # add them, file FILE

  Entries already in the books are skipped, and --save refuses entries in a
  closed period. Saved files move to documents/<account>/, like Save on the
  Import page.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from msgspec import Struct

from fava.context import g
from fava.core import FavaLedger
from fava.core.documents import filepath_in_document_folder
from fava.json_api import api_endpoint
from fava.qb_close import closed_through

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from fava.beans.abc import Directive
    from fava.core.ingest import WrappedImporter

#: Where the Docker image mounts the books.
DOCKER_BOOKS = Path("/books")
#: beangulp marks entries that are already in the books with this metadata.
DUPLICATE = "__duplicate__"
#: Files listed in the popup.
MAX_FILES = 20


class QbInbox(Struct, frozen=True):
    """The inbox folder and what's in it."""

    #: The inbox as the user's computer sees it; None when Favabooks runs
    #: in Docker and doesn't know where the books folder is.
    inbox: str | None
    #: The inbox relative to the folder with docker-compose.yml (Docker).
    relative: str | None
    docker: bool
    files: list[str]
    file_count: int
    documents: int
    transactions: int


def inbox_dir(ledger: FavaLedger) -> Path | None:
    """The first import folder, where new files go."""
    dirs = ledger.fava_options.import_dirs
    return ledger.join_path(dirs[0]) if dirs else None


def inbox_files(inbox: Path | None) -> list[Path]:
    """Files waiting in the inbox (not hidden ones like .gitkeep)."""
    if inbox is None or not inbox.is_dir():
        return []
    return sorted(
        p
        for p in inbox.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    )


def host_path(path: Path) -> str | None:
    """A path in the container as the user's computer sees it, if known.

    The compose file passes its own folder's books folder as
    FAVABOOKS_HOST_BOOKS (empty where the shell doesn't set PWD, as in
    Windows PowerShell).
    """
    if not os.environ.get("FAVABOOKS_DOCKER"):
        return str(path)
    host = os.environ.get("FAVABOOKS_HOST_BOOKS", "").rstrip("/\\")
    if (
        not host
        or host == str(DOCKER_BOOKS)
        or not path.is_relative_to(DOCKER_BOOKS)
    ):
        return None
    windows = "\\" in host or re.match(r"^[A-Za-z]:", host) is not None
    return ("\\" if windows else "/").join(
        [host, *path.relative_to(DOCKER_BOOKS).parts]
    )


@api_endpoint
def get_qb_inbox() -> QbInbox:
    """The inbox and whether the books have documents yet."""
    ledger = g.ledger
    ledger.changed()
    inbox = inbox_dir(ledger)
    files = inbox_files(inbox)
    docker = bool(os.environ.get("FAVABOOKS_DOCKER"))
    relative = None
    if docker and inbox is not None and inbox.is_relative_to(DOCKER_BOOKS):
        relative = "/".join(["books", *inbox.relative_to(DOCKER_BOOKS).parts])
    return QbInbox(
        inbox=host_path(inbox) if inbox is not None else None,
        relative=relative,
        docker=docker,
        files=[str(p.relative_to(inbox)) for p in files[:MAX_FILES]]
        if inbox is not None
        else [],
        file_count=len(files),
        documents=len(ledger.all_entries_by_type.Document),
        transactions=len(ledger.all_entries_by_type.Transaction),
    )


# --- Command line -------------------------------------------------------


class InboxError(Exception):
    """A problem the command line reports and stops on."""


def _out(text: str) -> None:
    sys.stdout.write(text + "\n")


def _err(text: str) -> None:
    sys.stderr.write(text + "\n")


def _importers(ledger: FavaLedger) -> list[WrappedImporter]:
    ingest = ledger.ingest
    if ingest.errors:
        raise InboxError(ingest.errors[0].message)
    if ingest.loaded_config is None:
        return []
    return list(ingest.loaded_config.importers.values())


def _new_name(importer: WrappedImporter, path: Path) -> tuple[str, str]:
    """The account a file is filed under, and its new name."""
    info = importer.file_import_info(path)
    name = info.name
    if not re.match(r"^\d{4}-\d{2}-\d{2}", name):
        name = f"{info.date} {name}"
    return info.account, name


def list_inbox(ledger: FavaLedger) -> None:
    """Print the files waiting and which importer reads each."""
    inbox = inbox_dir(ledger)
    if inbox is None:
        msg = (
            'the books have no inbox; add: custom "fava-option" '
            '"import-dirs" "inbox"'
        )
        raise InboxError(msg)
    importers = _importers(ledger)
    files = inbox_files(inbox)
    if not files:
        _out(f"The inbox is empty: {inbox}")
        return
    for path in files:
        _out(str(path))
        matches = [i for i in importers if i.identify(path)]
        for importer in matches:
            account, name = _new_name(importer, path)
            _out(f"  {importer.name}: {account}, files as '{name}'")
        if not matches:
            _out(
                "  no importer: a CSV needs its bank connected in Favabooks "
                "(Bank & card accounts); book anything else by hand and file "
                "it in documents/"
            )


def _pick(
    importers: list[WrappedImporter], path: Path, name: str | None
) -> WrappedImporter:
    matches = [i for i in importers if i.identify(path)]
    if name is not None:
        matches = [i for i in matches if i.name == name]
    if not matches:
        msg = (
            f"no importer reads {path.name}"
            + (f" as {name}" if name is not None else "")
            + "; connect the account in Favabooks (Banking → Bank & card "
            "accounts) or book the file by hand"
        )
        raise InboxError(msg)
    if len(matches) > 1:
        names = ", ".join(i.name for i in matches)
        msg = (
            f"several importers read {path.name} ({names}); pick one with "
            "--importer"
        )
        raise InboxError(msg)
    return matches[0]


def import_file(
    ledger: FavaLedger, path: Path, importer_name: str | None, *, save: bool
) -> None:
    """Print (and with save, add) the new entries of a file."""
    # Not at the top: fava.beans.str imports fava.core, which imports it
    # back, so it only works once fava.core is loaded.
    from fava.beans.str import to_string  # noqa: PLC0415

    if not path.is_file():
        msg = f"{path} isn't a file"
        raise InboxError(msg)
    importer = _pick(_importers(ledger), path, importer_name)
    entries = ledger.ingest.extract(str(path), importer.name)
    new: list[Directive] = [e for e in entries if not e.meta.get(DUPLICATE)]
    for entry in new:
        _out(to_string(entry))
    skipped = len(entries) - len(new)
    _err(
        f"{len(new)} new entries from {path.name}"
        + (f" ({skipped} already in the books, skipped)" if skipped else "")
    )
    closed = closed_through(ledger)
    inside = [e for e in new if closed is not None and e.date <= closed]
    if closed is not None and inside:
        msg = (
            f"{len(inside)} entries are dated on or before {closed}, when the "
            "books were closed; reopen them in Favabooks first"
        )
        if save:
            raise InboxError(msg)
        _err(f"Warning: {msg}.")
    if not save:
        return
    if new:
        ledger.file.insert_entries(new)
        _err(f"Added {len(new)} entries.")
    else:
        _err("Nothing new to add.")
    account, name = _new_name(importer, path)
    documents = ledger.options["documents"]
    if not documents or not account:
        _err(f"Left {path} in place: the books have no documents folder.")
        return
    target = filepath_in_document_folder(documents[0], account, name, ledger)
    if target.exists():
        _err(f"Left {path} in place: {target} already exists.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(path, target)
    _err(f"Filed {path.name} as {target}.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the inbox command line."""
    parser = argparse.ArgumentParser(
        prog="python -m fava.qb_inbox",
        description=(
            "List the inbox, or import a file with the importers set up in "
            "Favabooks. Prints the new entries; --save adds them to the "
            "books and files the file under documents/."
        ),
    )
    parser.add_argument("ledger", help="the main .beancount file")
    parser.add_argument("file", nargs="?", help="a file to import")
    parser.add_argument("--importer", help="the importer, if several match")
    parser.add_argument(
        "--save", action="store_true", help="add the entries and file it"
    )
    args = parser.parse_args(argv)
    if not Path(args.ledger).is_file():
        _err(f"Error: {args.ledger} isn't a file")
        return 1
    try:
        # The polling watcher starts no thread; a command needs no watching.
        ledger = FavaLedger(
            str(Path(args.ledger).resolve()), poll_watcher=True
        )
        if args.file is None:
            list_inbox(ledger)
        else:
            import_file(ledger, Path(args.file), args.importer, save=args.save)
    except InboxError as error:
        _err(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
