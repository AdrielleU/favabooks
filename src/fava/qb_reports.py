"""Standard financial reports (qb-fork).

Profit and loss, balance sheet, trial balance and general ledger, laid out
like QuickBooks, Xero and FreshBooks: account trees with subtotals, the
usual computed lines (gross profit, net income, retained earnings), report
periods and column breakdowns. Amounts are in the operating currency:
postings at a price or cost use their weight; anything else is converted
at the price on the posting's date, or reported as unconverted.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from msgspec import Struct

from fava.beans import create
from fava.beans.funcs import hash_entry
from fava.context import g
from fava.core.conversion import convert_position
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.qb_docs import list_parties
from fava.qb_docs import PURCHASES
from fava.qb_reconcile import NOTE_PREFIX
from fava.qb_transactions import parse_period
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable

    from fava.beans.abc import Posting
    from fava.beans.abc import Transaction
    from fava.beans.protocols import Amount

ZERO = Decimal()
CENT = Decimal("0.01")
DAY = datetime.timedelta(days=1)
#: Expense accounts named like this are cost of goods sold.
COGS_WORDS = ("COGS", "CostOfGoods", "Cost-of-Goods", "CostOfSales")


class QbColumn(Struct, frozen=True):
    """A report column: a period (P&L) or an as-of date (start empty)."""

    label: str
    start: datetime.date | None
    end: datetime.date


class QbNode(Struct, frozen=True):
    """An account in a report tree; `amounts` include its children."""

    account: str
    name: str
    amounts: list[Decimal]
    children: list[QbNode]
    #: Amounts posted to this account itself (when it has children too).
    own: list[Decimal]


class QbBlock(Struct, frozen=True):
    """A report section (with its account tree) or a computed line."""

    #: "section" or "line".
    kind: str
    key: str
    title: str
    amounts: list[Decimal]
    node: QbNode | None = None


class QbStatement(Struct, frozen=True):
    """A financial statement."""

    title: str
    company: str
    currency: str
    columns: list[QbColumn]
    blocks: list[QbBlock]
    #: Amounts that couldn't be converted, e.g. "12.00 EUR".
    unconverted: list[str]


# --- Helpers ------------------------------------------------------------


def _roots() -> dict[str, str]:
    options = g.ledger.options
    return {
        "assets": options["name_assets"],
        "liabilities": options["name_liabilities"],
        "equity": options["name_equity"],
        "income": options["name_income"],
        "expenses": options["name_expenses"],
    }


def _currency() -> str:
    currencies = g.ledger.options["operating_currency"]
    return currencies[0] if currencies else "USD"


def _company() -> str:
    return str(g.ledger.options["title"])


def fiscal_year_start(date: datetime.date) -> datetime.date:
    """First day of the fiscal year containing `date`."""
    fye = g.ledger.fava_options.fiscal_year_end
    month = (fye.month - 1) % 12 + 1
    start = datetime.date(date.year, month, fye.day) + DAY
    if start > date:
        start = datetime.date(date.year - 1, month, fye.day) + DAY
    return start


def _cents(number: Decimal) -> Decimal:
    """Round to cents, keeping amounts already at cents unchanged."""
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and exponent >= -2:
        return number
    return number.quantize(CENT)


def _weight(posting: Posting) -> Amount:
    """A posting's weight in its transaction: at cost, price, or units."""
    units = posting.units
    cost = posting.cost
    if cost is not None and cost.number is not None:
        return create.amount(units.number * cost.number, cost.currency)
    if posting.price is not None:
        price = posting.price
        return create.amount(units.number * price.number, price.currency)
    return units


class _Amounts:
    """Operating-currency amounts of postings; records what can't convert."""

    def __init__(self) -> None:
        self.currency = _currency()
        self.unconverted: dict[str, Decimal] = defaultdict(Decimal)

    def of(self, posting: Posting, date: datetime.date) -> Decimal | None:
        weight = _weight(posting)
        if weight.currency == self.currency:
            return _cents(weight.number)
        converted = convert_position(
            create.position(weight, None), self.currency, g.ledger.prices, date
        )
        if converted.currency == self.currency:
            return _cents(converted.number)
        self.unconverted[weight.currency] += weight.number
        return None

    def notes(self) -> list[str]:
        return [
            f"{number} {currency}"
            for currency, number in sorted(self.unconverted.items())
            if number
        ]


