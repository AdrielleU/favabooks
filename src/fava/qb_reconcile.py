"""Reconcile and the account overview for the Register (qb-fork).

Reconciling an account against a statement: tick the transactions on the
statement until the cleared balance equals the statement's ending balance.
Finishing marks each ticked transaction with `reconciled-<account>:
<statement date>` metadata, adds a note, and adds a balance assertion when
nothing is outstanding (so later edits that break it are flagged).
"""

from __future__ import annotations

import datetime
import re
from collections import Counter
from collections import defaultdict
from decimal import Decimal
from decimal import InvalidOperation
from typing import cast
from typing import TYPE_CHECKING

from beancount.core import data
from beancount.core.amount import Amount
from msgspec import Struct

from fava.beans.funcs import hash_entry
from fava.context import g
from fava.json_api import api_endpoint
from fava.json_api import ValidationError

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Directive
    from fava.beans.abc import Transaction

ZERO = Decimal()
NOTE_PREFIX = "Reconciled"


def reconciled_key(account: str) -> str:
    """Metadata key marking a transaction reconciled for `account`."""
    slug = re.sub(r"[^a-z0-9]+", "-", account.lower()).strip("-")
    return f"reconciled-{slug}"


class QbAccountOverview(Struct, frozen=True):
    """A bank or card account with its balance and activity."""

    account: str
    balance: Decimal
    currency: str
    transactions: int
    last_date: datetime.date | None


def _postings(account: str) -> list[tuple[Transaction, Decimal, str]]:
    """(transaction, amount, currency) for every posting to `account`."""
    found = []
    for txn in g.ledger.all_entries_by_type.Transaction:
        for posting in txn.postings:
            units = posting.units
            if (
                posting.account == account
                and units is not None
                and units.number is not None
            ):
                found.append((txn, units.number, units.currency))
    return found


@api_endpoint
def get_qb_accounts_overview() -> list[QbAccountOverview]:
    """Bank and card accounts (Assets, Liabilities) with activity."""
    ledger = g.ledger
    ledger.changed()
    options = ledger.options
    roots = (f"{options['name_assets']}:", f"{options['name_liabilities']}:")
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    amounts: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    counts: Counter[str] = Counter()
    last: dict[str, datetime.date] = {}
    for txn in ledger.all_entries_by_type.Transaction:
        touched = set()
        for posting in txn.postings:
            units = posting.units
            if (
                not posting.account.startswith(roots)
                or units is None
                or units.number is None
            ):
                continue
            totals[posting.account][units.currency] += 1
            amounts[posting.account, units.currency] += units.number
            touched.add(posting.account)
            last[posting.account] = txn.date
        counts.update(touched)
    overview = []
    for account in sorted(
        totals, key=lambda a: (not a.startswith(roots[0]), a)
    ):
        currency = totals[account].most_common(1)[0][0]
        overview.append(
            QbAccountOverview(
                account,
                amounts[account, currency],
                currency,
                counts[account],
                last[account],
            )
        )
    return overview


class QbReconcileRow(Struct, frozen=True):
    """A transaction not yet reconciled for the account."""

    entry_hash: str
    date: datetime.date
    payee: str
    narration: str
    amount: Decimal


class QbReconciliation(Struct, frozen=True):
    """A finished reconciliation (from its note)."""

    date: datetime.date
    comment: str


class QbReconcile(Struct, frozen=True):
    """What the Reconcile screen needs for one account and statement date."""

    account: str
    currency: str
    #: Total of transactions already reconciled.
    beginning_balance: Decimal
    #: Unreconciled transactions up to the statement date, oldest first.
    rows: list[QbReconcileRow]
    #: Book balance on the statement date (reconciled or not).
    books_balance: Decimal
    history: list[QbReconciliation]


def _parse_date(value: str) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        msg = "dates look like 2026-01-31"
        raise ValidationError(msg) from None


