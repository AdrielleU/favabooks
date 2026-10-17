"""Close books (qb-fork).

Closing the books through a date writes, in plain Beancount:

- a `custom "closed-books"` entry on that date (with an optional note);
- a `balance` check the next day for every account used so far (each
  currency), marked with `closed-books:` metadata.

Any later change to an entry on or before the closing date then breaks a
balance check, which Beancount reports as an error, whatever tool made
it. Favabooks' own pages also refuse to write into a closed period
(`check_open`). Reopening removes the latest close's entries.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import cast
from typing import TYPE_CHECKING

from beancount.core import data
from beancount.core.amount import Amount
from beancount.parser.grammar import ValueType
from msgspec import Struct

from fava.beans.funcs import hash_entry
from fava.context import g
from fava.core.file import get_entry_slice
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable

    from fava.beans.abc import Directive
    from fava.core import FavaLedger

CLOSE_TYPE = "closed-books"
META_KEY = "closed-books"
DAY = datetime.timedelta(days=1)


def _closes(ledger: FavaLedger | None = None) -> list[Directive]:
    return sorted(
        (
            c
            for c in (ledger or g.ledger).all_entries_by_type.Custom
            if c.type == CLOSE_TYPE
        ),
        key=lambda c: c.date,
    )


def closed_through(ledger: FavaLedger | None = None) -> datetime.date | None:
    """The latest closing date, or None if the books were never closed."""
    closes = _closes(ledger)
    return closes[-1].date if closes else None


def check_open(dates: Iterable[datetime.date]) -> None:
    """Refuse a change dated on or before the closing date."""
    closed = closed_through()
    if closed is None:
        return
    inside = [d for d in dates if d <= closed]
    if inside:
        msg = (
            f"the books are closed through {closed}, so entries dated "
            f"{min(inside)} can't change; reopen them in Settings → Close "
            "books first"
        )
        raise ValidationError(msg)


class QbClose(Struct, frozen=True):
    """A close of the books."""

    entry_hash: str
    date: datetime.date
    note: str
    #: Balance checks written with it.
    checks: int


class QbCloseState(Struct, frozen=True):
    """Whether and how far the books are closed, and a suggested date."""

    closed_through: datetime.date | None
    history: list[QbClose]
    #: End of the last full year (or month) with transactions to close.
    suggested: datetime.date
    today: datetime.date


def _note(entry: Directive) -> str:
    values = getattr(entry, "values", None) or []
    return " ".join(str(v.value) for v in values if isinstance(v.value, str))


def _checks_by_date() -> dict[datetime.date, list[Directive]]:
    by_date: dict[datetime.date, list[Directive]] = defaultdict(list)
    for entry in g.ledger.all_entries_by_type.Balance:
        value = entry.meta.get(META_KEY)
        if isinstance(value, datetime.date):
            by_date[value].append(entry)
    return by_date


@api_endpoint
def get_qb_close() -> QbCloseState:
    """The closing state and the closes so far, latest first."""
    g.ledger.changed()
    today = local_today()
    checks = _checks_by_date()
    history = [
        QbClose(hash_entry(c), c.date, _note(c), len(checks[c.date]))
        for c in reversed(_closes())
    ]
    year_end = datetime.date(today.year - 1, 12, 31)
    closed = closed_through()
    month_end = today.replace(day=1) - DAY
    suggested = year_end if closed is None or closed < year_end else month_end
    return QbCloseState(closed, history, suggested, today)


@api_endpoint
def put_qb_close(date: str, note: str = "") -> str:
    """Close the books through `date`."""
    ledger = g.ledger
    ledger.changed()
    try:
        day = datetime.date.fromisoformat(date)
    except ValueError:
        msg = "the closing date looks like 2025-12-31"
        raise ValidationError(msg) from None
    if day >= local_today():
        msg = "the closing date must be in the past"
        raise ValidationError(msg)
    closed = closed_through()
    if closed is not None and day <= closed:
        msg = f"the books are already closed through {closed}"
        raise ValidationError(msg)

    balances: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for txn in ledger.all_entries_by_type.Transaction:
        if txn.date > day:
            break
        for posting in txn.postings:
            units = posting.units
            # Booking fills in every posting's units.
            if (
                units is not None and units.number is not None
            ):  # pragma: no branch
                balances[posting.account, units.currency] += units.number
    check_day = day + DAY
    meta = {META_KEY: day}
    entries: list[data.Directive] = [
        data.Custom(
            {},
            day,
            CLOSE_TYPE,
            [ValueType(" ".join(note.split()) or "Books closed", str)],
        )
    ]
    for (account, currency), number in sorted(balances.items()):
        details = ledger.accounts.get(account)
        closes = details.close_date if details is not None else None
        if closes is not None and closes <= check_day:
            continue
        entries.append(
            data.Balance(
                dict(meta),
                check_day,
                account,
                Amount(number, currency),
                None,
                None,
            )
        )
    ledger.file.insert_entries(cast("list[Directive]", entries))
    return (
        f"Closed the books through {day} with {len(entries) - 1} balance "
        "checks."
    )


@api_endpoint
def delete_qb_close() -> str:
    """Reopen the books: remove the latest close and its balance checks."""
    ledger = g.ledger
    ledger.changed()
    closes = _closes()
    if not closes:
        msg = "the books aren't closed"
        raise ValidationError(msg)
    latest = closes[-1]
    entries = [latest, *_checks_by_date()[latest.date]]
    # Bottom-up, so the line numbers in the other entries' hashes hold.
    entries.sort(
        key=lambda e: (str(e.meta["filename"]), int(str(e.meta["lineno"]))),
        reverse=True,
    )
    for entry in entries:
        _, sha256sum = get_entry_slice(entry)
        ledger.file.delete_entry_slice(hash_entry(entry), sha256sum)
    previous = closes[-2].date if len(closes) > 1 else None
    return f"Reopened the books after {latest.date}." + (
        f" They're still closed through {previous}." if previous else ""
    )
