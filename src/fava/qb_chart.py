"""Chart of accounts (qb-fork).

Every account with its QuickBooks-style type, balance and activity, and
adding (open) or closing accounts. Opening and closing write Open and
Close directives, so the ledger stays plain Beancount.
"""

from __future__ import annotations

import datetime
from collections import Counter
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from beancount.core.account import is_valid
from msgspec import Struct

from fava.beans import create
from fava.context import g
from fava.core.file import insert_entry
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.qb_qbo import qbo_type
from fava.qb_reports import _Amounts
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Directive

ZERO = Decimal()


class QbChartAccount(Struct, frozen=True):
    """An account in the chart of accounts."""

    account: str
    #: QuickBooks-style account type and detail type.
    type: str
    detail_type: str
    #: Balance in the operating currency (balance sheet accounts: to date;
    #: income and expenses: from `year_start`, the latest year with data).
    balance: Decimal
    transactions: int
    open_date: datetime.date | None
    close_date: datetime.date | None
    last_date: datetime.date | None


class QbChart(Struct, frozen=True):
    """The chart of accounts and the account roots."""

    currency: str
    accounts: list[QbChartAccount]
    #: Root names by kind (assets, liabilities, equity, income, expenses).
    roots: dict[str, str]
    #: First day the balance of income and expenses counts from.
    year_start: datetime.date


def _roots() -> dict[str, str]:
    options = g.ledger.options
    return {
        "assets": options["name_assets"],
        "liabilities": options["name_liabilities"],
        "equity": options["name_equity"],
        "income": options["name_income"],
        "expenses": options["name_expenses"],
    }


@api_endpoint
def get_qb_chart() -> QbChart:
    """Every account (open and closed) with type, balance and activity."""
    g.ledger.changed()
    roots = _roots()
    pnl = (f"{roots['income']}:", f"{roots['expenses']}:")
    today = local_today()
    txns = g.ledger.all_entries_by_type.Transaction
    # The latest year with transactions (this year once it has any).
    latest = min(today, txns[-1].date) if txns else today
    year_start = datetime.date(latest.year, 1, 1)
    amounts = _Amounts()
    balances: dict[str, Decimal] = defaultdict(Decimal)
    counts: Counter[str] = Counter()
    last: dict[str, datetime.date] = {}
    for txn in txns:
        touched = set()
        for posting in txn.postings:
            account = posting.account
            touched.add(account)
            last[account] = txn.date
            if txn.date > today or (
                account.startswith(pnl) and txn.date < year_start
            ):
                continue
            number = amounts.of(posting, txn.date)
            if number is not None:
                balances[account] += number
        counts.update(touched)
    opened = {o.account: o.date for o in g.ledger.all_entries_by_type.Open}
    accounts = []
    for name in sorted(g.ledger.accounts):
        details = g.ledger.accounts[name]
        kind, detail = qbo_type(name)
        accounts.append(
            QbChartAccount(
                account=name,
                type=kind,
                detail_type=detail,
                balance=balances[name],
                transactions=counts[name],
                open_date=opened.get(name),
                close_date=details.close_date,
                last_date=last.get(name),
            )
        )
    return QbChart(amounts.currency, accounts, roots, year_start)


def _insert_with_accounts(entry: Directive) -> None:
    """Add an Open or Close where the other accounts are declared.

    That's the end of the file holding the most Open entries (often an
    accounts file); without any, the ledger's usual insert position.
    """
    ledger = g.ledger
    files = Counter(
        str(o.meta["filename"])
        for o in ledger.all_entries_by_type.Open
        if o.meta and "filename" in o.meta
    )
    if not files:
        ledger.file.insert_entries([entry])
        return
    path, _ = insert_entry(
        entry,
        files.most_common(1)[0][0],
        [],
        ledger.fava_options.currency_column,
        ledger.fava_options.indent,
    )
    ledger.watcher.notify(path)
    ledger.extensions.after_insert_entry(entry)


def _date(value: str, label: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        msg = f"the {label} looks like 2026-01-31"
        raise ValidationError(msg) from None


@api_endpoint
def put_qb_account_open(account: str, date: str, currency: str = "") -> str:
    """Add an account (an Open directive) from `date`."""
    ledger = g.ledger
    ledger.changed()
    name = account.strip()
    roots = _roots()
    if not is_valid(name) or name.split(":", 1)[0] not in roots.values():
        msg = (
            f"'{name}' isn't a valid account name: it starts with one of "
            f"{', '.join(roots.values())}, then parts that each start with "
            "a capital letter or digit, joined by ':' (no spaces)"
        )
        raise ValidationError(msg)
    if name in ledger.accounts:
        msg = f"{name} already exists"
        raise ValidationError(msg)
    opened = _date(date, "opening date")
    currencies = [currency.strip().upper()] if currency.strip() else []
    _insert_with_accounts(create.open({}, opened, name, currencies))
    return f"Added {name}."


@api_endpoint
def put_qb_account_close(account: str, date: str) -> str:
    """Close an account (a Close directive) on `date`.

    Only an account with nothing in it can close: Beancount would flag
    later postings, and a balance left behind would vanish from reports.
    """
    ledger = g.ledger
    ledger.changed()
    if account not in ledger.accounts:
        msg = f"unknown account '{account}'"
        raise ValidationError(msg)
    if ledger.accounts[account].close_date is not None:
        msg = f"{account} is already closed"
        raise ValidationError(msg)
    closed = _date(date, "closing date")
    later = [
        txn.date
        for txn in ledger.all_entries_by_type.Transaction
        if txn.date > closed
        and any(p.account == account for p in txn.postings)
    ]
    if later:
        msg = f"{account} has transactions after {closed}, on {max(later)}"
        raise ValidationError(msg)
    roots = _roots()
    if account.split(":", 1)[0] in {roots["assets"], roots["liabilities"]}:
        amounts = _Amounts()
        balance = sum(
            (
                amounts.of(p, txn.date) or ZERO
                for txn in ledger.all_entries_by_type.Transaction
                for p in txn.postings
                if p.account == account
            ),
            ZERO,
        )
        if balance:
            msg = (
                f"{account} still has a balance of {balance}: move it out "
                "(or reconcile it to zero) before closing"
            )
            raise ValidationError(msg)
    _insert_with_accounts(create.close({}, closed, account))
    return f"Closed {account} on {closed}."