def _postings(
    roots: Iterable[str],
) -> Iterable[tuple[Transaction, Posting]]:
    prefixes = tuple(f"{root}:" for root in roots)
    for txn in g.ledger.all_entries_by_type.Transaction:
        for posting in txn.postings:
            if posting.account.startswith(prefixes):
                yield txn, posting


def _tree(
    root: str, own: dict[str, list[Decimal]], width: int, sign: int
) -> QbNode | None:
    """The account tree under `root` from per-account amounts."""
    accounts = sorted(a for a in own if a.startswith(f"{root}:"))
    if not accounts:
        return None
    names = {root}
    for account in accounts:
        parts = account.split(":")
        names.update(":".join(parts[:i]) for i in range(1, len(parts) + 1))
    children: dict[str, list[str]] = defaultdict(list)
    for name in sorted(names):
        if name != root:
            children[name.rsplit(":", 1)[0]].append(name)

    def build(account: str) -> QbNode:
        nodes = [build(child) for child in children[account]]
        mine = [sign * n for n in own.get(account, [ZERO] * width)]
        amounts = [
            mine[i] + sum((node.amounts[i] for node in nodes), ZERO)
            for i in range(width)
        ]
        return QbNode(
            account, account.rsplit(":", 1)[-1], amounts, nodes, mine
        )

    return build(root)


def _sum(*rows: list[Decimal]) -> list[Decimal]:
    return [sum(values, ZERO) for values in zip(*rows, strict=True)]


def _neg(row: list[Decimal]) -> list[Decimal]:
    return [-n for n in row]


def _section(key: str, title: str, node: QbNode | None, width: int) -> QbBlock:
    return QbBlock(
        "section",
        key,
        title,
        node.amounts if node else [ZERO] * width,
        node,
    )


def _columns(
    start: datetime.date, end: datetime.date, by: str
) -> list[QbColumn]:
    """Columns from `start` to `end` by month, quarter or year (or one)."""
    if by not in {"month", "quarter", "year"}:
        return [QbColumn("Total", start, end)]
    step = {"month": 1, "quarter": 3, "year": 12}[by]
    columns = []
    month = start.month - 1 if by == "month" else 0
    if by == "quarter":
        month = (start.month - 1) // 3 * 3
    cursor = datetime.date(start.year, month + 1, 1)
    while cursor <= end:
        months = cursor.month - 1 + step
        following = datetime.date(
            cursor.year + months // 12, months % 12 + 1, 1
        )
        first, last = max(cursor, start), min(following - DAY, end)
        label = (
            cursor.strftime("%b %Y")
            if by == "month"
            else f"Q{(cursor.month - 1) // 3 + 1} {cursor.year}"
            if by == "quarter"
            else str(cursor.year)
        )
        columns.append(QbColumn(label, first, last))
        cursor = following
    columns.append(QbColumn("Total", start, end))
    return columns


