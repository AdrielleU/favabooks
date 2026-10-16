"""QuickBooks-style endpoints for the favabooks fork.

Imported at the top of application.py so the endpoints are registered on the
json_api blueprint before the module-level app is created.
"""

from __future__ import annotations

import datetime
import re
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from beancount.core.data import Transaction
from msgspec import Struct

from fava.beans.funcs import hash_entry
from fava.context import g
from fava.core.conversion import conversion_from_str
from fava.core.file import get_entry_slice
from fava.core.inventory import CounterInventory
from fava.helpers import FavaAPIError
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from fava.core import FavaLedger

#: Accounts shown on the dashboard's balances card.
CASH_ACCOUNTS = re.compile(r"^Assets:(Bank|Stripe)(:|$)")
#: Number of expense accounts on the "expenses by category" card.
TOP_EXPENSES = 8
ZERO = Decimal()


class QbAmount(Struct, frozen=True):
    """An account with an amount in the operating currency."""

    account: str
    amount: Decimal


class QbProfitLoss(Struct, frozen=True):
    """Income, expenses and net profit for one month, all positive-signed."""

    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal


class QbDashboard(Struct, frozen=True):
    """Everything the dashboard shows, in one response."""

    currency: str
    balances_date: datetime.date
    balances: list[QbAmount]
    this_month: QbProfitLoss
    last_month: QbProfitLoss
    top_expenses: list[QbAmount]
    review_count: int
    error_count: int


