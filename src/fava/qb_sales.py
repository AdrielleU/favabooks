"""Customers and invoices (qb-fork): bookkeeping, not invoicing.

Invoices are sent elsewhere (Stripe, a PDF, another app); Favabooks only
books them. An invoice is every transaction carrying the same `invoice:`
metadata:

- Recorded or imported invoices debit Accounts Receivable and credit
  income. Matching the deposit that paid it moves the deposit's income or
  uncategorized posting to Accounts Receivable, which clears the balance.
- Sales the Stripe importer books (income straight to `Assets:Stripe`, with
  `invoice:` and `customer:`) are paid as soon as they're booked.

Customers are the `customer:` metadata, or the payee, of those invoices and
of any other income transaction.
"""

from __future__ import annotations

import csv
import datetime
import io
import re
from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec
from msgspec import Struct

from fava.beans import create
from fava.beans.abc import Transaction
from fava.beans.funcs import hash_entry
from fava.context import g
from fava.core.file import get_entry_slice
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.qb_importers.bank_csv import parse_amount
from fava.qb_importers.bank_csv import parse_date
from fava.qb_transactions import documents_by_name
from fava.qb_transactions import QbReceipt  # noqa: TC001 (msgspec)
from fava.qb_transactions import receipts_of
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from fava.beans.abc import Directive

ZERO = Decimal()
AR_LEAF = "AccountsReceivable"
#: Payment terms when an invoice has no due date.
DEFAULT_TERMS = datetime.timedelta(days=30)
DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%b %d, %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%Y/%m/%d",
)


def _roots() -> tuple[str, str]:
    options = g.ledger.options
    return options["name_assets"], options["name_income"]


def ar_account() -> str:
    """The Accounts Receivable account: an open one, or the default name."""
    assets, _ = _roots()
    for account in g.ledger.accounts:
        if account.startswith(f"{assets}:") and "Receivable" in account:
            return account
    return f"{assets}:{AR_LEAF}"


def _is_ar(account: str, assets: str) -> bool:
    return account.startswith(f"{assets}:") and "Receivable" in account


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


# --- Invoices -----------------------------------------------------------


class QbInvoice(Struct, frozen=True):
    """An invoice and how much of it is paid."""

    number: str
    customer: str
    date: datetime.date
    due: datetime.date | None
    amount: Decimal
    paid: Decimal
    balance: Decimal
    currency: str
    #: paid, open, partial or overdue.
    status: str
    #: Where it came from: "stripe" (paid sale) or "invoice" (receivable).
    source: str
    memo: str
    #: The invoice entry first, then payments.
    entry_hashes: list[str]
    receipts: list[QbReceipt]


@dataclass
class _Invoice:
    number: str
    customer: str = ""
    date: datetime.date | None = None
    due: datetime.date | None = None
    billed: Decimal = ZERO
    paid: Decimal = ZERO
    currency: str = ""
    source: str = "invoice"
    memo: str = ""
    email: str = ""
    entry_hashes: list[str] = field(default_factory=list)
    receipts: list[QbReceipt] = field(default_factory=list)


def _sums(
    txn: Transaction, test: Callable[[str], bool]
) -> tuple[Decimal, Decimal, str]:
    """Positive and negative sums, and currency, of postings passing `test`."""
    positive = negative = ZERO
    currency = ""
    for posting in txn.postings:
        units = posting.units
        if not test(posting.account) or units is None or units.number is None:
            continue
        currency = currency or units.currency
        if units.number > 0:
            positive += units.number
        else:
            negative -= units.number
    return positive, negative, currency