def _add_months(date: datetime.date, months: int) -> datetime.date:
    total = date.year * 12 + date.month - 1 + months
    return datetime.date(total // 12, total % 12 + 1, 1)


def _previous(
    first: datetime.date, last: datetime.date
) -> tuple[datetime.date, datetime.date]:
    """The period before `first`..`last`.

    Whole months compare with the same number of months before (a year with
    the year before); other periods with the same number of days.
    """
    following = last + DAY
    if first.day == 1 and following.day == 1:
        months = (following.year - first.year) * 12 + following.month
        months -= first.month
        return _add_months(first, -months), first - DAY
    return first - (following - first), first - DAY


def _data_range() -> tuple[datetime.date, datetime.date]:
    txns = g.ledger.all_entries_by_type.Transaction
    if not txns:
        today = local_today()
        return today, today
    return txns[0].date, txns[-1].date


def _period(start: str, end: str) -> tuple[datetime.date, datetime.date]:
    first, last = parse_period(start, end)
    data_first, data_last = _data_range()
    first = first or data_first
    last = last or max(data_last, first)
    if last < first:
        msg = "the end date is before the start date"
        raise ValidationError(msg)
    return first, last


# --- Profit and loss ----------------------------------------------------


def _is_cogs(account: str) -> bool:
    return any(word.lower() in account.lower() for word in COGS_WORDS)


@api_endpoint
def get_qb_profit_loss(
    start: str = "", end: str = "", by: str = "total", compare: str = ""
) -> QbStatement:
    """Profit and loss for `start`..`end` (inclusive).

    `by` breaks the period into month, quarter or year columns (plus a
    total); `compare` adds the previous period of the same length.
    """
    g.ledger.changed()
    first, last = _period(start, end)
    columns = _columns(first, last, by)
    if compare and len(columns) == 1:
        columns.append(QbColumn("Previous period", *_previous(first, last)))
    width = len(columns)
    roots = _roots()
    amounts = _Amounts()
    own: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO] * width)
    for txn, posting in _postings((roots["income"], roots["expenses"])):
        hits = [
            i
            for i, c in enumerate(columns)
            if c.start is not None and c.start <= txn.date <= c.end
        ]
        if not hits:
            continue
        number = amounts.of(posting, txn.date)
        if number is None:
            continue
        for i in hits:
            own[posting.account][i] += number

    cogs_own = {a: v for a, v in own.items() if _is_cogs(a)}
    expense_own = {a: v for a, v in own.items() if not _is_cogs(a)}
    income = _tree(roots["income"], own, width, -1)
    cogs = _tree(roots["expenses"], cogs_own, width, 1)
    expenses = _tree(roots["expenses"], expense_own, width, 1)
    income_block = _section("income", "Income", income, width)
    blocks = [income_block]
    gross = income_block.amounts
    if cogs is not None:
        cogs_block = _section("cogs", "Cost of goods sold", cogs, width)
        gross = _sum(income_block.amounts, _neg(cogs_block.amounts))
        blocks += [cogs_block, QbBlock("line", "gross", "Gross profit", gross)]
    expense_block = _section("expenses", "Expenses", expenses, width)
    blocks += [
        expense_block,
        QbBlock(
            "line",
            "net",
            "Net income",
            _sum(gross, _neg(expense_block.amounts)),
        ),
    ]
    return QbStatement(
        "Profit and loss",
        _company(),
        amounts.currency,
        columns,
        blocks,
        amounts.notes(),
    )


# --- Balance sheet ------------------------------------------------------


def _as_of(value: str) -> datetime.date:
    _, date = parse_period("", value)
    return date or max(local_today(), _data_range()[1])


@api_endpoint
def get_qb_balance_sheet(as_of: str = "", compare: str = "") -> QbStatement:
    """Balance sheet at the end of `as_of`.

    Equity includes retained earnings (income less expenses before the
    fiscal year) and net income for the fiscal year so far. `compare` adds
    the same date a year earlier.
    """
    g.ledger.changed()
    date = _as_of(as_of)
    dates = [date]
    if compare:
        try:
            dates.append(date.replace(year=date.year - 1))
        except ValueError:  # 29 February
            dates.append(date.replace(year=date.year - 1, day=28))
    columns = [QbColumn(f"As of {d.isoformat()}", None, d) for d in dates]
    width = len(columns)
    roots = _roots()
    amounts = _Amounts()
    own: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO] * width)
    retained = [ZERO] * width
    net = [ZERO] * width
    for txn, posting in _postings(roots.values()):
        number = None
        for i, column in enumerate(columns):
            if txn.date > column.end:
                continue
            if number is None:
                number = amounts.of(posting, txn.date)
                if number is None:
                    break
            root = posting.account.split(":", 1)[0]
            if root in {roots["income"], roots["expenses"]}:
                if txn.date < fiscal_year_start(column.end):
                    retained[i] -= number
                else:
                    net[i] -= number
            else:
                own[posting.account][i] += number

    assets = _tree(roots["assets"], own, width, 1)
    liabilities = _tree(roots["liabilities"], own, width, -1)
    equity = _tree(roots["equity"], own, width, -1)
    extra = [
        QbNode("", "Retained earnings", retained, [], retained),
        QbNode("", "Net income", net, [], net),
    ]
    equity_children = [*(equity.children if equity else []), *extra]
    equity_own = equity.own if equity else [ZERO] * width
    equity_node = QbNode(
        roots["equity"],
        roots["equity"],
        _sum(equity_own, *(n.amounts for n in equity_children)),
        equity_children,
        equity_own,
    )
    asset_block = _section("assets", "Assets", assets, width)
    liability_block = _section(
        "liabilities", "Liabilities", liabilities, width
    )
    equity_block = _section("equity", "Equity", equity_node, width)
    return QbStatement(
        "Balance sheet",
        _company(),
        amounts.currency,
        columns,
        [
            asset_block,
            liability_block,
            equity_block,
            QbBlock(
                "line",
                "liabilities_equity",
                "Total liabilities and equity",
                _sum(liability_block.amounts, equity_block.amounts),
            ),
        ],
        amounts.notes(),
    )


