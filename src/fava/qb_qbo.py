"""QuickBooks Online export (qb-fork).

Files for QuickBooks Online's own importer (Settings → Import data), in
the order it wants them: the chart of accounts, then customers and
vendors, then journal entries.

- Account names are flattened ("Expenses:Legal:Startup" becomes
  "Legal - Startup") so both files agree on names whatever QuickBooks does
  with sub-accounts; each gets a QuickBooks account type and detail type.
- Journal entries are one per transaction for the year (with an opening
  entry for balances carried in from earlier years), or a single entry with
  the year-end balances. Amounts are in the operating currency; lines to
  Accounts Receivable or Payable carry the customer or vendor name, which
  QuickBooks requires.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from msgspec import Struct

from fava.context import g
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.qb_reports import _Amounts

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Transaction

ZERO = Decimal()

#: (words in the account name, QuickBooks detail type) for expenses.
EXPENSE_DETAILS = (
    (("advertis", "marketing", "promotion"), "Advertising/Promotional"),
    (("software", "subscription", "saas", "dues"), "Dues & subscriptions"),
    (
        ("legal", "accounting", "professional", "bookkeep"),
        "Legal & Professional Fees",
    ),
    (("meal", "food"), "Travel Meals"),
    (("travel", "airfare", "hotel", "lodging"), "Travel"),
    (("telephone", "phone", "internet"), "Communication"),
    (("utilit",), "Utilities"),
    (("rent", "lease"), "Rent or Lease of Buildings"),
    (("insurance",), "Insurance"),
    (("fee", "bank", "stripe", "paypal"), "Bank Charges"),
    (("tax",), "Taxes Paid"),
    (("interest",), "Interest Paid"),
    (("shipping", "postage", "freight"), "Shipping, Freight & Delivery"),
    (("repair", "maintenance"), "Repair & Maintenance"),
    (("supplies",), "Supplies & Materials"),
    (("auto", "vehicle", "fuel", "mileage"), "Auto"),
    (("charit", "donation"), "Charitable Contributions"),
    (
        ("office", "cloud", "hosting", "equipment", "startup", "admin"),
        "Office/General Administrative Expenses",
    ),
)


def _has(account: str, words: tuple[str, ...]) -> bool:
    lowered = account.lower()
    return any(word in lowered for word in words)


def qbo_type(account: str) -> tuple[str, str]:  # noqa: PLR0911, PLR0912 (a lookup table)
    """QuickBooks Online account type and detail type for an account."""
    options = g.ledger.options
    root = account.split(":", 1)[0]
    if root == options["name_assets"]:
        if "Receivable" in account:
            return "Accounts receivable (A/R)", "Accounts Receivable (A/R)"
        if _has(account, ("bank", "checking", "savings")):
            detail = "Savings" if _has(account, ("savings",)) else "Checking"
            return "Bank", detail
        if _has(account, ("cash",)):
            return "Bank", "Cash on hand"
        if _has(account, ("equipment", "computer", "furniture", "vehicle")):
            return "Fixed Assets", "Machinery & Equipment"
        return "Other Current Assets", "Other Current Assets"
    if root == options["name_liabilities"]:
        if "Payable" in account:
            return "Accounts payable (A/P)", "Accounts Payable (A/P)"
        if _has(account, ("creditcard", "credit card", "card")):
            return "Credit Card", "Credit Card"
        if _has(account, ("tax",)):
            return "Other Current Liabilities", "Sales Tax Payable"
        if _has(account, ("loan", "note")):
            return "Long Term Liabilities", "Notes Payable"
        return "Other Current Liabilities", "Other Current Liabilities"
    if root == options["name_equity"]:
        if _has(account, ("opening",)):
            return "Equity", "Opening Balance Equity"
        if _has(account, ("retained",)):
            return "Equity", "Retained Earnings"
        if _has(account, ("draw", "distribution")):
            return "Equity", "Owner's Equity"
        return "Equity", "Owner's Equity"
    if root == options["name_income"]:
        if _has(account, ("interest",)):
            return "Other Income", "Interest Earned"
        if _has(account, ("product", "goods")):
            return "Income", "Sales of Product Income"
        return "Income", "Service/Fee Income"
    if _has(account, ("cogs", "costofgoods", "cost-of-goods", "costofsales")):
        return "Cost of Goods Sold", "Supplies & Materials - COGS"
    if _has(account, ("uncategorized",)):
        return "Expenses", "Other Miscellaneous Service Cost"
    for words, detail in EXPENSE_DETAILS:
        if _has(account, words):
            return "Expenses", detail
    return "Expenses", "Other Business Expenses"


def qbo_names(accounts: list[str]) -> dict[str, str]:
    """Import-safe QuickBooks names: no root, " - " for sub-accounts.

    Names that would clash (e.g. Assets:Equipment and Expenses:Equipment)
    get their root in parentheses.
    """
    short = {
        a: " - ".join(a.split(":")[1:]) or a for a in sorted(set(accounts))
    }
    counts: defaultdict[str, int] = defaultdict(int)
    for name in short.values():
        counts[name.lower()] += 1
    return {
        a: f"{name} ({a.split(':', 1)[0]})"
        if counts[name.lower()] > 1
        else name
        for a, name in short.items()
    }


class QbQboAccount(Struct, frozen=True):
    """A chart of accounts row."""

    name: str
    type: str
    detail_type: str
    #: The Beancount account it comes from (for the description).
    account: str


class QbQboLine(Struct, frozen=True):
    """A journal entry line."""

    journal_no: str
    date: datetime.date
    account: str
    debit: Decimal
    credit: Decimal
    description: str
    #: Customer or vendor (required on A/R and A/P lines).
    name: str


class QbQboParty(Struct, frozen=True):
    """A customer or vendor to import before the journal entries."""

    name: str
    email: str


class QbQboExport(Struct, frozen=True):
    """Everything QuickBooks Online imports, for one year."""

    year: int
    mode: str
    currency: str
    accounts: list[QbQboAccount]
    customers: list[QbQboParty]
    vendors: list[QbQboParty]
    lines: list[QbQboLine]
    journals: int
    #: Transactions left out, with the reason.
    skipped: list[str]


#: QuickBooks' built-in account for profit carried in from earlier years.
RETAINED_EARNINGS = "Retained Earnings"

Line = tuple[str, Decimal, str]
Journal = tuple[datetime.date, str, list[Line]]


def _party(txn: Transaction, key: str) -> str:
    value = txn.meta.get(key)
    return str(value).strip() if value else (txn.payee or "")


class _Collected:
    """Journals, carried balances and names gathered from the ledger."""

    def __init__(self) -> None:
        self.amounts = _Amounts()
        self.journals: list[Journal] = []
        self.carried: dict[str, Decimal] = defaultdict(Decimal)
        self.customers: dict[str, str] = {}
        self.vendors: dict[str, str] = {}
        self.skipped: list[str] = []

    def lines(self, txn: Transaction) -> list[Line] | None:
        """The transaction's lines, or None if an amount can't convert."""
        lines: list[Line] = []
        for posting in txn.postings:
            number = self.amounts.of(posting, txn.date)
            if number is None:
                return None
            name = ""
            if "Receivable" in posting.account:
                name = _party(txn, "customer")
                email = txn.meta.get("customer_email", "")
                self.customers.setdefault(name, str(email))
            elif "Payable" in posting.account:
                name = _party(txn, "vendor")
                self.vendors.setdefault(
                    name, str(txn.meta.get("vendor_email", ""))
                )
            lines.append((posting.account, number, name))
        return lines

    def carry(self, lines: list[Line]) -> None:
        """Add lines to the balances carried in (profit to retained)."""
        options = g.ledger.options
        pnl = {options["name_income"], options["name_expenses"]}
        for account, number, _ in lines:
            if account.split(":", 1)[0] in pnl:
                self.carried[RETAINED_EARNINGS] += number
            else:
                self.carried[account] += number


def _collect(year: int, mode: str) -> _Collected:
    first, last = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
    collected = _Collected()
    for txn in g.ledger.all_entries_by_type.Transaction:
        if txn.date > last:
            break
        lines = collected.lines(txn)
        if lines is not None and (txn.date < first or mode == "balances"):
            collected.carry(lines)
            continue
        if lines is None or sum((n for _, n, _ in lines), ZERO) != ZERO:
            collected.skipped.append(
                f"{txn.date} {txn.payee or ''} {txn.narration or ''}: "
                "amounts in another currency without a price"
            )
            continue
        if any(n for _, n, _ in lines):
            description = " - ".join(
                part for part in (txn.payee, txn.narration) if part
            )
            collected.journals.append((txn.date, description, lines))
    carried = [(a, n, "") for a, n in sorted(collected.carried.items()) if n]
    if carried:
        label = (
            f"Balances at {last.isoformat()}"
            if mode == "balances"
            else f"Opening balances carried in to {year}"
        )
        date = last if mode == "balances" else first
        collected.journals.insert(0, (date, label, carried))
    return collected


@api_endpoint
def get_qb_qbo_export(year: int, mode: str = "transactions") -> QbQboExport:
    """QuickBooks Online import files for `year`.

    `mode` "transactions" gives one journal entry per transaction (plus an
    opening entry for balances from earlier years); "balances" gives one
    entry with every balance at year end.
    """
    g.ledger.changed()
    if mode not in {"transactions", "balances"}:
        msg = "mode is transactions or balances"
        raise ValidationError(msg)
    collected = _collect(year, mode)
    used = sorted(
        {a for _, _, lines in collected.journals for a, _, _ in lines}
        - {RETAINED_EARNINGS}
    )
    names = {**qbo_names(used), RETAINED_EARNINGS: RETAINED_EARNINGS}
    rows: list[QbQboLine] = []
    for i, (date, description, lines) in enumerate(collected.journals, 1):
        rows.extend(
            QbQboLine(
                f"FB{year}-{i:04d}",
                date,
                names[account],
                max(number, ZERO),
                max(-number, ZERO),
                description,
                name,
            )
            for account, number, name in lines
            if number
        )
    return QbQboExport(
        year=year,
        mode=mode,
        currency=collected.amounts.currency,
        accounts=[QbQboAccount(names[a], *qbo_type(a), a) for a in used],
        customers=[
            QbQboParty(n, e)
            for n, e in sorted(collected.customers.items())
            if n
        ],
        vendors=[
            QbQboParty(n, e) for n, e in sorted(collected.vendors.items()) if n
        ],
        lines=rows,
        journals=len(collected.journals),
        skipped=collected.skipped,
    )
