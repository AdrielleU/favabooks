"""All transactions and category totals (qb-fork).

A QuickBooks-style list of transactions: each one classified as an expense,
income, a transfer between bank and card accounts, or other, with its
categories, the account it was paid with, and any receipts linked through
`document` metadata.
"""

from __future__ import annotations

import datetime
from collections import Counter
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from msgspec import Struct

from fava.beans.abc import Transaction
from fava.beans.funcs import hash_entry
from fava.context import g
from fava.json_api import api_endpoint
from fava.json_api import ValidationError

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Posting

#: Most rows returned; `total` says how many matched.
TRANSACTIONS_LIMIT = 1000
KINDS = ("expense", "income", "transfer", "other")
#: Flags of entries the time filter adds (opening balances, conversions).
SYNTHETIC_FLAGS = {"S", "C"}
ZERO = Decimal()


class QbReceipt(Struct, frozen=True):
    """A document linked to a transaction."""

    name: str
    #: Full path of the matching Document entry ("" if not found).
    filename: str


class QbTransactionRow(Struct, frozen=True):
    """One transaction, summarised."""

    entry_hash: str
    date: datetime.date
    flag: str
    kind: str
    payee: str
    narration: str
    #: Income and expense accounts (other accounts for transfers).
    categories: list[str]
    #: Bank and card accounts.
    paid_with: list[str]
    #: Positive size of the transaction.
    amount: Decimal
    currency: str
    receipts: list[QbReceipt]
    tags: list[str]


def parse_period(
    start: str, end: str
) -> tuple[datetime.date | None, datetime.date | None]:
    """Inclusive start and end dates ("" for open-ended)."""
    try:
        return (
            datetime.date.fromisoformat(start) if start else None,
            datetime.date.fromisoformat(end) if end else None,
        )
    except ValueError:
        msg = "dates look like 2026-01-31"
        raise ValidationError(msg) from None


def in_period(
    date: datetime.date | None,
    period: tuple[datetime.date | None, datetime.date | None],
) -> bool:
    """Whether `date` is in the inclusive (start, end) period."""
    start, end = period
    return date is not None and (
        (start is None or date >= start) and (end is None or date <= end)
    )


class QbTransactions(Struct, frozen=True):
    """Matching transactions (newest first) and counts per kind."""

    rows: list[QbTransactionRow]
    total: int
    #: Counts per kind before the kind filter, plus "all" and "review".
    counts: dict[str, int]
    #: First day of each month with transactions (for the date picker).
    months: list[datetime.date]


def _roots() -> dict[str, str]:
    options = g.ledger.options
    return {
        "assets": options["name_assets"],
        "liabilities": options["name_liabilities"],
        "income": options["name_income"],
        "expenses": options["name_expenses"],
    }


def _root(account: str) -> str:
    return account.split(":", 1)[0]


def _units(posting: Posting) -> tuple[Decimal, str]:
    units = posting.units
    # Booking fills in every posting's units of a loaded ledger.
    if units is None or units.number is None:  # pragma: no cover
        return ZERO, ""
    return units.number, units.currency


def _classify(
    txn: Transaction, roots: dict[str, str]
) -> tuple[str, Decimal, str, list[str], list[str]]:
    """Kind, amount, currency, categories and bank accounts of `txn`.

    Income wins over expenses (a sale with a processing fee is income);
    amounts are in the first currency seen for the deciding root.
    """
    banks = (roots["assets"], roots["liabilities"])
    by_root: dict[str, dict[str, Decimal]] = defaultdict(dict)
    positive: dict[str, Decimal] = {}
    categories: list[str] = []
    paid_with: list[str] = []
    for posting in txn.postings:
        root = _root(posting.account)
        target = paid_with if root in banks else categories
        if posting.account not in target:
            target.append(posting.account)
        number, currency = _units(posting)
        sums = by_root[root]
        sums[currency] = sums.get(currency, ZERO) + number
        if number > 0:
            positive[currency] = positive.get(currency, ZERO) + number
    for kind, root, sign in (
        ("income", roots["income"], -1),
        ("expense", roots["expenses"], 1),
    ):
        if root in by_root:
            currency, number = next(iter(by_root[root].items()))
            return kind, sign * number, currency, categories, paid_with
    kind = "transfer" if not categories and paid_with else "other"
    currency, number = next(iter(positive.items()), ("", ZERO))
    return kind, number, currency, categories, paid_with


