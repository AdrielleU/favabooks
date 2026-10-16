"""Expense spreadsheets (CSV) with receipts, like QuickBooks' file upload.

`ExpenseCSV` maps a spreadsheet's columns (date, payee, amount, category,
payment method, receipt file, ...) to transactions: the category's expense
account against the card or account that paid. `ExpenseReceipts` files the
receipts the spreadsheet names under their expense account, so each
transaction's `document:` metadata finds its receipt (Fava's Import page,
"Move").

Example importers/config.py::

    from fava.qb_importers import ExpenseColumns, ExpenseCSV, ExpenseReceipts

    expenses = ExpenseCSV(
        columns=ExpenseColumns(
            narration="Product/Plan",
            paid_with="Card (last 4)",
            receipt="Receipt File",
            meta={"invoice": "Invoice #"},
        ),
        categories={"Software & Subscriptions": "Expenses:Software"},
    )
    CONFIG = [expenses, ExpenseReceipts(expenses, ["inbox/expenses.csv"])]
"""

from __future__ import annotations

import csv
import datetime
import re
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING

from beancount.core import data
from beancount.core.amount import Amount
from beangulp.importer import Importer

from fava.qb_importers.bank_csv import parse_amount
from fava.qb_importers.bank_csv import parse_date
from fava.qb_importers.formats import ISO_DATE
from fava.qb_importers.formats import US_DATE

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence


@dataclass(frozen=True)
class ExpenseColumns:
    """Which spreadsheet column holds what. Only date, payee, amount needed."""

    date: str = "Date"
    payee: str = "Vendor"
    amount: str = "Amount"
    narration: str | None = None
    category: str | None = "Category"
    #: Card last four digits, or a payment method such as "PayPal".
    paid_with: str | None = None
    #: File name of the receipt (PDF, image) for the row.
    receipt: str | None = None
    #: A column whose value becomes a tag, e.g. a venture or class.
    tag: str | None = None
    #: Extra metadata: metadata key -> column.
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpenseRow:
    """One spreadsheet row, as booked."""

    lineno: int
    date: datetime.date
    payee: str
    narration: str
    amount: Amount
    account: str
    paid_with: str
    needs_review: bool
    receipt: str
    tag: str
    meta: dict[str, str]


