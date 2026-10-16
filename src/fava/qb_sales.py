"""Sales (invoices, customers) and purchases (bills, vendors) (qb-fork).

The endpoints for both sides of `fava.qb_docs`.
"""

from __future__ import annotations

from fava.json_api import api_endpoint
from fava.qb_docs import import_csv
from fava.qb_docs import list_docs
from fava.qb_docs import list_parties
from fava.qb_docs import match_payment
from fava.qb_docs import payment_candidates
from fava.qb_docs import preview_csv
from fava.qb_docs import PURCHASES
from fava.qb_docs import QbDocImport  # noqa: TC001 (return annotations)
from fava.qb_docs import QbDocPreview  # noqa: TC001
from fava.qb_docs import QbDocs  # noqa: TC001
from fava.qb_docs import QbParty  # noqa: TC001
from fava.qb_docs import QbPayment  # noqa: TC001
from fava.qb_docs import QbRecorded  # noqa: TC001
from fava.qb_docs import record
from fava.qb_docs import SALES

# --- Sales --------------------------------------------------------------


@api_endpoint
def get_qb_invoices() -> QbDocs:
    """Every invoice in the ledger (not limited by the header filters)."""
    return list_docs(SALES)


@api_endpoint
def get_qb_customers(start: str = "", end: str = "") -> list[QbParty]:
    """Customers from invoices and income, biggest sales first.

    Totals are for `start` to `end` (inclusive); balances are as of today.
    """
    return list_parties(SALES, start, end)


@api_endpoint
def put_qb_invoice(doc: dict[str, str]) -> QbRecorded:
    """Book one invoice: receivable up, income credited."""
    return record(SALES, doc)


@api_endpoint
def get_qb_invoice_payments(key: str) -> list[QbPayment]:
    """Deposits that could have paid invoice `key`, best match first."""
    return payment_candidates(SALES, key)


@api_endpoint
def put_qb_invoice_payment(key: str, entry_hash: str) -> str:
    """Mark deposit `entry_hash` as the payment for invoice `key`."""
    return match_payment(SALES, key, entry_hash)


@api_endpoint
def put_qb_invoice_csv_preview(
    content: str, mapping: dict[str, str] | None = None
) -> QbDocPreview:
    """Read a CSV of invoices; `mapping` overrides the guessed columns."""
    return preview_csv(SALES, content, mapping)


@api_endpoint
def put_qb_invoice_csv_import(
    content: str,
    mapping: dict[str, str],
    account: str,
    payment_account: str = "",
) -> QbDocImport:
    """Book the new rows of a CSV of invoices."""
    return import_csv(SALES, content, mapping, account, payment_account)


# --- Purchases ----------------------------------------------------------


@api_endpoint
def get_qb_bills() -> QbDocs:
    """Every bill in the ledger (not limited by the header filters)."""
    return list_docs(PURCHASES)


@api_endpoint
def get_qb_vendors(start: str = "", end: str = "") -> list[QbParty]:
    """Vendors from bills and expenses, biggest spending first.

    Totals are for `start` to `end` (inclusive); balances are as of today.
    """
    return list_parties(PURCHASES, start, end)


@api_endpoint
def put_qb_bill(doc: dict[str, str]) -> QbRecorded:
    """Book one bill: payable up, expense debited."""
    return record(PURCHASES, doc)


@api_endpoint
def get_qb_bill_payments(key: str) -> list[QbPayment]:
    """Payments that could have paid bill `key`, best match first."""
    return payment_candidates(PURCHASES, key)


@api_endpoint
def put_qb_bill_payment(key: str, entry_hash: str) -> str:
    """Mark payment `entry_hash` as the payment for bill `key`."""
    return match_payment(PURCHASES, key, entry_hash)


@api_endpoint
def put_qb_bill_csv_preview(
    content: str, mapping: dict[str, str] | None = None
) -> QbDocPreview:
    """Read a CSV of bills; `mapping` overrides the guessed columns."""
    return preview_csv(PURCHASES, content, mapping)


@api_endpoint
def put_qb_bill_csv_import(
    content: str,
    mapping: dict[str, str],
    account: str,
    payment_account: str = "",
) -> QbDocImport:
    """Book the new rows of a CSV of bills."""
    return import_csv(PURCHASES, content, mapping, account, payment_account)