def _collect() -> dict[str, _Invoice]:
    """Sales invoices by number, from transactions with `invoice:` metadata.

    Only transactions touching income or Accounts Receivable count; an
    `invoice:` on an expense is the vendor's invoice number.
    """
    assets, income = _roots()
    documents = documents_by_name()
    invoices: dict[str, _Invoice] = {}
    for txn in g.ledger.all_entries_by_type.Transaction:
        number = _text(txn.meta.get("invoice"))
        if not number:
            continue
        billed, paid, currency = _sums(txn, lambda a: _is_ar(a, assets))
        stripe = False
        if not currency:
            # No receivable: a sale paid when booked (e.g. by Stripe).
            refunds, sales, currency = _sums(
                txn, lambda a: a.startswith(f"{income}:")
            )
            if not currency:
                # Neither: a vendor's invoice on an expense, not a sale.
                continue
            billed = paid = sales - refunds
            stripe = True
        inv = invoices.setdefault(number, _Invoice(number))
        if stripe and inv.date is None:
            inv.source = "stripe"
        if billed > 0 and inv.date is None:
            inv.date = txn.date
            inv.memo = txn.narration or ""
            due = txn.meta.get("due")
            inv.due = due if isinstance(due, datetime.date) else None
        inv.billed += billed
        inv.paid += paid
        inv.currency = inv.currency or currency
        inv.customer = (
            inv.customer
            or _text(txn.meta.get("customer"))
            or (txn.payee or "")
        )
        inv.email = inv.email or _text(txn.meta.get("customer_email"))
        inv.entry_hashes.append(hash_entry(txn))
        inv.receipts.extend(receipts_of(txn, documents))
    return invoices


def _status(inv: _Invoice, today: datetime.date) -> str:
    balance = inv.billed - inv.paid
    if balance <= 0:
        return "paid"
    if inv.due is not None and inv.due < today:
        return "overdue"
    return "partial" if inv.paid > 0 else "open"


def _invoice(inv: _Invoice, today: datetime.date) -> QbInvoice:
    return QbInvoice(
        number=inv.number,
        customer=inv.customer,
        date=inv.date or today,
        due=inv.due,
        amount=inv.billed,
        paid=inv.paid,
        balance=inv.billed - inv.paid,
        currency=inv.currency,
        status=_status(inv, today),
        source=inv.source,
        memo=inv.memo,
        entry_hashes=inv.entry_hashes,
        receipts=inv.receipts,
    )


class QbInvoices(Struct, frozen=True):
    """All invoices, newest first."""

    ar_account: str
    today: datetime.date
    invoices: list[QbInvoice]
    #: Income accounts, most used first (for recording invoices).
    income_accounts: list[str]


def _income_accounts() -> list[str]:
    _, income = _roots()
    used: Counter[str] = Counter()
    for txn in g.ledger.all_entries_by_type.Transaction:
        used.update(
            p.account
            for p in txn.postings
            if p.account.startswith(f"{income}:")
        )
    open_accounts = [
        a
        for a in g.ledger.accounts
        if a.startswith(f"{income}:")
        and g.ledger.accounts[a].close_date is None
    ]
    return sorted(open_accounts, key=lambda a: (-used[a], a))


@api_endpoint
def get_qb_invoices() -> QbInvoices:
    """Every invoice in the ledger (not limited by the header filters)."""
    g.ledger.changed()
    today = local_today()
    invoices = [_invoice(inv, today) for inv in _collect().values()]
    invoices.sort(key=lambda i: (i.date, i.number), reverse=True)
    return QbInvoices(ar_account(), today, invoices, _income_accounts())


# --- Customers ----------------------------------------------------------


class QbCustomer(Struct, frozen=True):
    """A customer with their sales and what they owe."""

    name: str
    email: str
    invoices: int
    #: Total sales (invoiced or paid directly).
    sales: Decimal
    open_balance: Decimal
    overdue: Decimal
    currency: str
    last_date: datetime.date


@dataclass
class _Customer:
    email: str = ""
    invoices: int = 0
    sales: Decimal = ZERO
    open_balance: Decimal = ZERO
    overdue: Decimal = ZERO
    currency: str = ""
    last_date: datetime.date = datetime.date.min