# --- Trial balance ------------------------------------------------------


class QbTrialRow(Struct, frozen=True):
    """An account's debit or credit balance."""

    account: str
    debit: Decimal
    credit: Decimal


class QbTrialBalance(Struct, frozen=True):
    """Debit and credit balances; the two totals are equal."""

    company: str
    currency: str
    as_of: datetime.date
    fiscal_start: datetime.date
    rows: list[QbTrialRow]
    debit: Decimal
    credit: Decimal
    unconverted: list[str]


@api_endpoint
def get_qb_trial_balance(as_of: str = "") -> QbTrialBalance:
    """Trial balance at the end of `as_of`.

    Balance sheet accounts are balances to date; income and expense
    accounts are for the fiscal year so far, with earlier years in
    retained earnings (as if the books were closed each year end).
    """
    g.ledger.changed()
    date = _as_of(as_of)
    fiscal = fiscal_year_start(date)
    roots = _roots()
    pnl = (roots["income"], roots["expenses"])
    amounts = _Amounts()
    balances: dict[str, Decimal] = defaultdict(Decimal)
    retained_account = f"{roots['equity']}:Retained-Earnings (computed)"
    for txn, posting in _postings(roots.values()):
        if txn.date > date:
            continue
        number = amounts.of(posting, txn.date)
        if number is None:
            continue
        account = posting.account
        if account.split(":", 1)[0] in pnl and txn.date < fiscal:
            account = retained_account
        balances[account] += number
    rows = [
        QbTrialRow(account, max(n, ZERO), max(-n, ZERO))
        for account, n in sorted(balances.items())
        if n
    ]
    return QbTrialBalance(
        _company(),
        amounts.currency,
        date,
        fiscal,
        rows,
        sum((r.debit for r in rows), ZERO),
        sum((r.credit for r in rows), ZERO),
        amounts.notes(),
    )


# --- General ledger -----------------------------------------------------


class QbLedgerRow(Struct, frozen=True):
    """A posting in the general ledger."""

    entry_hash: str
    date: datetime.date
    payee: str
    narration: str
    #: The transaction's other accounts.
    split: list[str]
    amount: Decimal
    balance: Decimal


class QbLedgerAccount(Struct, frozen=True):
    """One account's activity in the period."""

    account: str
    opening: Decimal
    rows: list[QbLedgerRow]
    closing: Decimal


class QbGeneralLedger(Struct, frozen=True):
    """Every account's postings in the period, with running balances."""

    company: str
    currency: str
    start: datetime.date
    end: datetime.date
    accounts: list[QbLedgerAccount]
    unconverted: list[str]


@api_endpoint
def get_qb_general_ledger(
    start: str = "", end: str = "", account: str = ""
) -> QbGeneralLedger:
    """Postings from `start` to `end` by account (optionally one subtree).

    Opening balances for income and expense accounts start at the fiscal
    year; balance sheet accounts carry their balance to date.
    """
    g.ledger.changed()
    first, last = _period(start, end)
    fiscal = fiscal_year_start(first)
    roots = _roots()
    pnl = (roots["income"], roots["expenses"])
    amounts = _Amounts()
    opening: dict[str, Decimal] = defaultdict(Decimal)
    rows: dict[str, list[QbLedgerRow]] = defaultdict(list)
    for txn, posting in _postings(roots.values()):
        name = posting.account
        if txn.date > last or (
            account and name != account and not name.startswith(f"{account}:")
        ):
            continue
        number = amounts.of(posting, txn.date)
        if number is None:
            continue
        if txn.date < first:
            if name.split(":", 1)[0] not in pnl or txn.date >= fiscal:
                opening[name] += number
            continue
        balance = (
            rows[name][-1].balance if rows[name] else opening[name]
        ) + number
        rows[name].append(
            QbLedgerRow(
                hash_entry(txn),
                txn.date,
                txn.payee or "",
                txn.narration or "",
                list(
                    dict.fromkeys(
                        p.account for p in txn.postings if p.account != name
                    )
                ),
                number,
                balance,
            )
        )
    accounts = [
        QbLedgerAccount(
            name,
            opening[name],
            rows[name],
            rows[name][-1].balance if rows[name] else opening[name],
        )
        for name in sorted(set(rows) | {a for a, n in opening.items() if n})
    ]
    return QbGeneralLedger(
        _company(),
        amounts.currency,
        first,
        last,
        accounts,
        amounts.notes(),
    )


