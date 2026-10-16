from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

from beancount.core import data
from beancount.core.amount import Amount

from fava.qb_importers import ExpenseColumns
from fava.qb_importers import ExpenseCSV
from fava.qb_importers import ExpenseReceipts

SHEET = Path(__file__).parent / "qb_data" / "imports" / "expenses.csv"


def importer() -> ExpenseCSV:
    return ExpenseCSV(
        "my_expenses",
        columns=ExpenseColumns(
            narration="Product/Plan",
            paid_with="Card (last 4)",
            receipt="Receipt File",
            tag="Business / Venture",
            meta={"invoice": "Invoice #"},
        ),
        categories={
            "Cloud": "Expenses:Cloud",
            "Office": "Expenses:Office",
            "Equipment": "Expenses:Equipment",
        },
        payment_methods={"PayPal": "Liabilities:PayPal"},
    )


def test_expense_csv() -> None:
    imp = importer()
    path = str(SHEET)
    assert imp.name == "my_expenses"
    assert imp.identify(path)
    assert imp.account(path) == "Expenses"
    assert imp.date(path) == datetime.date(2026, 2, 3)

    entries = imp.extract(path, [])
    txns = [e for e in entries if isinstance(e, data.Transaction)]
    assert len(txns) == len(entries) == 4  # TOTAL and bad rows skipped
    summary = [
        (
            t.flag,
            t.payee,
            t.postings[0].account,
            t.postings[1].account,
            sorted(t.tags),
        )
        for t in txns
    ]
    assert summary == [
        (
            "*",
            "Cloud Co",
            "Expenses:Cloud",
            "Liabilities:CreditCard:Card-4242",
            ["sample-studio"],
        ),
        # No card: unassigned, for review.
        (
            "!",
            "Paper Shop",
            "Expenses:Office",
            "Liabilities:CreditCard:Unassigned",
            ["sample-studio"],
        ),
        # Unknown category: uncategorized, for review.
        (
            "!",
            "Ads Inc",
            "Expenses:Uncategorized",
            "Liabilities:PayPal",
            ["side-project-beta"],
        ),
        # Split payment: booked to the card, for review.
        (
            "!",
            "Gadget Store",
            "Expenses:Equipment",
            "Liabilities:CreditCard:Card-4242",
            ["sample-studio"],
        ),
    ]
    first = txns[0]
    assert first.narration == "VM hosting"
    assert first.meta["invoice"] == "INV-1"
    assert first.meta["document"] == "2026-01-05.cloudco_2026_01.pdf"
    assert first.postings[0].units == Amount(Decimal("24.00"), "USD")
    assert first.postings[1].units == Amount(Decimal("-24.00"), "USD")
    # Leading space in the receipt file name is ignored.
    assert txns[1].meta["document"] == "2026-01-09.paper_2026_01.pdf"
    assert "document" not in txns[2].meta


def test_expense_csv_defaults_and_other_files(tmp_path: Path) -> None:
    # Default columns: Date, Vendor, Amount, Category.
    imp = ExpenseCSV()
    (txn, *_) = imp.extract(str(SHEET), [])
    assert isinstance(txn, data.Transaction)
    assert txn.flag == "!"  # no categories configured
    assert txn.narration == ""
    assert txn.tags == data.EMPTY_SET

    other = tmp_path / "other.csv"
    other.write_text("When,Who,How much\n2026-01-01,X,1\n")
    assert not imp.identify(str(other))
    assert imp.extract(str(other), []) == []
    assert imp.date(str(other)) is None
    assert not imp.identify(str(tmp_path / "expenses.pdf"))


def test_expense_receipts(tmp_path: Path) -> None:
    imp = importer()
    receipts = ExpenseReceipts(
        imp,
        [str(SHEET)],
        also=[
            (
                r"cloud_itemized_(?P<year>\d{4})(?:_(?P<month>\d{2}))?\.csv",
                "Expenses:Cloud",
            )
        ],
    )
    assert receipts.name == "my_expenses:receipts"

    def info(name: str) -> tuple[bool, str, datetime.date | None, str | None]:
        path = tmp_path / name
        path.write_text("x")
        p = str(path)
        return (
            receipts.identify(p),
            receipts.account(p),
            receipts.date(p),
            receipts.filename(p),
        )

    assert info("cloudco_2026_01.pdf") == (
        True,
        "Expenses:Cloud",
        datetime.date(2026, 1, 5),
        "2026-01-05.cloudco_2026_01.pdf",
    )
    # The file on disk has a leading space, like the spreadsheet cell.
    assert info(" paper_2026_01.pdf")[3] == "2026-01-09.paper_2026_01.pdf"
    assert info("cloud_itemized_2026_03.csv")[2:] == (
        datetime.date(2026, 3, 1),
        "2026-03-01.cloud_itemized_2026_03.csv",
    )
    assert info("cloud_itemized_2026.csv")[2] == datetime.date(2026, 12, 1)
    assert info("random.pdf") == (False, "Expenses:Uncategorized", None, None)
    assert receipts.extract(str(tmp_path / "random.pdf"), []) == []