@api_endpoint
def get_qb_customers() -> list[QbCustomer]:
    """Customers from invoices and income, biggest sales first."""
    g.ledger.changed()
    _, income = _roots()
    today = local_today()
    customers: dict[str, _Customer] = {}

    def customer(name: str) -> _Customer:
        return customers.setdefault(name or "(no name)", _Customer())

    for inv in _collect().values():
        c = customer(inv.customer)
        c.email = c.email or inv.email
        c.invoices += 1
        c.sales += inv.billed
        balance = inv.billed - inv.paid
        if balance > 0:
            c.open_balance += balance
            if _status(inv, today) == "overdue":
                c.overdue += balance
        c.currency = c.currency or inv.currency
        c.last_date = max(c.last_date, inv.date or c.last_date)
    for txn in g.ledger.all_entries_by_type.Transaction:
        if _text(txn.meta.get("invoice")):
            continue
        refunds, sales, currency = _sums(
            txn, lambda a: a.startswith(f"{income}:")
        )
        if not currency:
            continue
        c = customer(_text(txn.meta.get("customer")) or (txn.payee or ""))
        c.email = c.email or _text(txn.meta.get("customer_email"))
        c.sales += sales - refunds
        c.currency = c.currency or currency
        c.last_date = max(c.last_date, txn.date)
    result = [
        QbCustomer(
            name,
            c.email,
            c.invoices,
            c.sales,
            c.open_balance,
            c.overdue,
            c.currency,
            c.last_date,
        )
        for name, c in customers.items()
    ]
    result.sort(key=lambda c: (-c.sales, c.name))
    return result


# --- Recording invoices -------------------------------------------------


class InvoiceForm(Struct, frozen=True):
    """An invoice to book, as typed or read from a CSV row."""

    customer: str
    number: str
    date: str
    amount: str
    income_account: str
    due: str = ""
    memo: str = ""
    email: str = ""
    currency: str = ""


def _parse_form(
    form: InvoiceForm, existing: set[str]
) -> tuple[datetime.date, datetime.date | None, Decimal]:
    """Validated date, due date and amount, or a ValidationError."""
    if not form.customer.strip():
        msg = "enter the customer"
        raise ValidationError(msg)
    if not form.number.strip():
        msg = "enter the invoice number"
        raise ValidationError(msg)
    if form.number.strip() in existing:
        msg = f"invoice {form.number.strip()} is already in your books"
        raise ValidationError(msg)
    date = parse_date(form.date, DATE_FORMATS)
    if date is None:
        msg = f"the invoice date '{form.date}' isn't a date"
        raise ValidationError(msg)
    due = parse_date(form.due, DATE_FORMATS) if form.due.strip() else None
    if form.due.strip() and due is None:
        msg = f"the due date '{form.due}' isn't a date"
        raise ValidationError(msg)
    amount = parse_amount(form.amount)
    if amount is None or amount <= 0:
        msg = "the amount must be a positive number"
        raise ValidationError(msg)
    _, income = _roots()
    if not form.income_account.startswith(f"{income}:"):
        msg = f"choose an income account (under {income})"
        raise ValidationError(msg)
    return date, due, amount


def _invoice_entry(
    form: InvoiceForm,
    date: datetime.date,
    due: datetime.date | None,
    amount: Decimal,
) -> Transaction:
    meta: dict[str, object] = {
        "invoice": form.number.strip(),
        "customer": form.customer.strip(),
        "due": due or date + DEFAULT_TERMS,
    }
    if form.email.strip():
        meta["customer_email"] = form.email.strip()
    currency = form.currency or g.ledger.options["operating_currency"][0]
    narration = f"Invoice {form.number.strip()}"
    if form.memo.strip():
        narration += f": {form.memo.strip()}"
    return create.transaction(
        meta,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
        date,
        "*",
        form.customer.strip(),
        narration,
        postings=[
            create.posting(ar_account(), create.amount(amount, currency)),
            create.posting(
                form.income_account, create.amount(-amount, currency)
            ),
        ],
    )


def _payment_entry(
    number: str,
    customer: str,
    date: datetime.date,
    amount: Decimal,
    currency: str,
    account: str,
) -> Transaction:
    return create.transaction(
        {"invoice": number, "customer": customer},
        date,
        "*",
        customer,
        f"Payment for invoice {number}",
        postings=[
            create.posting(account, create.amount(amount, currency)),
            create.posting(ar_account(), create.amount(-amount, currency)),
        ],
    )


