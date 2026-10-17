from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from beancount.core import data
from beancount.loader import load_file

from fava.qb_receipts import ReceiptError


def test_receipts(tmp_path: Path) -> None:
    software = tmp_path / "documents" / "Expenses" / "Software"
    software.mkdir(parents=True)
    (software / "2025-01-03.invoice.pdf").touch()
    (software / "2025-01-04.other.pdf").touch()
    card = tmp_path / "documents" / "Liabilities" / "Card"
    card.mkdir(parents=True)
    (card / "2025-01-05.statement.pdf").touch()

    ledger = tmp_path / "main.beancount"
    ledger.write_text(
        dedent(
            """
            option "title" "Receipts"
            option "documents" "documents"
            plugin "fava.qb_receipts"

            2025-01-01 open Expenses:Software
            2025-01-01 open Liabilities:Card

            2025-01-03 * "SaaS" "By file name under the expense"
              document: "2025-01-03.invoice.pdf"
              Expenses:Software   10.00 USD
              Liabilities:Card
                document: "documents/Liabilities/Card/2025-01-05.statement.pdf"

            2025-01-06 * "Shop" "A receipt that isn't there"
              document: "2025-01-06.missing.pdf"
              Expenses:Software    5.00 USD
              Liabilities:Card

            2025-01-07 * "Plain" "No receipt; a posting without metadata"
              Expenses:Software    1.00 USD
              Liabilities:Card
            """
        )
    )
    entries, errors, _ = load_file(str(ledger))

    assert len(errors) == 1
    assert isinstance(errors[0], ReceiptError)
    assert "2025-01-06.missing.pdf" in errors[0].message
    documents = {
        Path(e.filename).name: e.tags or frozenset()
        for e in entries
        if isinstance(e, data.Document)
    }
    assert "linked" in documents["2025-01-03.invoice.pdf"]
    assert "linked" in documents["2025-01-05.statement.pdf"]
    assert "linked" not in documents["2025-01-04.other.pdf"]
    # No dok- links on anything.
    assert not any(getattr(e, "links", None) for e in entries)
