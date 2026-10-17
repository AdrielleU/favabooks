"""QuickBooks-style endpoints for the favabooks fork.

Imported at the top of application.py so the endpoints are registered on the
json_api blueprint before the module-level app is created.
"""

from __future__ import annotations

import datetime
import re
from collections import defaultdict
from decimal import Decimal
from decimal import InvalidOperation
from typing import TYPE_CHECKING

from beancount.core.data import Transaction
from msgspec import Struct

# Registers the Bank connections, Reconcile, Reports, Sales and All
# transactions endpoints.
from fava import qb_books  # noqa: F401
from fava import qb_chart  # noqa: F401
from fava import qb_connections  # noqa: F401
from fava import qb_prices  # noqa: F401
from fava import qb_qbo  # noqa: F401
from fava import qb_reconcile  # noqa: F401
from fava import qb_reports  # noqa: F401
from fava import qb_sales  # noqa: F401
from fava import qb_transactions  # noqa: F401
from fava.beans.funcs import hash_entry
from fava.context import g
from fava.core.conversion import conversion_from_str
from fava.core.file import get_entry_slice
from fava.core.inventory import CounterInventory
from fava.helpers import FavaAPIError
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.qb_importers import BANK_FORMATS
from fava.qb_importers import BankCSV
from fava.qb_importers import StripePayouts
from fava.qb_importers.stripe_payouts import REQUIRED as STRIPE_REQUIRED
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from fava.core import FavaLedger
    from fava.qb_importers import BankFormat

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

    The last day of the header's time filter if one is set; otherwise the
    latest transaction's date (or today, if that is earlier), so books whose
    data ends in an earlier year open on their last month, not an empty one.
    """
    date_range = g.filtered.date_range
    if date_range is not None:
        return date_range.end - datetime.timedelta(days=1)
    txns = g.ledger.all_entries_by_type.Transaction
    return min([local_today(), *(txn.date for txn in txns[-1:])])


def _data_years() -> list[int]:
    """Years that have transactions, newest first (none before the data)."""
    years = {txn.date.year for txn in g.ledger.all_entries_by_type.Transaction}
    return sorted(years, reverse=True)


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


class QbReviewAccount(Struct, frozen=True):
    """A bank or card account with transactions waiting for review."""

    account: str
    #: Balance in the books (all entries, regardless of filters).
    balance: Decimal
    currency: str
    to_review: int


class QbReview(Struct, frozen=True):
    """The review queue and the accounts it touches."""

    rows: list[QbReviewRow]
    accounts: list[QbReviewAccount]


class QbEditFailure(Struct, frozen=True):
    """An entry that could not be changed."""

    entry_hash: str
    error: str


class QbEditResult(Struct, frozen=True):
    """Outcome of an edit across several entries; edits are per entry."""

    changed: int
    failed: list[QbEditFailure]


@api_endpoint
def get_qb_review() -> QbReview:
    """Transactions flagged `!`, newest first, within the header filters."""
    g.ledger.changed()
    options = g.ledger.options
    roots = (f"{options['name_assets']}:", f"{options['name_liabilities']}:")
    rows: list[QbReviewRow] = []
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

    counts: dict[str, int] = defaultdict(int)
    currencies: dict[str, str] = {}
    for row in rows:
        counts[row.account] += 1
        currencies.setdefault(row.account, row.currency)
    # Keyed by currency too, so a multi-currency account sums correctly.
    balances: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for txn in g.ledger.all_entries_by_type.Transaction:
        for posting in txn.postings:
            if posting.account in counts:
                number, currency = _amount(posting.units)
                balances[posting.account, currency] += number
    accounts = [
        QbReviewAccount(
            account,
            balances[account, currencies[account]],
            currencies[account],
            n,
        )
        for account, n in sorted(counts.items())
    ]
    return QbReview(rows, accounts)


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
    entry_hashes: list[str],
    from_account: str = "",
    to_account: str = "",
    from_paid: str = "",
    to_paid: str = "",
) -> QbEditResult:
    """Accept reviewed entries (flag `!` to `*`).

    Optionally moves the category posting (from_account -> to_account)
    and the bank or card posting (from_paid -> to_paid), e.g. from an
    "Unassigned" card to the real one. All changes are one edit, since an
    entry's hash changes on save.
    """
    changes = [(from_account, to_account), (from_paid, to_paid)]
    for source_account, target in changes:
        if target:
            if not source_account:
                msg = "a from_ account is required with each to_ account"
                raise ValidationError(msg)
            _check_account(target)

    def edit(source: str) -> str:
        for source_account, target in changes:
            if target:
                source = _reclassify(source, source_account, target)
        return _PENDING_FLAG.sub(r"\1*", source, count=1)

    return _edit_entries(entry_hashes, edit)


# --- Bulk reclassify, register and exports (read-only) ---------------------

#: Most rows the bulk reclassify search returns; narrow the filters for more.
POSTINGS_LIMIT = 1000


def _amount(units: object) -> tuple[Decimal, str]:
    """Number and currency of a posting's units (always set after loading)."""
    number = getattr(units, "number", None)
    currency = getattr(units, "currency", "")
    return (number if isinstance(number, Decimal) else ZERO), currency