def _with_ar_open(
    entries: list[Transaction], first: datetime.date
) -> list[Directive]:
    """Prepend an Open for the receivable account when it isn't open yet."""
    account = ar_account()
    if account in g.ledger.accounts:
        return list(entries)
    earliest = min(
        [
            first,
            *(t.date for t in g.ledger.all_entries_by_type.Transaction[:1]),
        ]
    )
    return [create.open({}, earliest, account, []), *entries]


class QbRecorded(Struct, frozen=True):
    """A recorded invoice's entry (to attach the PDF to)."""

    entry_hash: str


@api_endpoint
def put_qb_invoice(invoice: dict[str, str]) -> QbRecorded:
    """Book one invoice: receivable up, income credited."""
    ledger = g.ledger
    ledger.changed()
    form = msgspec.convert(invoice, InvoiceForm)
    date, due, amount = _parse_form(form, set(_collect()))
    if form.income_account not in ledger.accounts:
        msg = f"unknown account '{form.income_account}'"
        raise ValidationError(msg)
    entry = _invoice_entry(form, date, due, amount)
    ledger.file.insert_entries(_with_ar_open([entry], date))
    ledger.load_file()
    number = form.number.strip()
    return QbRecorded(
        next(
            hash_entry(txn)
            for txn in ledger.all_entries_by_type.Transaction
            if _text(txn.meta.get("invoice")) == number
        )
    )


# --- Matching payments --------------------------------------------------


class QbDeposit(Struct, frozen=True):
    """A deposit that could be the payment for an invoice."""

    entry_hash: str
    date: datetime.date
    payee: str
    narration: str
    account: str
    amount: Decimal
    currency: str
    #: The posting that moves to Accounts Receivable.
    category: str
    exact: bool


def _open_invoice(number: str) -> _Invoice:
    inv = _collect().get(number)
    if inv is None:
        msg = f"no invoice {number}"
        raise ValidationError(msg)
    if inv.billed - inv.paid <= 0:
        msg = f"invoice {number} is already paid"
        raise ValidationError(msg)
    return inv


def _deposit(txn: Transaction) -> QbDeposit | None:
    """`txn` as a candidate payment, or None.

    A candidate puts money into an asset from income or an uncategorized
    account, and has no invoice yet.
    """
    assets, income = _roots()
    if _text(txn.meta.get("invoice")):
        return None
    into = [
        p
        for p in txn.postings
        if p.account.startswith(f"{assets}:")
        and not _is_ar(p.account, assets)
        and p.units is not None
        and p.units.number is not None
        and p.units.number > 0
    ]
    source = [
        p.account
        for p in txn.postings
        if p.account.startswith(f"{income}:")
        or p.account.endswith("Uncategorized")
    ]
    if len(into) != 1 or len(source) != 1:
        return None
    units = into[0].units
    return QbDeposit(
        hash_entry(txn),
        txn.date,
        txn.payee or "",
        txn.narration or "",
        into[0].account,
        units.number,
        units.currency,
        source[0],
        exact=False,
    )


@api_endpoint
def get_qb_invoice_deposits(number: str) -> list[QbDeposit]:
    """Deposits that could have paid invoice `number`, best match first."""
    g.ledger.changed()
    inv = _open_invoice(number)
    balance = inv.billed - inv.paid
    start = (inv.date or datetime.date.min) - datetime.timedelta(days=7)
    words = set(re.findall(r"\w{3,}", inv.customer.casefold()))
    found = []
    for txn in g.ledger.all_entries_by_type.Transaction:
        if txn.date < start:
            continue
        deposit = _deposit(txn)
        if deposit is None or deposit.currency != inv.currency:
            continue
        text = f"{deposit.payee} {deposit.narration}".casefold()
        named = any(w in text for w in words)
        exact = deposit.amount == balance
        found.append(
            (
                (not exact, not named, abs((deposit.date - start).days)),
                msgspec.structs.replace(deposit, exact=exact),
            )
        )
    found.sort(key=lambda pair: pair[0])
    return [deposit for _, deposit in found[:20]]