def _state(account: str, end: datetime.date | None) -> QbReconcile:
    if account not in g.ledger.accounts:
        msg = f"unknown account '{account}'"
        raise ValidationError(msg)
    key = reconciled_key(account)
    postings = _postings(account)
    currencies = Counter(currency for _, _, currency in postings)
    currency = currencies.most_common(1)[0][0] if currencies else "USD"
    beginning = ZERO
    books = ZERO
    open_rows: dict[str, QbReconcileRow] = {}
    for txn, number, posting_currency in postings:
        if posting_currency != currency:
            continue
        if end is None or txn.date <= end:
            books += number
        if key in txn.meta:
            beginning += number
            continue
        if end is not None and txn.date > end:
            continue
        entry_hash = hash_entry(txn)
        previous = open_rows.get(entry_hash)
        open_rows[entry_hash] = QbReconcileRow(
            entry_hash,
            txn.date,
            txn.payee or "",
            txn.narration or "",
            number + (previous.amount if previous else ZERO),
        )
    history = [
        QbReconciliation(note.date, note.comment)
        for note in g.ledger.all_entries_by_type.Note
        if note.account == account and note.comment.startswith(NOTE_PREFIX)
    ]
    return QbReconcile(
        account=account,
        currency=currency,
        beginning_balance=beginning,
        rows=list(open_rows.values()),
        books_balance=books,
        history=sorted(history, key=lambda h: h.date, reverse=True),
    )


@api_endpoint
def get_qb_reconcile(account_name: str, end_date: str = "") -> QbReconcile:
    """An account's reconciliation state up to a statement date."""
    g.ledger.changed()
    return _state(account_name, _parse_date(end_date))


class QbReconcileResult(Struct, frozen=True):
    """Outcome of finishing a reconciliation."""

    reconciled: int
    #: Whether a balance assertion was added (nothing outstanding).
    balance_assertion: bool


@api_endpoint
def put_qb_reconcile(
    account_name: str,
    end_date: str,
    ending_balance: str,
    entry_hashes: list[str],
) -> QbReconcileResult:
    """Finish a reconciliation once the difference is zero."""
    ledger = g.ledger
    ledger.changed()
    end = _parse_date(end_date)
    if end is None:
        msg = "enter the statement ending date"
        raise ValidationError(msg)
    try:
        ending = Decimal(ending_balance.replace(",", "").replace("$", ""))
    except InvalidOperation:
        msg = "the ending balance must be a number"
        raise ValidationError(msg) from None
    state = _state(account_name, end)
    rows = {row.entry_hash: row for row in state.rows}
    unknown = [h for h in entry_hashes if h not in rows]
    if unknown:
        msg = "some transactions are not open for this statement"
        raise ValidationError(msg)
    picked = list(dict.fromkeys(entry_hashes))
    cleared = state.beginning_balance + sum(
        (rows[h].amount for h in picked), ZERO
    )
    difference = ending - cleared
    if difference != ZERO:
        msg = f"the difference is {difference} {state.currency}, not zero"
        raise ValidationError(msg)

    key = reconciled_key(account_name)
    # Bottom-up: an inserted line shifts the entries below it (and line
    # numbers are part of entry hashes), so insert into the last one first.
    entries_by_hash = {h: ledger.get_entry(h) for h in picked}
    for entry_hash in sorted(
        picked,
        key=lambda h: (
            entries_by_hash[h].meta["filename"],
            entries_by_hash[h].meta["lineno"],
        ),
        reverse=True,
    ):
        ledger.file.insert_metadata(entry_hash, key, end.isoformat())
    ledger.load_file()

    outstanding = len(state.rows) - len(picked)
    entries: list[data.Directive] = [
        data.Note(
            {},
            end,
            account_name,
            f"{NOTE_PREFIX}: statement ending {end.isoformat()}, balance "
            f"{ending} {state.currency}, {len(picked)} transactions"
            + (f", {outstanding} outstanding" if outstanding else ""),
            None,
            None,
        )
    ]
    assertion = outstanding == 0 and ending == state.books_balance
    if assertion:
        entries.append(
            data.Balance(
                {},
                end + datetime.timedelta(days=1),
                account_name,
                Amount(ending, state.currency),
                None,
                None,
            )
        )
    ledger.file.insert_entries(cast("list[Directive]", entries))
    return QbReconcileResult(len(picked), assertion)
