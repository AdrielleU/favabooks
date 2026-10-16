"""QuickBooks-style endpoints for the ledger-ui fork.

Imported at the top of application.py so the endpoints are registered on the
json_api blueprint before the module-level app is created.
"""

from __future__ import annotations

import datetime
import re
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from msgspec import Struct

from fava.context import g
from fava.core.conversion import conversion_from_str
from fava.core.inventory import CounterInventory
from fava.json_api import api_endpoint
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
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