@api_endpoint
def put_qb_invoice_payment(number: str, entry_hash: str) -> str:
    """Mark deposit `entry_hash` as the payment for invoice `number`."""
    ledger = g.ledger
    ledger.changed()
    inv = _open_invoice(number)
    entry = ledger.get_entry(entry_hash)
    deposit = _deposit(entry) if isinstance(entry, Transaction) else None
    if deposit is None:
        msg = "that transaction isn't a deposit that can pay an invoice"
        raise ValidationError(msg)
    # An open invoice has a receivable posting, so the account is open.
    source, sha256sum = get_entry_slice(entry)
    header, *body = source.split("\n")
    meta = [f'  invoice: "{number}"']
    if "customer" not in entry.meta:
        meta.append(f'  customer: "{inv.customer}"')
    posting = re.compile(rf"^(\s+){re.escape(deposit.category)}(?=\s|$)")
    new_source = "\n".join(
        [
            header,
            *meta,
            *(
                posting.sub(lambda m: m.group(1) + ar_account(), line)
                for line in body
            ),
        ]
    )
    ledger.file.save_entry_slice(entry_hash, new_source, sha256sum)
    return f"Matched to invoice {number}."


# --- Importing invoices from a CSV --------------------------------------

#: Invoice fields and header names that mean them, most specific first.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "number": (
        "invoice number",
        "invoice no",
        "invoice #",
        "invoice id",
        "number",
        "no.",
        "num",
        "invoice",
        "id",
    ),
    "customer": (
        "customer name",
        "client name",
        "customer",
        "client",
        "bill to",
        "company",
        "name",
    ),
    "email": ("customer email", "client email", "email"),
    "date": (
        "invoice date",
        "date (utc)",
        "date issued",
        "issue date",
        "issued",
        "date",
        "created (utc)",
        "created",
    ),
    "due": ("due date (utc)", "due date", "due"),
    "amount": (
        "total",
        "invoice total",
        "amount",
        "amount due",
        "invoice amount",
    ),
    "paid": ("amount paid", "paid amount", "paid"),
    "paid_date": ("paid at (utc)", "paid at", "date paid", "paid date"),
    "status": ("status", "invoice status"),
    "currency": ("currency",),
}
SKIP_STATUSES = {"draft", "void", "voided", "deleted", "uncollectible"}