def _month_start(day: datetime.date, offset: int = 0) -> datetime.date:
    """First day of the month of `day`, shifted by `offset` months."""
    months = day.year * 12 + day.month - 1 + offset
    return datetime.date(months // 12, months % 12 + 1, 1)


def _anchor_date() -> datetime.date:
    """The day whose month the dashboard shows.

    The last day of the header's time filter if one is set, otherwise today.
    """
    date_range = g.filtered.date_range
    if date_range is not None:
        return date_range.end - datetime.timedelta(days=1)
    return local_today()


def _operating_currency(ledger: FavaLedger) -> str:
    currencies = ledger.options["operating_currency"]
    return currencies[0] if currencies else "USD"


@api_endpoint
def get_qb_dashboard() -> QbDashboard:
    """Bank balances, P&L this month vs last, top expenses and counts."""
    ledger = g.ledger
    ledger.changed()
    options = ledger.options
    income_root = options["name_income"]
    expenses_root = options["name_expenses"]
    currency = _operating_currency(ledger)
    conv = conversion_from_str(currency)

    def convert(inventory: CounterInventory, date: datetime.date) -> Decimal:
        return conv.apply(inventory, ledger.prices, date).get(currency, ZERO)

    this_start = _month_start(_anchor_date())
    last_start = _month_start(this_start, -1)
    next_start = _month_start(this_start, 1)

    cash: dict[str, CounterInventory] = defaultdict(CounterInventory)
    pnl = {
        key: (CounterInventory(), CounterInventory())
        for key in (this_start, last_start)
    }
    by_account: dict[str, CounterInventory] = defaultdict(CounterInventory)
    review_count = 0

    for txn in ledger.all_entries_by_type.Transaction:
        if txn.flag == "!":
            review_count += 1
        if txn.date >= next_start:
            continue
        month = (
            this_start
            if txn.date >= this_start
            else last_start
            if txn.date >= last_start
            else None
        )
        for posting in txn.postings:
            account = posting.account
            if CASH_ACCOUNTS.match(account):
                cash[account].add_position(posting)
            if month is None:
                continue
            income, expenses = pnl[month]
            if account.startswith(f"{income_root}:"):
                income.add_position(posting)
            elif account.startswith(f"{expenses_root}:"):
                expenses.add_position(posting)
                if month == this_start:
                    by_account[account].add_position(posting)

    balances_date = next_start - datetime.timedelta(days=1)
    balances = [
        QbAmount(account, convert(inventory, balances_date))
        for account, inventory in sorted(cash.items())
        if (close := ledger.accounts[account].close_date) is None
        or close >= this_start
    ]

    def profit_loss(start: datetime.date) -> QbProfitLoss:
        end = _month_start(start, 1) - datetime.timedelta(days=1)
        income, expenses = pnl[start]
        income_total = -convert(income, end)
        expenses_total = convert(expenses, end)
        return QbProfitLoss(
            start.strftime("%Y-%m"),
            income_total,
            expenses_total,
            income_total - expenses_total,
        )

    expense_rows = [
        QbAmount(account, convert(inventory, balances_date))
        for account, inventory in by_account.items()
    ]
    expense_rows.sort(key=lambda row: row.amount, reverse=True)

    return QbDashboard(
        currency=currency,
        balances_date=balances_date,
        balances=balances,
        this_month=profit_loss(this_start),
        last_month=profit_loss(last_start),
        top_expenses=[r for r in expense_rows if r.amount > 0][:TOP_EXPENSES],
        review_count=review_count,
        error_count=len(ledger.errors),
    )


# --- Review queue and reclassify -------------------------------------------

#: The `!` flag on a transaction's first line ("2026-03-12 ! ...").
_PENDING_FLAG = re.compile(r"^(\d{4}-\d{2}-\d{2}\s+)!")


def _posting_line(account: str) -> re.Pattern[str]:
    """Match posting lines for exactly `account`, keeping indent and flag."""
    return re.compile(
        rf"^(\s+(?:\S\s+)?){re.escape(account)}(?=\s|$)", re.MULTILINE
    )


class QbReviewRow(Struct, frozen=True):
    """A transaction flagged `!` waiting in the review queue."""

    entry_hash: str
    date: datetime.date
    payee: str
    narration: str
    #: The bank or card posting (first Assets/Liabilities posting).
    account: str
    amount: Decimal
    currency: str
    #: The other postings' accounts; one entry unless the transaction is split.
    categories: list[str]


class QbEditFailure(Struct, frozen=True):
    """An entry that could not be changed."""

    entry_hash: str
    error: str


class QbEditResult(Struct, frozen=True):
    """Outcome of an edit across several entries; edits are per entry."""

    changed: int
    failed: list[QbEditFailure]


@api_endpoint
def get_qb_review() -> list[QbReviewRow]:
    """Transactions flagged `!`, newest first, within the header filters."""
    g.ledger.changed()
    options = g.ledger.options
    roots = (f"{options['name_assets']}:", f"{options['name_liabilities']}:")
    rows = []
    for entry in g.filtered.entries:
        if not isinstance(entry, Transaction) or entry.flag != "!":
            continue
        postings = entry.postings
        source = next(
            (p for p in postings if p.account.startswith(roots)), postings[0]
        )
        categories = [p.account for p in postings if p is not source]
        # Units are always filled in after loading; the fallback is for typing.
        units = source.units
        number = units.number if units is not None else None
        rows.append(
            QbReviewRow(
                entry_hash=hash_entry(entry),
                date=entry.date,
                payee=entry.payee or "",
                narration=entry.narration or "",
                account=source.account,
                amount=number if number is not None else ZERO,
                currency=units.currency if units is not None else "",
                categories=list(dict.fromkeys(categories)),
            )
        )
    rows.sort(key=lambda row: row.date, reverse=True)
    return rows


def _check_account(account: str) -> None:
    if account not in g.ledger.accounts:
        msg = f"unknown account '{account}'"
        raise ValidationError(msg)


def _edit_entries(
    entry_hashes: list[str], edit: Callable[[str], str]
) -> QbEditResult:
    """Apply `edit` to the source text of each entry and save it.

    Saves go through save_entry_slice (sha-checked, fires the extension hooks
    such as auto-commit). Each entry is saved on its own, so one failure
    doesn't stop the rest; failures are returned instead of raised.
    """
    ledger = g.ledger
    entries = []
    failed = []
    for entry_hash in dict.fromkeys(entry_hashes):
        try:
            entries.append((entry_hash, ledger.get_entry(entry_hash)))
        except FavaAPIError as error:
            failed.append(QbEditFailure(entry_hash, str(error)))
    # Edit bottom-up so line numbers of entries not yet edited stay valid.
    entries.sort(
        key=lambda pair: (pair[1].meta["filename"], pair[1].meta["lineno"]),
        reverse=True,
    )
    changed = 0
    for entry_hash, entry in entries:
        source, sha256sum = get_entry_slice(entry)
        new_source = edit(source)
        if new_source == source:
            continue
        try:
            ledger.file.save_entry_slice(entry_hash, new_source, sha256sum)
        except FavaAPIError as error:
            failed.append(QbEditFailure(entry_hash, str(error)))
        else:
            changed += 1
    return QbEditResult(changed, failed)


def _reclassify(source: str, from_account: str, to_account: str) -> str:
    return _posting_line(from_account).sub(
        lambda match: match.group(1) + to_account, source
    )


@api_endpoint
def put_qb_reclassify(
    entry_hashes: list[str], from_account: str, to_account: str
) -> QbEditResult:
    """Move postings from one account to another across many entries."""
    _check_account(to_account)
    return _edit_entries(
        entry_hashes,
        lambda source: _reclassify(source, from_account, to_account),
    )


@api_endpoint
def put_qb_accept(
    entry_hashes: list[str], from_account: str = "", to_account: str = ""
) -> QbEditResult:
    """Accept reviewed entries (flag `!` to `*`), optionally recategorising.

    Both changes are made in one edit, since an entry's hash changes on save.
    """
    if to_account:
        if not from_account:
            msg = "from_account is required with to_account"
            raise ValidationError(msg)
        _check_account(to_account)

    def edit(source: str) -> str:
        if to_account:
            source = _reclassify(source, from_account, to_account)
        return _PENDING_FLAG.sub(r"\1*", source, count=1)

    return _edit_entries(entry_hashes, edit)
