"""One beangulp importer for many banks' CSV downloads, driven by formats."""

from __future__ import annotations

import csv
import datetime
import re
from collections import defaultdict
from decimal import Decimal
from decimal import InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from beancount.core import data
from beancount.core.amount import Amount
from beangulp.importer import Importer

from fava.qb_importers.formats import BANK_FORMATS_BY_KEY
from fava.qb_importers.formats import BankFormat

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

#: How many lines to search for the header row (some banks add a summary).
HEADER_SEARCH_LINES = 30
#: How far apart (days) a duplicate's date may be, e.g. posted vs. made.
DUPLICATE_DAYS = 2


def _norm(text: str) -> str:
    return text.strip().casefold()


def parse_amount(text: str) -> Decimal | None:
    """Parse "$1,234.56", "-12.00", "(12.00)" or "" (None)."""
    cleaned = (
        text.strip()
        .replace("$", "")
        .replace(",", "")
        .replace("\N{MINUS SIGN}", "-")
        .replace(" ", "")
    )
    if not cleaned:
        return None
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    try:
        number = Decimal(cleaned.strip("()"))
    except InvalidOperation:
        return None
    return -number if negative else number


def parse_date(text: str, formats: Sequence[str]) -> datetime.date | None:
    """Parse a date in the first of `formats` that fits."""
    text = text.strip()
    for fmt in formats:
        try:
            return datetime.datetime.strptime(text, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None


class Row:
    """One CSV row by (case-insensitive) column name, with its line number."""

    def __init__(
        self, lineno: int, header: list[str], cells: list[str]
    ) -> None:
        self.lineno = lineno
        self.cells = dict(zip(header, cells, strict=False))

    def get(self, column: str | None) -> str:
        """Cell text for `column` (empty if the column is missing)."""
        return self.cells.get(_norm(column), "").strip() if column else ""


def read_rows(path: str, fmt: BankFormat) -> list[Row] | None:
    """The data rows of `path` if it is in layout `fmt`, else None."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    lines = list(csv.reader(text.splitlines()))
    if fmt.columns:
        required = {_norm(c) for c in fmt.columns}
        absent = {_norm(c) for c in fmt.absent}
        for index, cells in enumerate(lines[:HEADER_SEARCH_LINES]):
            header = [_norm(cell) for cell in cells]
            if required.issubset(header) and not absent.intersection(header):
                body = lines[index + 1 :]
                start = index + 2
                break
        else:
            return None
    else:
        header = [_norm(c) for c in fmt.positional]
        body = lines
        start = 1
    rows = [
        Row(start + offset, header, cells)
        for offset, cells in enumerate(body)
        if any(cell.strip() for cell in cells)
    ]
    if not fmt.columns and not (rows and _looks_positional(rows[0], fmt)):
        return None
    return rows


def _looks_positional(row: Row, fmt: BankFormat) -> bool:
    """Whether a header-less first row has this layout's shape."""
    return (
        len(row.cells) == len(fmt.positional)
        and parse_date(row.get(fmt.date), fmt.date_formats) is not None
        and parse_amount(row.get(fmt.amount)) is not None
    )


def row_amount(row: Row, fmt: BankFormat) -> Decimal | None:
    """The row's amount, negative for money out (or a card purchase)."""
    if fmt.amount:
        number = parse_amount(row.get(fmt.amount))
        if number is None:
            return None
        if fmt.sign_column:
            out = row.get(fmt.sign_column).casefold() in fmt.out_values
            return -abs(number) if out else abs(number)
        return -number if fmt.negate else number
    debit = parse_amount(row.get(fmt.debit)) or Decimal()
    credit = parse_amount(row.get(fmt.credit)) or Decimal()
    if not debit and not credit:
        return None
    return abs(credit) - abs(debit)


class BankCSV(Importer):
    """Import a bank or card CSV download.

    Args:
        format: A key of `BANK_FORMATS` (e.g. "chase_checking"), or your own
            `BankFormat` for a bank that isn't listed.
        account: The Beancount account the file belongs to.
        currency: Currency of the amounts.
        filename: Optional regex the file name must match, to tell apart two
            accounts at the same bank (e.g. their last four digits).
        uncategorized: The other leg of every transaction, to be fixed in
            the review queue (or predicted by smart_importer).
        skip: Regexes; rows whose description matches are left out (e.g.
            Stripe payouts, which the Stripe importer books).
        flag: Flag for new transactions; "!" puts them in For review.
        balance: Add a balance assertion from the running-balance column.
    """

    def __init__(
        self,
        format: str | BankFormat,  # noqa: A002
        account: str,
        *,
        currency: str = "USD",
        filename: str | None = None,
        uncategorized: str = "Expenses:Uncategorized",
        skip: Sequence[str] = (),
        flag: str = "!",
        balance: bool = True,
    ) -> None:
        if isinstance(format, BankFormat):
            self.layouts: tuple[BankFormat, ...] = (format,)
        elif format in BANK_FORMATS_BY_KEY:
            self.layouts = BANK_FORMATS_BY_KEY[format]
        else:
            known = ", ".join(sorted(BANK_FORMATS_BY_KEY))
            msg = f"Unknown bank format {format!r}. Known formats: {known}"
            raise ValueError(msg)
        self.key = self.layouts[0].key
        self._account = account
        self.currency = currency
        self.filename_re = (
            re.compile(filename, re.IGNORECASE) if filename else None
        )
        self.uncategorized = uncategorized
        self.skip = [re.compile(pattern, re.IGNORECASE) for pattern in skip]
        self.flag = flag
        self.balance = balance

    @property
    def name(self) -> str:
        """Unique per format, account and file-name filter."""
        base = f"{self.key}:{self._account}"
        return (
            f"{base}:{self.filename_re.pattern}" if self.filename_re else base
        )

    def account(self, filepath: str) -> str:  # noqa: ARG002
        """The account this importer books to."""
        return self._account

    def _read(self, filepath: str) -> tuple[BankFormat, list[Row]] | None:
        for fmt in self.layouts:
            rows = read_rows(filepath, fmt)
            if rows is not None:
                return fmt, rows
        return None

    def identify(self, filepath: str) -> bool:
        """A .csv (or .txt) file whose name and header fit this importer."""
        path = Path(filepath)
        if path.suffix.lower() not in {".csv", ".txt"}:
            return False
        if self.filename_re and not self.filename_re.search(path.name):
            return False
        return self._read(filepath) is not None

    def date(self, filepath: str) -> datetime.date | None:
        """The latest transaction date in the file."""
        dates = [txn.date for txn, _ in self._transactions(filepath)]
        return max(dates, default=None)

    def _transactions(
        self, filepath: str
    ) -> list[tuple[data.Transaction, Decimal | None]]:
        """Transactions with the running balance after each, if given."""
        found = self._read(filepath)
        if found is None:
            return []
        fmt, rows = found
        txns = []
        for row in rows:
            day = parse_date(row.get(fmt.date), fmt.date_formats)
            number = row_amount(row, fmt)
            description = " ".join(row.get(fmt.description).split())
            if day is None or number is None:
                continue
            if (
                fmt.status
                and row.get(fmt.status).casefold() in fmt.skip_status
            ):
                continue
            if any(pattern.search(description) for pattern in self.skip):
                continue
            memo = " ".join(part for c in fmt.memo if (part := row.get(c)))
            txn = data.Transaction(
                data.new_metadata(filepath, row.lineno),
                day,
                self.flag,
                description or None,
                memo,
                data.EMPTY_SET,
                data.EMPTY_SET,
                [
                    data.Posting(
                        self._account,
                        Amount(number, self.currency),
                        None,
                        None,
                        None,
                        None,
                    ),
                    data.Posting(
                        self.uncategorized, None, None, None, None, None
                    ),
                ],
            )
            txns.append((txn, parse_amount(row.get(fmt.balance))))
        return txns

    def deduplicate(
        self, entries: data.Entries, existing: data.Entries
    ) -> None:
        """Mark entries already in the ledger.

        A transaction is a duplicate when an existing one posts the exact
        same amount to this account within DUPLICATE_DAYS; each existing
        transaction matches once. (beangulp's default allows 5% amount
        differences, which wrongly drops small card charges.) A balance is
        a duplicate when the same assertion exists.
        """
        dates: dict[Amount, list[datetime.date]] = defaultdict(list)
        balances = set()
        for entry in existing:
            if isinstance(entry, data.Transaction):
                for posting in entry.postings:
                    if posting.account == self._account and posting.units:
                        dates[posting.units].append(entry.date)
            elif isinstance(entry, data.Balance):
                balances.add((entry.date, entry.account, entry.amount))
        window = datetime.timedelta(days=DUPLICATE_DAYS)
        for entry in entries:
            if not isinstance(entry, data.Transaction):  # statement balance
                duplicate = (
                    entry.date,
                    getattr(entry, "account", ""),
                    getattr(entry, "amount", None),
                ) in balances
            else:
                units = entry.postings[0].units
                candidates = dates.get(units, []) if units else []
                match = next(
                    (d for d in candidates if abs(d - entry.date) <= window),
                    None,
                )
                duplicate = match is not None
                if match is not None:
                    candidates.remove(match)
            if duplicate:
                entry.meta["__duplicate__"] = True

    def extract(
        self,
        filepath: str,
        existing: data.Entries,  # noqa: ARG002
    ) -> data.Entries:
        """Transactions flagged for review, plus a statement balance."""
        txns = self._transactions(filepath)
        entries: data.Entries = [txn for txn, _ in txns]
        balances = [(txn, bal) for txn, bal in txns if bal is not None]
        if self.balance and balances:
            # Files are newest-first or oldest-first; in date order, the
            # last row with a balance gives the closing balance.
            if balances[0][0].date > balances[-1][0].date:
                balances.reverse()
            txn, amount = balances[-1]
            entries.append(
                data.Balance(
                    data.new_metadata(filepath, txn.meta["lineno"]),
                    txn.date + datetime.timedelta(days=1),
                    self._account,
                    Amount(amount, self.currency),
                    None,
                    None,
                )
            )
        return entries
