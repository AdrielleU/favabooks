"""Stripe "Itemized payout reconciliation" report importer.

Download: Dashboard → Reports → Payouts reconciliation → Download →
Itemized. Add the optional columns customer_name, customer_email and
invoice_id for richer entries (docs.stripe.com/reports/report-types/
payout-reconciliation). Not named stripe.py, so the Stripe SDK isn't shadowed.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from beancount.core import data
from beancount.core.amount import Amount
from beangulp.importer import Importer

from fava.qb_importers.bank_csv import parse_amount
from fava.qb_importers.bank_csv import parse_date
from fava.qb_importers.formats import ISO_DATE

if TYPE_CHECKING:  # pragma: no cover
    import datetime

#: Columns every version of the itemized report has by default.
REQUIRED = {
    "balance_transaction_id",
    "reporting_category",
    "gross",
    "fee",
    "net",
}
#: Date columns across report versions, most specific first.
CREATED = ("created_utc", "created")
PAYOUT_DATE = (
    "automatic_payout_effective_at_utc",
    "automatic_payout_effective_at",
)
#: Categories whose counter-posting is revenue.
REVENUE = {"charge", "refund", "partial_capture_reversal", "refund_failure"}


def _first(row: dict[str, str], columns: tuple[str, ...]) -> str:
    return next((row[c] for c in columns if row.get(c)), "")


class StripePayouts(Importer):
    """Book a Stripe itemized payout reconciliation CSV.

    Args:
        account: The Stripe balance account.
        bank: Where payouts land; one transfer per payout.
        income: Revenue account for charges and refunds.
        fees: Account for Stripe's fees.
        uncategorized: Anything else (disputes, adjustments), flagged "!".
        filename: Optional text the file name must contain.
    """

    def __init__(
        self,
        account: str = "Assets:Stripe",
        *,
        bank: str = "Assets:Bank:Checking",
        income: str = "Income:Services",
        fees: str = "Expenses:Fees:Stripe",
        uncategorized: str = "Expenses:Uncategorized",
        filename: str | None = None,
    ) -> None:
        self._account = account
        self.bank = bank
        self.income = income
        self.fees = fees
        self.uncategorized = uncategorized
        self.filename_pattern = filename

    @property
    def name(self) -> str:
        """Unique per Stripe account."""
        return f"stripe_payouts:{self._account}"

    def account(self, filepath: str) -> str:  # noqa: ARG002
        """The Stripe balance account."""
        return self._account

    def _rows(self, filepath: str) -> list[tuple[int, dict[str, str]]] | None:
        path = Path(filepath)
        if path.suffix.lower() != ".csv":
            return None
        pattern = self.filename_pattern
        if pattern and pattern.casefold() not in path.name.casefold():
            return None
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(text.splitlines())
        if not REQUIRED.issubset(reader.fieldnames or ()):
            return None
        return [(reader.line_num, row) for row in reader]

    def identify(self, filepath: str) -> bool:
        """A CSV with the itemized payout reconciliation columns."""
        return self._rows(filepath) is not None

    def date(self, filepath: str) -> datetime.date | None:
        """The latest balance transaction in the report."""
        dates = [
            parse_date(_first(row, CREATED), ISO_DATE)
            for _, row in self._rows(filepath) or []
        ]
        return max((d for d in dates if d), default=None)

    def _posting(
        self, account: str, number: Decimal, currency: str
    ) -> data.Posting:
        return data.Posting(
            account, Amount(number, currency), None, None, None, None
        )

    def extract(
        self,
        filepath: str,
        existing: data.Entries,  # noqa: ARG002
    ) -> data.Entries:
        """One entry per balance transaction, one transfer per payout."""
        entries: data.Entries = []
        payouts: dict[str, list[Decimal]] = defaultdict(list)
        payout_info: dict[str, tuple[datetime.date, str]] = {}
        for lineno, row in self._rows(filepath) or []:
            category = row["reporting_category"].strip()
            day = parse_date(_first(row, CREATED), ISO_DATE)
            gross = parse_amount(row["gross"])
            fee = parse_amount(row["fee"]) or Decimal()
            net = parse_amount(row["net"])
            if (
                category == "payout"
                or day is None
                or gross is None
                or net is None
            ):
                # Payout rows only appear in other reports; transfers are
                # booked from automatic_payout_id below.
                continue
            currency = (row.get("currency") or "usd").strip().upper()
            meta = data.new_metadata(filepath, lineno)
            meta["stripe_txn"] = row["balance_transaction_id"].strip()
            customer = (
                row.get("customer_name") or row.get("customer_email") or ""
            ).strip()
            if customer:
                meta["customer"] = customer
            if invoice := (row.get("invoice_id") or "").strip():
                meta["invoice"] = invoice
            payout = (row.get("automatic_payout_id") or "").strip()
            if payout:
                meta["payout"] = payout
                payouts[payout].append(net)
                payout_date = parse_date(_first(row, PAYOUT_DATE), ISO_DATE)
                payout_info.setdefault(payout, (payout_date or day, currency))

            if category in REVENUE:
                counter, flag = self.income, "*"
            elif category == "fee":
                counter, flag = self.fees, "*"
            else:
                counter, flag = self.uncategorized, "!"
            postings = [self._posting(self._account, net, currency)]
            if fee:
                postings.append(self._posting(self.fees, fee, currency))
            postings.append(self._posting(counter, -gross, currency))
            entries.append(
                data.Transaction(
                    meta,
                    day,
                    flag,
                    customer or None,
                    (row.get("description") or category).strip(),
                    data.EMPTY_SET,
                    data.EMPTY_SET,
                    postings,
                )
            )

        for payout, nets in payouts.items():
            day, currency = payout_info[payout]
            total = sum(nets, Decimal())
            meta = data.new_metadata(filepath, 0)
            meta["payout"] = payout
            entries.append(
                data.Transaction(
                    meta,
                    day,
                    "*",
                    "Stripe",
                    f"Payout {payout}",
                    data.EMPTY_SET,
                    data.EMPTY_SET,
                    [
                        self._posting(self._account, -total, currency),
                        self._posting(self.bank, total, currency),
                    ],
                )
            )
        return entries

    def deduplicate(
        self, entries: data.Entries, existing: data.Entries
    ) -> None:
        """Mark entries whose Stripe id is already in the ledger."""
        seen = {
            (key, entry.meta[key])
            for entry in existing
            if isinstance(entry, data.Transaction)
            for key in ("stripe_txn", "payout")
            if key in entry.meta
        }
        for entry in entries:
            key = "stripe_txn" if "stripe_txn" in entry.meta else "payout"
            if (key, entry.meta.get(key)) in seen:
                entry.meta["__duplicate__"] = True