# --- Year-end checks ----------------------------------------------------


class QbCheck(Struct, frozen=True):
    """A year-end check before sending the books to an accountant."""

    key: str
    title: str
    ok: bool
    detail: str
    #: Report to fix it in, with its URL parameters.
    report: str
    params: dict[str, str]


def _reconciled_through(account: str) -> datetime.date | None:
    dates = [
        note.date
        for note in g.ledger.all_entries_by_type.Note
        if note.account == account and note.comment.startswith(NOTE_PREFIX)
    ]
    return max(dates, default=None)


@api_endpoint
def get_qb_year_checks(year: int) -> list[QbCheck]:
    """What to sort out before handing `year` to an accountant."""
    g.ledger.changed()
    first, last = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
    period = {"period": str(year)}
    roots = _roots()
    banks = (f"{roots['assets']}:", f"{roots['liabilities']}:")
    txns = [
        t
        for t in g.ledger.all_entries_by_type.Transaction
        if first <= t.date <= last
    ]
    review = sum(t.flag == "!" for t in txns)
    uncategorized = [
        p.account
        for t in txns
        for p in t.postings
        if p.account.endswith("Uncategorized")
    ]
    expenses = [
        t
        for t in txns
        if any(
            p.account.startswith(f"{roots['expenses']}:") for p in t.postings
        )
    ]
    no_receipt = sum(
        not any(
            key.startswith("document")
            for meta in (t.meta, *(p.meta or {} for p in t.postings))
            for key in meta
        )
        for t in expenses
    )
    active = sorted(
        {
            p.account
            for t in txns
            for p in t.postings
            if p.account.startswith(banks)
        }
        - {a for a in g.ledger.accounts if "Payable" in a or "Receivable" in a}
    )
    unreconciled = [
        a
        for a in active
        if (_reconciled_through(a) or datetime.date.min) < last
    ]
    errors = len(g.ledger.errors)
    threshold = Decimal(2000 if year >= 2026 else 600)
    contractors = [
        p.name
        for p in list_parties(PURCHASES, first.isoformat(), last.isoformat())
        if p.bank_paid >= threshold
    ]

    def plural(n: int, word: str) -> str:
        return f"{n} {word}{'' if n == 1 else 's'}"

    return [
        QbCheck(
            "review",
            "Every transaction reviewed",
            review == 0,
            f"{plural(review, 'transaction')} still marked for review."
            if review
            else "Nothing waiting in For review.",
            "qb_transactions",
            {**period, "kind": "review"},
        ),
        QbCheck(
            "uncategorized",
            "Nothing uncategorized",
            not uncategorized,
            f"{plural(len(uncategorized), 'posting')} in "
            f"{', '.join(sorted(set(uncategorized)))}."
            if uncategorized
            else "Every transaction has a category.",
            "qb_reclassify",
            {"account_name": uncategorized[0]} if uncategorized else {},
        ),
        QbCheck(
            "reconciled",
            "Bank and card accounts reconciled",
            not unreconciled,
            f"Not reconciled through {last.isoformat()}: "
            f"{', '.join(unreconciled)}."
            if unreconciled
            else "Every account is reconciled through year end.",
            "qb_reconcile",
            {"account_name": unreconciled[0]} if unreconciled else {},
        ),
        QbCheck(
            "receipts",
            "Receipts attached",
            no_receipt == 0,
            f"{plural(no_receipt, 'expense')} without a receipt."
            if no_receipt
            else "Every expense has a receipt.",
            "qb_transactions",
            {**period, "kind": "expense"},
        ),
        QbCheck(
            "errors",
            "No errors in the books",
            errors == 0,
            f"{plural(errors, 'error')} to fix."
            if errors
            else "The ledger loads without errors.",
            "errors",
            {},
        ),
        QbCheck(
            "contractors",
            "1099 contractors reviewed",
            not contractors,
            f"Paid {threshold} or more by bank or check: "
            f"{', '.join(contractors)}. Check who needs a 1099-NEC."
            if contractors
            else "No vendor was paid enough by bank or check to need a "
            "1099-NEC.",
            "qb_vendors",
            period,
        ),
    ]