def _parse_decimal(value: str, name: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        msg = f"{name} must be a number"
        raise ValidationError(msg) from None


class QbPostingRow(Struct, frozen=True):
    """A posting to the searched account, for bulk reclassify."""

    entry_hash: str
    date: datetime.date
    flag: str
    payee: str
    narration: str
    amount: Decimal
    currency: str
    #: Accounts of the transaction's other postings.
    others: list[str]


class QbPostings(Struct, frozen=True):
    """Search result; `total` counts matches beyond the returned rows too."""

    rows: list[QbPostingRow]
    total: int


@api_endpoint
def get_qb_postings(
    account_name: str,
    payee: str = "",
    min_amount: str = "",
    max_amount: str = "",
) -> QbPostings:
    """Postings to exactly `account_name` in the header filters, newest first.

    `payee` matches payee or narration, case-insensitively; the amount range
    is on the absolute amount.
    """
    g.ledger.changed()
    account = account_name
    _check_account(account)
    low = _parse_decimal(min_amount, "min_amount")
    high = _parse_decimal(max_amount, "max_amount")
    needle = payee.casefold()
    rows: list[QbPostingRow] = []
    for entry in g.filtered.entries:
        if not isinstance(entry, Transaction):
            continue
        text = f"{entry.payee or ''} {entry.narration or ''}".casefold()
        if needle not in text:
            continue
        for posting in entry.postings:
            if posting.account != account:
                continue
            number, currency = _amount(posting.units)
            if (low is not None and abs(number) < low) or (
                high is not None and abs(number) > high
            ):
                continue
            rows.append(
                QbPostingRow(
                    entry_hash=hash_entry(entry),
                    date=entry.date,
                    flag=entry.flag or "",
                    payee=entry.payee or "",
                    narration=entry.narration or "",
                    amount=number,
                    currency=currency,
                    others=list(
                        dict.fromkeys(
                            p.account
                            for p in entry.postings
                            if p.account != account
                        )
                    ),
                )
            )
    rows.reverse()
    return QbPostings(rows[:POSTINGS_LIMIT], len(rows))


class QbBalance(Struct, frozen=True):
    """An amount in one currency."""

    currency: str
    amount: Decimal


class QbRegisterRow(Struct, frozen=True):
    """One posting in an account register, with the balance after it."""

    entry_hash: str
    date: datetime.date
    flag: str
    payee: str
    narration: str
    amount: Decimal
    currency: str
    balance: Decimal
    categories: list[str]


class QbRegister(Struct, frozen=True):
    """An account register; rows newest first."""

    account: str
    #: Balance before the first row when a time filter is set.
    opening: list[QbBalance]
    rows: list[QbRegisterRow]


@api_endpoint
def get_qb_register(account_name: str) -> QbRegister:
    """Register for exactly `account_name` with running balances.

    Only the time filter applies: rows are limited to its range, and the
    running balance includes everything before it.
    """
    g.ledger.changed()
    account = account_name
    _check_account(account)
    date_range = g.filtered.date_range
    balances: dict[str, Decimal] = defaultdict(Decimal)
    opening: dict[str, Decimal] = defaultdict(Decimal)
    rows: list[QbRegisterRow] = []
    for entry in g.ledger.all_entries_by_type.Transaction:
        if date_range is not None and entry.date >= date_range.end:
            break
        before = date_range is not None and entry.date < date_range.begin
        for posting in entry.postings:
            if posting.account != account:
                continue
            number, currency = _amount(posting.units)
            balances[currency] += number
            if before:
                opening[currency] += number
                continue
            rows.append(
                QbRegisterRow(
                    entry_hash=hash_entry(entry),
                    date=entry.date,
                    flag=entry.flag or "",
                    payee=entry.payee or "",
                    narration=entry.narration or "",
                    amount=number,
                    currency=currency,
                    balance=balances[currency],
                    categories=list(
                        dict.fromkeys(
                            p.account
                            for p in entry.postings
                            if p.account != account
                        )
                    ),
                )
            )
    rows.reverse()
    return QbRegister(
        account,
        [QbBalance(c, n) for c, n in sorted(opening.items()) if n],
        rows,
    )


class QbExports(Struct, frozen=True):
    """The year's report queries and the years there is data for."""

    year: int
    years: list[int]
    exports: list[QbExport]


class QbExport(Struct, frozen=True):
    """A report download: run `query` via download-query as CSV or XLSX."""

    key: str
    title: str
    description: str
    query: str


@api_endpoint
def get_qb_exports(year: int = 0) -> QbExports:
    """BQL for the year-end reports an accountant asks for.

    `year` defaults to the latest year with transactions.

    Dates are in the query itself, because download-query ignores the
    header filters (upstream issue #1882).
    """
    years = _data_years()
    year = year or next(iter(years), local_today().year)
    options = g.ledger.options
    begin = datetime.date(year, 1, 1)
    end = datetime.date(year + 1, 1, 1)
    year_end = end - datetime.timedelta(days=1)
    period = f"FROM OPEN ON {begin} CLOSE ON {end}"
    pnl = "|".join((options["name_income"], options["name_expenses"]))
    bs = "|".join(
        (
            options["name_assets"],
            options["name_liabilities"],
            options["name_equity"],
        )
    )
    exports = [
        QbExport(
            "trial_balance",
            "Trial balance",
            f"Every account's balance for {year}.",
            "SELECT account, sum(cost(position)) AS balance "
            f"{period} GROUP BY account ORDER BY account",
        ),
        QbExport(
            "profit_loss",
            "Profit and loss",
            f"Income and expenses by account for {year}.",
            "SELECT account, sum(cost(position)) AS amount "
            f"{period} WHERE account ~ '^({pnl}):' "
            "GROUP BY account ORDER BY account",
        ),
        QbExport(
            "balance_sheet",
            "Balance sheet",
            f"Assets, liabilities and equity at {year_end}.",
            # Only an int year and Beancount's account-root option names are
            # interpolated, and BQL is a read-only query over the ledger.
            "SELECT account, sum(cost(position)) AS balance "  # noqa: S608
            f"FROM CLOSE ON {end} CLEAR WHERE account ~ '^({bs}):' "
            "GROUP BY account ORDER BY account",
        ),
        QbExport(
            "general_ledger",
            "General ledger",
            f"Every posting in {year}, by account and date.",
            "SELECT date, flag, account, payee, narration, "
            f"cost(position) AS amount {period} ORDER BY account, date",
        ),
    ]
    return QbExports(year, years, exports)


# --- Bank formats and configured importers ---------------------------------


class QbBankFormat(Struct, frozen=True):
    """A CSV layout the importers recognise (several can share a key)."""

    key: str
    bank: str
    kind: str
    download: str
    #: Header columns that identify the file; empty for header-less files.
    columns: list[str]
    amounts: str
    has_balance: bool
    confidence: str


class QbImporter(Struct, frozen=True):
    """An importer in this ledger's import config."""

    name: str
    key: str
    account: str


class QbBankImports(Struct, frozen=True):
    """Supported formats and how this ledger's imports are set up."""

    formats: list[QbBankFormat]
    importers: list[QbImporter]
    config_file: str
    import_dirs: list[str]
    errors: list[str]


def _describe_amounts(fmt: BankFormat) -> str:
    if fmt.debit and fmt.credit:
        return f'"{fmt.debit}" is money out, "{fmt.credit}" money in'
    if fmt.sign_column:
        return f'"{fmt.amount}" with "{fmt.sign_column}" giving the direction'
    if fmt.negate:
        return f'"{fmt.amount}", purchases positive (flipped on import)'
    return f'"{fmt.amount}", negative is money out'


@api_endpoint
def get_qb_bank_formats() -> QbBankImports:
    """Bank and Stripe formats, plus the ledger's configured importers."""
    ledger = g.ledger
    formats = [
        QbBankFormat(
            key=fmt.key,
            bank=fmt.bank,
            kind=fmt.kind,
            download=fmt.download,
            columns=list(fmt.columns),
            amounts=_describe_amounts(fmt),
            has_balance=fmt.balance is not None,
            confidence=fmt.confidence,
        )
        for fmt in BANK_FORMATS
    ]
    formats.append(
        QbBankFormat(
            key="stripe_payouts",
            bank="Stripe",
            kind="Payments (payout reconciliation)",
            download="Reports → Payouts reconciliation → Download → Itemized",
            columns=sorted(STRIPE_REQUIRED),
            amounts='"gross", "fee" and "net" per balance transaction',
            has_balance=False,
            confidence="verified",
        )
    )
    importers = []
    config = ledger.ingest.loaded_config
    for wrapped in config.importers.values() if config else ():
        importer = wrapped.importer
        if isinstance(importer, BankCSV):
            key, account = importer.key, importer.account("")
        elif isinstance(importer, StripePayouts):
            key, account = "stripe_payouts", importer.account("")
        else:
            key, account = "", ""
        importers.append(QbImporter(importer.name, key, account))
    module_path = ledger.ingest.module_path
    return QbBankImports(
        formats=formats,
        importers=importers,
        config_file=str(module_path) if module_path else "",
        import_dirs=[
            str(ledger.join_path(d)) for d in ledger.fava_options.import_dirs
        ],
        errors=[error.message for error in ledger.ingest.errors],
    )