def _tag(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


class ExpenseCSV(Importer):
    """Book each row of an expense spreadsheet.

    Args:
        name: Importer name (unique in the import config).
        columns: Which column holds what.
        categories: Category cell -> expense account.
        uncategorized: Account for categories not in `categories`.
        payment_methods: Payment cell (case-insensitive substring, e.g.
            "paypal") -> account.
        card_account: Account for a cell with card digits; "{}" becomes
            the last four digits.
        unassigned: Account when the payment method is blank or unknown.
        currency: Currency of the amounts.
        file_under: Account whose documents folder keeps the spreadsheet
            after import; defaults to `uncategorized`. (Fava needs a real
            account here, so not just "Expenses".)
        flag: Flag of complete rows; rows with an unknown category or
            payment method get "!" so they show in For review.
    """

    def __init__(  # noqa: PLR0913
        self,
        name: str = "expense_csv",
        *,
        columns: ExpenseColumns | None = None,
        categories: dict[str, str] | None = None,
        uncategorized: str = "Expenses:Uncategorized",
        payment_methods: dict[str, str] | None = None,
        card_account: str = "Liabilities:CreditCard:Card-{}",
        unassigned: str = "Liabilities:CreditCard:Unassigned",
        currency: str = "USD",
        file_under: str | None = None,
        flag: str = "*",
    ) -> None:
        self._name = name
        self.columns = columns or ExpenseColumns()
        self.categories = categories or {}
        self.uncategorized = uncategorized
        self.payment_methods = {
            k.casefold(): v for k, v in (payment_methods or {}).items()
        }
        self.card_account = card_account
        self.unassigned = unassigned
        self.currency = currency
        self.file_under = file_under or uncategorized
        self.flag = flag

    @property
    def name(self) -> str:
        """The importer's name."""
        return self._name

    def account(self, filepath: str) -> str:  # noqa: ARG002
        """Where the spreadsheet is filed (it spans many accounts)."""
        return self.file_under

    def _payment(self, cell: str) -> tuple[str, bool]:
        """Account for a payment cell, and whether it needs review."""
        folded = cell.casefold()
        for key, account in self.payment_methods.items():
            if key in folded:
                return account, False
        digits = re.search(r"\d{4}", cell)
        if digits is None:
            return self.unassigned, True
        # "1234 + gift card": a split payment, booked to the card; check it.
        return self.card_account.format(digits.group(0)), "+" in cell

    def rows(self, filepath: str) -> list[ExpenseRow] | None:
        """The booked rows, or None if `filepath` isn't this spreadsheet."""
        path = Path(filepath)
        if path.suffix.lower() != ".csv":
            return None
        cols = self.columns
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            required = {cols.date, cols.payee, cols.amount}
            if not required.issubset(reader.fieldnames or ()):
                return None
            raw = [
                (
                    reader.line_num,
                    {k: (v or "").strip() for k, v in r.items() if k},
                )
                for r in reader
            ]
        rows = []
        for lineno, cell in raw:
            day = parse_date(cell[cols.date], (*ISO_DATE, *US_DATE))
            number = parse_amount(cell[cols.amount])
            if day is None or number is None:
                continue  # a TOTAL line, a note, or a blank row
            category = cell.get(cols.category or "", "")
            account = self.categories.get(category, self.uncategorized)
            paid_with, review = self._payment(
                cell.get(cols.paid_with or "", "")
            )
            rows.append(
                ExpenseRow(
                    lineno=lineno,
                    date=day,
                    payee=cell[cols.payee],
                    narration=cell.get(cols.narration or "", ""),
                    amount=Amount(number, self.currency),
                    account=account,
                    paid_with=paid_with,
                    needs_review=review or account == self.uncategorized,
                    receipt=cell.get(cols.receipt or "", "").strip(),
                    tag=_tag(cell.get(cols.tag or "", "")),
                    meta={
                        k: cell[c] for k, c in cols.meta.items() if cell.get(c)
                    },
                )
            )
        return rows

    def identify(self, filepath: str) -> bool:
        """A CSV with this spreadsheet's date, payee and amount columns."""
        return self.rows(filepath) is not None

    def date(self, filepath: str) -> datetime.date | None:
        """The latest row's date."""
        return max(
            (row.date for row in self.rows(filepath) or []), default=None
        )

    def extract(
        self,
        filepath: str,
        existing: data.Entries,  # noqa: ARG002
    ) -> data.Entries:
        """One transaction per row, linked to its receipt."""
        entries: data.Entries = []
        for row in self.rows(filepath) or []:
            meta = data.new_metadata(filepath, row.lineno)
            meta.update(row.meta)
            if row.receipt:
                meta["document"] = receipt_name(row)
            entries.append(
                data.Transaction(
                    meta,
                    row.date,
                    "!" if row.needs_review else self.flag,
                    row.payee or None,
                    row.narration,
                    frozenset({row.tag}) if row.tag else data.EMPTY_SET,
                    data.EMPTY_SET,
                    [
                        data.Posting(
                            row.account, row.amount, None, None, None, None
                        ),
                        data.Posting(
                            row.paid_with, -row.amount, None, None, None, None
                        ),
                    ],
                )
            )
        return entries


def receipt_name(row: ExpenseRow) -> str:
    """Where a receipt is filed: "<date>.<file name>" (Fava keeps it as is)."""
    return f"{row.date.isoformat()}.{row.receipt}"


class ExpenseReceipts(Importer):
    r"""File the receipts that expense spreadsheets name.

    Args:
        expenses: The ExpenseCSV that reads the spreadsheets.
        spreadsheets: Paths of the spreadsheets listing the receipts.
        also: Other files to file: (regex on the file name, account). The
            regex's named groups "year" and optional "month" give the date,
            e.g. r"cloud_itemized_(?P<year>\\d{4})_(?P<month>\\d{2})\\.csv".
    """

    def __init__(
        self,
        expenses: ExpenseCSV,
        spreadsheets: Sequence[str],
        also: Sequence[tuple[str, str]] = (),
    ) -> None:
        self.expenses = expenses
        self.spreadsheets = list(spreadsheets)
        self.also = [
            (re.compile(pattern), account) for pattern, account in also
        ]

    @property
    def name(self) -> str:
        """Unique next to the ExpenseCSV it belongs to."""
        return f"{self.expenses.name}:receipts"

    def _find(self, filepath: str) -> tuple[str, datetime.date, str] | None:
        """(account, date, file name) for a receipt, if it is one."""
        name = Path(filepath).name.strip()
        for sheet in self.spreadsheets:
            for row in self.expenses.rows(sheet) or []:
                if row.receipt == name:
                    return row.account, row.date, name
        for pattern, account in self.also:
            match = pattern.fullmatch(name)
            if match:
                year = int(match["year"])
                month = int(match.groupdict().get("month") or 12)
                return account, datetime.date(year, month, 1), name
        return None

    def identify(self, filepath: str) -> bool:
        """A file one of the spreadsheets lists (or that `also` matches)."""
        return self._find(filepath) is not None

    def account(self, filepath: str) -> str:
        """The expense account of the receipt's row."""
        found = self._find(filepath)
        return found[0] if found else self.expenses.uncategorized

    def date(self, filepath: str) -> datetime.date | None:
        """The receipt's row date."""
        found = self._find(filepath)
        return found[1] if found else None

    def filename(self, filepath: str) -> str | None:
        """Return "<date>.<name>", matching the transaction's `document:`."""
        found = self._find(filepath)
        return f"{found[1].isoformat()}.{found[2]}" if found else None

    def extract(
        self,
        filepath: str,  # noqa: ARG002
        existing: data.Entries,  # noqa: ARG002
    ) -> data.Entries:
        """Receipts are filed, not booked."""
        return []
