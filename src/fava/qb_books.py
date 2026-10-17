"""Business details (events) and books statistics (qb-fork).

Events are Beancount `event` entries: a type and a description that holds
from its date until the next event of the same type (an address, a tax
status, a registered agent). Future-dated events are reminders.

Statistics show how complete and up to date the books are: entry counts,
transactions per month, and when each bank or card account last had
activity, so a stopped import stands out.
"""

from __future__ import annotations

import datetime
from collections import Counter
from collections import defaultdict
from typing import cast
from typing import TYPE_CHECKING

from beancount.core import data
from msgspec import Struct

from fava.beans.funcs import hash_entry
from fava.context import g
from fava.core.file import get_entry_slice
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Directive

#: Event types a small business usually keeps, offered as suggestions.
SUGGESTED_TYPES = [
    "address",
    "registered-agent",
    "tax-status",
    "ein",
    "business-license",
    "sales-tax-permit",
    "insurance",
    "bank",
    "accountant",
    "fiscal-year",
]


class QbEvent(Struct, frozen=True):
    """An event entry."""

    entry_hash: str
    date: datetime.date
    type: str
    description: str


class QbEventType(Struct, frozen=True):
    """The current value of one event type, and how many it has had."""

    type: str
    current: QbEvent | None
    #: The next future event of this type (a reminder), if any.
    upcoming: QbEvent | None
    count: int


class QbEvents(Struct, frozen=True):
    """Every event, the current value of each type, and suggestions."""

    today: datetime.date
    types: list[QbEventType]
    events: list[QbEvent]
    suggestions: list[str]


@api_endpoint
def get_qb_events() -> QbEvents:
    """Events, newest first, with the current value per type."""
    g.ledger.changed()
    today = local_today()
    events = sorted(
        (
            QbEvent(hash_entry(e), e.date, e.type, e.description)
            for e in g.ledger.all_entries_by_type.Event
        ),
        key=lambda e: (e.date, e.type),
        reverse=True,
    )
    by_type: dict[str, list[QbEvent]] = defaultdict(list)
    for event in events:
        by_type[event.type].append(event)
    types = [
        QbEventType(
            name,
            next((e for e in history if e.date <= today), None),
            next(
                (e for e in reversed(history) if e.date > today),
                None,
            ),
            len(history),
        )
        for name, history in sorted(by_type.items())
    ]
    return QbEvents(
        today,
        types,
        events,
        [t for t in SUGGESTED_TYPES if t not in by_type],
    )


@api_endpoint
def put_qb_event(date: str, type: str, description: str) -> str:  # noqa: A002
    """Add an event."""
    ledger = g.ledger
    ledger.changed()
    try:
        day = datetime.date.fromisoformat(date)
    except ValueError:
        msg = "the date looks like 2026-01-31"
        raise ValidationError(msg) from None
    name = "-".join(type.strip().lower().split())
    text = " ".join(description.split())
    if not name or not text:
        msg = "enter the type and the description"
        raise ValidationError(msg)
    entry = data.Event({}, day, name, text)
    ledger.file.insert_entries([cast("Directive", entry)])
    return f"Added {name}: {text} from {day}."


@api_endpoint
def delete_qb_event(entry_hash: str) -> str:
    """Delete an event entry."""
    ledger = g.ledger
    ledger.changed()
    entry = next(
        (
            e
            for e in ledger.all_entries_by_type.Event
            if hash_entry(e) == entry_hash
        ),
        None,
    )
    if entry is None:
        msg = "that event isn't in the books (any more)"
        raise ValidationError(msg)
    _, sha256sum = get_entry_slice(entry)
    ledger.file.delete_entry_slice(entry_hash, sha256sum)
    return f"Deleted {entry.type}: {entry.description}."


# --- Statistics ---------------------------------------------------------


class QbAccountActivity(Struct, frozen=True):
    """A bank or card account and when it last had activity."""

    account: str
    postings: int
    last_date: datetime.date | None
    #: Days since the last transaction (None without any).
    days: int | None


class QbMonth(Struct, frozen=True):
    """Transactions in a month."""

    month: datetime.date
    transactions: int
    to_review: int


class QbStatistics(Struct, frozen=True):
    """How complete and up to date the books are."""

    today: datetime.date
    first_date: datetime.date | None
    last_date: datetime.date | None
    transactions: int
    to_review: int
    open_accounts: int
    documents: int
    errors: int
    #: Entries per directive type ("Transaction", "Document", ...).
    entries: dict[str, int]
    months: list[QbMonth]
    accounts: list[QbAccountActivity]
    #: (account, postings) for every account, most first.
    postings: list[tuple[str, int]]


@api_endpoint
def get_qb_statistics() -> QbStatistics:
    """Entry counts, monthly activity and bank/card account freshness."""
    ledger = g.ledger
    ledger.changed()
    today = local_today()
    txns = ledger.all_entries_by_type.Transaction
    options = ledger.options
    banks = (f"{options['name_assets']}:", f"{options['name_liabilities']}:")
    postings: Counter[str] = Counter()
    last: dict[str, datetime.date] = {}
    months: dict[datetime.date, list[int]] = defaultdict(lambda: [0, 0])
    for txn in txns:
        month = txn.date.replace(day=1)
        months[month][0] += 1
        months[month][1] += txn.flag == "!"
        for posting in txn.postings:
            postings[posting.account] += 1
            last[posting.account] = txn.date
    entries = Counter(type(e).__name__ for e in ledger.all_entries)
    open_accounts = [
        a for a, d in ledger.accounts.items() if d.close_date is None
    ]
    accounts = [
        QbAccountActivity(
            account,
            postings[account],
            last.get(account),
            (today - last[account]).days if account in last else None,
        )
        for account in sorted(open_accounts)
        if account.startswith(banks)
    ]
    accounts.sort(key=lambda a: (a.days is not None, -(a.days or 0)))
    return QbStatistics(
        today=today,
        first_date=txns[0].date if txns else None,
        last_date=txns[-1].date if txns else None,
        transactions=len(txns),
        to_review=sum(t.flag == "!" for t in txns),
        open_accounts=len(open_accounts),
        documents=len(ledger.all_entries_by_type.Document),
        errors=len(ledger.errors),
        entries=dict(sorted(entries.items())),
        months=[QbMonth(m, n, r) for m, (n, r) in sorted(months.items())],
        accounts=accounts,
        postings=postings.most_common(),
    )