def _read_csv(content: str) -> tuple[list[str], list[list[str]]]:
    rows = [
        row
        for row in csv.reader(io.StringIO(content.lstrip("\ufeff")))
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        msg = "the file is empty"
        raise ValidationError(msg)
    return [cell.strip() for cell in rows[0]], rows[1:]


def guess_mapping(header: list[str]) -> dict[str, str]:
    """Columns for each invoice field, by header name."""
    lowered = {column.casefold(): column for column in header}
    mapping: dict[str, str] = {}
    for field_name, names in SYNONYMS.items():
        for name in names:
            column = lowered.get(name)
            if column is not None and column not in mapping.values():
                mapping[field_name] = column
                break
    return mapping


class QbInvoiceRow(Struct, frozen=True):
    """A CSV row read as an invoice."""

    line: int
    number: str
    customer: str
    date: datetime.date | None
    due: datetime.date | None
    amount: Decimal | None
    paid: Decimal
    status: str
    #: new, duplicate, skipped or invalid.
    state: str
    problem: str
    email: str = ""
    currency: str = ""
    paid_date: datetime.date | None = None


class QbInvoicePreview(Struct, frozen=True):
    """How a CSV of invoices will be imported."""

    header: list[str]
    mapping: dict[str, str]
    rows: list[QbInvoiceRow]


def _rows(
    content: str, mapping: dict[str, str] | None
) -> tuple[list[str], dict[str, str], list[QbInvoiceRow]]:
    header, raw_rows = _read_csv(content)
    mapping = {
        k: v
        for k, v in (mapping or guess_mapping(header)).items()
        if v in header
    }
    index = {
        field_name: header.index(col) for field_name, col in mapping.items()
    }
    existing = set(_collect())
    seen: set[str] = set()
    rows = []
    for line, raw in enumerate(raw_rows, start=2):

        def cell(name: str, raw: list[str] = raw) -> str:
            i = index.get(name)
            return raw[i].strip() if i is not None and i < len(raw) else ""

        number = cell("number")
        status = cell("status")
        date = parse_date(cell("date"), DATE_FORMATS)
        amount = parse_amount(cell("amount"))
        paid = parse_amount(cell("paid"))
        if paid is None:
            paid = amount if status.casefold() == "paid" and amount else ZERO
        missing = [
            name
            for name, value in (
                ("invoice number", number),
                ("customer", cell("customer")),
                ("date", date),
                ("amount", amount),
            )
            if not value
        ]
        if status.casefold() in SKIP_STATUSES:
            state, problem = "skipped", f"status is {status}"
        elif missing:
            state, problem = "invalid", "missing " + ", ".join(missing)
        elif number in existing or number in seen:
            state, problem = "duplicate", "already in your books"
        else:
            state, problem = "new", ""
        seen.add(number)
        rows.append(
            QbInvoiceRow(
                line=line,
                number=number,
                customer=cell("customer"),
                date=date,
                due=parse_date(cell("due"), DATE_FORMATS),
                amount=amount,
                paid=paid,
                status=status,
                state=state,
                problem=problem,
                email=cell("email"),
                currency=cell("currency").upper(),
                paid_date=parse_date(cell("paid_date"), DATE_FORMATS),
            )
        )
    return header, mapping, rows


@api_endpoint
def put_qb_invoice_csv_preview(
    content: str, mapping: dict[str, str] | None = None
) -> QbInvoicePreview:
    """Read a CSV of invoices; `mapping` overrides the guessed columns."""
    g.ledger.changed()
    header, used, rows = _rows(content, mapping)
    return QbInvoicePreview(header, used, rows)


class QbInvoiceImport(Struct, frozen=True):
    """What an invoice import booked."""

    invoices: int
    payments: int


@api_endpoint
def put_qb_invoice_csv_import(
    content: str,
    mapping: dict[str, str],
    income_account: str,
    payment_account: str = "",
) -> QbInvoiceImport:
    """Book the new rows of a CSV of invoices.

    With `payment_account`, the paid part of each invoice is booked as a
    payment into that account (only when those deposits aren't imported
    from a bank or Stripe as well).
    """
    ledger = g.ledger
    ledger.changed()
    if income_account not in ledger.accounts:
        msg = "choose the income account for these invoices"
        raise ValidationError(msg)
    if payment_account and payment_account not in ledger.accounts:
        msg = f"unknown account '{payment_account}'"
        raise ValidationError(msg)
    _, _, rows = _rows(content, mapping)
    default_currency = ledger.options["operating_currency"][0]
    entries: list[Transaction] = []
    payments = 0
    for row in rows:
        if row.state != "new" or row.date is None or row.amount is None:
            continue
        currency = row.currency or default_currency
        form = InvoiceForm(
            customer=row.customer,
            number=row.number,
            date=row.date.isoformat(),
            amount=str(row.amount),
            income_account=income_account,
            email=row.email,
            currency=currency,
        )
        entries.append(_invoice_entry(form, row.date, row.due, row.amount))
        paid = min(row.paid, row.amount)
        if payment_account and paid > 0:
            payments += 1
            entries.append(
                _payment_entry(
                    row.number,
                    row.customer,
                    row.paid_date or row.date,
                    paid,
                    currency,
                    payment_account,
                )
            )
    if not entries:
        msg = "there are no new invoices in this file"
        raise ValidationError(msg)
    ledger.file.insert_entries(
        _with_ar_open(entries, min(e.date for e in entries))
    )
    return QbInvoiceImport(len(entries) - payments, payments)