def documents_by_name() -> dict[str, list[str]]:
    """Full paths of the ledger's Document entries by file name."""
    documents: dict[str, list[str]] = defaultdict(list)
    for doc in g.ledger.all_entries_by_type.Document:
        documents[Path(doc.filename).name].append(doc.filename)
    return documents


def receipts_of(
    txn: Transaction, documents: dict[str, list[str]]
) -> list[QbReceipt]:
    """Documents named in `document*` metadata, matched to Document entries."""
    names = [
        value
        for meta in (txn.meta, *(p.meta for p in txn.postings))
        if meta
        for key, value in meta.items()
        if key.startswith("document") and isinstance(value, str)
    ]
    base = Path(str(txn.meta.get("filename", ""))).parent
    receipts = []
    for name in dict.fromkeys(names):
        full = str((base / name).resolve())
        matches = documents.get(Path(name).name, [])
        filename = full if full in matches else (matches[0] if matches else "")
        receipts.append(QbReceipt(Path(name).name, filename))
    return receipts


@api_endpoint
def get_qb_transactions(
    search: str = "", kind: str = "", start: str = "", end: str = ""
) -> QbTransactions:
    """Transactions in the header filters, newest first.

    `search` matches payee, description, accounts, tags and the amount;
    `kind` is one of expense, income, transfer, other or review (flagged !);
    `start` and `end` limit the dates (inclusive).
    """
    g.ledger.changed()
    period = parse_period(start, end)
    months: set[datetime.date] = set()
    roots = _roots()
    documents = documents_by_name()
    needle = search.strip().casefold()
    counts: Counter[str] = Counter()
    rows: list[QbTransactionRow] = []
    for entry in g.filtered.entries:
        if not isinstance(entry, Transaction) or entry.flag in SYNTHETIC_FLAGS:
            continue
        months.add(entry.date.replace(day=1))
        if not in_period(entry.date, period):
            continue
        txn_kind, amount, currency, categories, paid_with = _classify(
            entry, roots
        )
        tags = sorted(entry.tags or ())
        if needle:
            text = " ".join(
                [
                    entry.payee or "",
                    entry.narration or "",
                    *categories,
                    *paid_with,
                    *tags,
                    f"{amount:.2f}",
                ]
            ).casefold()
            if needle not in text:
                continue
        review = entry.flag == "!"
        counts["all"] += 1
        counts[txn_kind] += 1
        counts["review"] += review
        if kind and kind != txn_kind and not (kind == "review" and review):
            continue
        rows.append(
            QbTransactionRow(
                entry_hash=hash_entry(entry),
                date=entry.date,
                flag=entry.flag or "",
                kind=txn_kind,
                payee=entry.payee or "",
                narration=entry.narration or "",
                categories=categories,
                paid_with=paid_with,
                amount=amount,
                currency=currency,
                receipts=receipts_of(entry, documents),
                tags=tags,
            )
        )
    rows.reverse()
    return QbTransactions(
        rows[:TRANSACTIONS_LIMIT],
        len(rows),
        {name: counts[name] for name in ("all", *KINDS, "review")},
        sorted(months),
    )


class QbCategory(Struct, frozen=True):
    """An income or expense account with its activity in the filters."""

    account: str
    count: int
    total: Decimal
    currency: str


@api_endpoint
def get_qb_categories() -> list[QbCategory]:
    """Income and expense accounts used in the header filters.

    Expenses first, then income; each by most transactions first.
    """
    g.ledger.changed()
    roots = _roots()
    wanted = (roots["expenses"], roots["income"])
    counts: Counter[str] = Counter()
    totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    currencies: dict[str, Counter[str]] = defaultdict(Counter)
    for entry in g.filtered.entries:
        if not isinstance(entry, Transaction) or entry.flag in SYNTHETIC_FLAGS:
            continue
        seen = set()
        for posting in entry.postings:
            if _root(posting.account) not in wanted:
                continue
            seen.add(posting.account)
            number, currency = _units(posting)
            totals[posting.account, currency] += number
            currencies[posting.account][currency] += 1
        counts.update(seen)
    categories = []
    for account, count in counts.items():
        currency = currencies[account].most_common(1)[0][0]
        total = totals[account, currency]
        categories.append(
            QbCategory(
                account,
                count,
                -total if _root(account) == roots["income"] else total,
                currency,
            )
        )
    categories.sort(
        key=lambda c: (
            _root(c.account) != roots["expenses"],
            -c.count,
            c.account,
        )
    )
    return categories
