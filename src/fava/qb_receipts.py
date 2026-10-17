"""Beancount plugin: check receipts named on entries (qb-fork).

Like Fava's `fava.plugins.link_documents`, but without its `dok-<date>`
links, which clutter the journal and the filter suggestions; Favabooks
finds receipts from the `document:` metadata itself.

For every entry with `document*` metadata (on the entry or a posting), the
named file must be a Document entry: either by file name under one of the
accounts involved, or by path relative to the entry's file. Matching
Document entries get the `#linked` tag (so the journal can hide receipts
that belong to a transaction); a missing file is an error.

Use it in a ledger with: plugin "fava.qb_receipts"
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from fava.beans.abc import Document
from fava.beans.account import get_entry_accounts
from fava.beans.funcs import get_position
from fava.beans.helpers import replace
from fava.helpers import BeancountError
from fava.util.sets import add_to_set

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from fava.beans.abc import Directive


class ReceiptError(BeancountError):
    """A receipt named in metadata isn't in the documents."""


__plugins__ = ["check_receipts"]


def check_receipts(
    entries: Sequence[Directive],
    _: object,
) -> tuple[Sequence[Directive], list[ReceiptError]]:
    """Tag the receipts entries name; report the ones that are missing."""
    errors = []
    by_fullname: dict[Path, int] = {}
    by_basename: dict[str, list[tuple[int, Document]]] = defaultdict(list)
    for index, entry in enumerate(entries):
        if isinstance(entry, Document):
            fullname = Path(entry.filename)
            by_fullname[fullname] = index
            by_basename[fullname.name].append((index, entry))

    linked: set[int] = set()
    for entry in entries:
        named = [
            (value, get_entry_accounts(entry))
            for key, value in entry.meta.items()
            if key.startswith("document") and isinstance(value, str)
        ]
        for posting in getattr(entry, "postings", []):
            named.extend(
                (value, [posting.account])
                for key, value in (posting.meta or {}).items()
                if key.startswith("document") and isinstance(value, str)
            )
        if not named:
            continue
        entry_filename, _ = get_position(entry)
        for name, accounts in named:
            found = [
                j for j, doc in by_basename[name] if doc.account in accounts
            ]
            path = (Path(entry_filename).parent / name).resolve()
            if path in by_fullname:
                found.append(by_fullname[path])
            if not found:
                errors.append(
                    ReceiptError(
                        entry.meta, f"Receipt not found: '{name}'", entry
                    )
                )
            linked.update(found)

    new_entries = list(entries)
    for j in linked:
        doc: Document = new_entries[j]  # type: ignore[assignment]  # ty:ignore[invalid-assignment]
        new_entries[j] = replace(doc, tags=add_to_set(doc.tags, "linked"))
    return new_entries, errors
