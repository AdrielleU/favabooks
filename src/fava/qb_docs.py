"""Invoices and bills (qb-fork): bookkeeping, not invoicing.

Invoices (sales) and bills (purchases) are sent and received elsewhere;
Favabooks only books them. Both work the same way, mirrored: a document is
every transaction carrying the same `invoice:` metadata (the document's
number, whoever issued it), on one side of the books.

- Sales touch income or Accounts Receivable; purchases touch expenses or
  Accounts Payable, and never income.
- Recorded or imported documents go through the receivable or payable
  account. Matching the payment moves the payment's income, expense or
  uncategorized posting to that account, which clears the balance.
- Documents booked straight to income or expenses (a Stripe sale, a card
  charge with its vendor invoice number) are paid when booked.

Customers and vendors are the `customer:` or `vendor:` metadata, or the
payee, of those documents and of any other income or expense transaction.
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
from fava.json_api import ValidationError
from fava.qb_close import check_open
from fava.qb_importers.bank_csv import parse_amount
from fava.qb_importers.bank_csv import parse_date
from fava.qb_transactions import documents_by_name
from fava.qb_transactions import in_period
from fava.qb_transactions import parse_period
from fava.qb_transactions import QbReceipt  # noqa: TC001 (msgspec)
from fava.qb_transactions import receipts_of
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from fava.beans.abc import Directive

ZERO = Decimal()
#: Payment terms when a document has no due date.
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
SKIP_STATUSES = {"draft", "void", "voided", "deleted", "uncollectible"}


def _root_name(option: str) -> str:
    """The root account named by an option such as "name_assets"."""
    options = g.ledger.options
    return {
        "name_assets": options["name_assets"],
        "name_liabilities": options["name_liabilities"],
        "name_income": options["name_income"],
        "name_expenses": options["name_expenses"],
    }[option]


@dataclass(frozen=True)
class Side:
    """Sales or purchases."""

    #: "invoice" or "bill", for messages.
    doc: str
    #: Metadata key naming the other party: "customer" or "vendor".
    party: str
    #: Option naming the root of the category accounts.
    root_option: str
    #: Option naming the root of the receivable or payable account.
    ledger_option: str
    #: Leaf of the default receivable or payable account.
    ledger_leaf: str
    #: Text in the receivable or payable account's name.
    ledger_word: str
    #: +1 when the ledger account grows with debits (receivable), else -1.
    sign: int
    #: Roots of accounts the money moves through (bank, card, Stripe).
    money_options: tuple[str, ...]
    #: Header names for the party column in a CSV.
    party_columns: tuple[str, ...]

    def root(self) -> str:
        """Root of the category accounts (Income or Expenses)."""
        return _root_name(self.root_option)

    def ledger_root(self) -> str:
        """Root of the receivable or payable account."""
        return _root_name(self.ledger_option)

    def is_ledger(self, account: str) -> bool:
        """Whether `account` is a receivable (or payable) account."""
        return (
            account.startswith(f"{self.ledger_root()}:")
            and self.ledger_word in account
        )

    def is_category(self, account: str) -> bool:
        """Whether `account` is an income (or expense) account."""
        return account.startswith(f"{self.root()}:")

    def ledger_account(self) -> str:
        """The receivable or payable account: an open one, or the default."""
        for account in g.ledger.accounts:
            if self.is_ledger(account):
                return account
        return f"{self.ledger_root()}:{self.ledger_leaf}"

    def is_money(self, account: str) -> bool:
        """Whether money moves through `account` (bank, card, Stripe)."""
        roots = tuple(f"{_root_name(o)}:" for o in self.money_options)
        return account.startswith(roots) and not self.is_ledger(account)

    def excluded(self, txn: Transaction) -> bool:
        """Purchases never include sales (a Stripe sale with its fee)."""
        if self.sign > 0:
            return False
        income = g.ledger.options["name_income"]
        return any(p.account.startswith(f"{income}:") for p in txn.postings)


SALES = Side(
    doc="invoice",
    party="customer",
    root_option="name_income",
    ledger_option="name_assets",
    ledger_leaf="AccountsReceivable",
    ledger_word="Receivable",
    sign=1,
    money_options=("name_assets",),
    party_columns=(
        "customer name",
        "client name",
        "customer",
        "client",
        "bill to",
        "company",
        "name",
    ),
)
PURCHASES = Side(
    doc="bill",
    party="vendor",
    root_option="name_expenses",
    ledger_option="name_liabilities",
    ledger_leaf="AccountsPayable",
    ledger_word="Payable",
    sign=-1,
    money_options=("name_assets", "name_liabilities"),
    party_columns=(
        "vendor name",
        "supplier name",
        "vendor",
        "supplier",
        "payee",
        "company",
        "name",
    ),
)


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


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


# --- Documents ----------------------------------------------------------


class QbDoc(Struct, frozen=True):
    """An invoice or bill and how much of it is paid."""

    #: Identifies the document in requests: the number for invoices,
    #: "vendor / number" for bills (vendors' numbers can collide).
    key: str
    number: str
    party: str
    date: datetime.date
    due: datetime.date | None
    amount: Decimal
    paid: Decimal
    balance: Decimal
    currency: str
    #: paid, open, partial or overdue.
    status: str
    #: Booked straight to income or expenses (paid when booked).
    direct: bool
    #: Bank, card or Stripe accounts it was paid with or into.
    paid_with: list[str]
    #: Income or expense accounts.
    categories: list[str]
    memo: str
    #: The document's entry first, then payments.
    entry_hashes: list[str]
    receipts: list[QbReceipt]
    #: Date of the last payment (None while nothing is paid).
    paid_date: datetime.date | None = None


@dataclass
class _Doc:
    number: str
    party: str
    date: datetime.date | None = None
    due: datetime.date | None = None
    billed: Decimal = ZERO
    paid: Decimal = ZERO
    currency: str = ""
    direct: bool = False
    memo: str = ""
    email: str = ""
    paid_date: datetime.date | None = None
    paid_with: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    entry_hashes: list[str] = field(default_factory=list)
    receipts: list[QbReceipt] = field(default_factory=list)


def doc_key(side: Side, party: str, number: str) -> str:
    """Key of a document (see QbDoc.key)."""
    return number if side.sign > 0 else f"{party} / {number}"


def _party(side: Side, txn: Transaction) -> str:
    return _text(txn.meta.get(side.party)) or (txn.payee or "")


def collect(side: Side) -> dict[str, _Doc]:
    """Documents by key, from transactions with `invoice:` metadata."""
    documents = documents_by_name()
    docs: dict[str, _Doc] = {}
    for txn in g.ledger.all_entries_by_type.Transaction:
        number = _text(txn.meta.get("invoice"))
        if not number or side.excluded(txn):
            continue
        positive, negative, currency = _sums(txn, side.is_ledger)
        direct = not currency
        if direct:
            positive, negative, currency = _sums(txn, side.is_category)
            if not currency:
                # Not this side: an invoice number on the other side's entry.
                continue
            billed = paid = (
                negative - positive if side.sign > 0 else positive - negative
            )
        else:
            billed, paid = (
                (positive, negative) if side.sign > 0 else (negative, positive)
            )
        party = _party(side, txn)
        doc = docs.setdefault(
            doc_key(side, party, number), _Doc(number, party)
        )
        # Dated by the document itself, not a payment (a $0 bill counts).
        if doc.date is None and (billed > 0 or paid == 0):
            doc.date = txn.date
            doc.direct = direct
            doc.memo = txn.narration or ""
            due = txn.meta.get("due")
            doc.due = due if isinstance(due, datetime.date) else None
        doc.billed += billed
        doc.paid += paid
        if paid > 0:
            doc.paid_date = max(doc.paid_date or txn.date, txn.date)
        doc.currency = doc.currency or currency
        doc.email = doc.email or _text(txn.meta.get(f"{side.party}_email"))
        for posting in txn.postings:
            target = (
                doc.paid_with
                if side.is_money(posting.account)
                else doc.categories
                if side.is_category(posting.account)
                else None
            )
            if target is not None and posting.account not in target:
                target.append(posting.account)
        doc.entry_hashes.append(hash_entry(txn))
        doc.receipts.extend(receipts_of(txn, documents))
    return docs


def _status(doc: _Doc, today: datetime.date) -> str:
    balance = doc.billed - doc.paid
    if balance <= 0:
        return "paid"
    if doc.due is not None and doc.due < today:
        return "overdue"
    return "partial" if doc.paid > 0 else "open"


class QbDocs(Struct, frozen=True):
    """All invoices or bills, newest first."""

    #: The receivable or payable account.
    ledger_account: str
    today: datetime.date
    docs: list[QbDoc]
    #: Income or expense accounts, most used first (for recording).
    accounts: list[str]


def _category_accounts(side: Side) -> list[str]:
    used: Counter[str] = Counter()
    for txn in g.ledger.all_entries_by_type.Transaction:
        used.update(
            p.account for p in txn.postings if side.is_category(p.account)
        )
    open_accounts = [
        a
        for a in g.ledger.accounts
        if side.is_category(a) and g.ledger.accounts[a].close_date is None
    ]
    return sorted(open_accounts, key=lambda a: (-used[a], a))


def list_docs(side: Side) -> QbDocs:
    """Every invoice or bill in the ledger (not limited by filters)."""
    g.ledger.changed()
    today = local_today()
    docs = [
        QbDoc(
            key=key,
            number=doc.number,
            party=doc.party,
            date=doc.date or today,
            due=doc.due,
            amount=doc.billed,
            paid=doc.paid,
            balance=doc.billed - doc.paid,
            currency=doc.currency,
            status=_status(doc, today),
            direct=doc.direct,
            paid_with=doc.paid_with,
            categories=doc.categories,
            memo=doc.memo,
            entry_hashes=doc.entry_hashes,
            receipts=doc.receipts,
            paid_date=doc.paid_date,
        )
        for key, doc in collect(side).items()
    ]
    docs.sort(key=lambda d: (d.date, d.key), reverse=True)
    return QbDocs(side.ledger_account(), today, docs, _category_accounts(side))


# --- Customers and vendors ----------------------------------------------


class QbParty(Struct, frozen=True):
    """A customer or vendor with their totals and open balance."""

    name: str
    email: str
    #: Number of invoices or bills.
    docs: int
    #: Total sales to them or spending with them.
    total: Decimal
    open_balance: Decimal
    overdue: Decimal
    currency: str
    last_date: datetime.date
    #: Their most used income or expense account.
    category: str
    #: Vendors: paid from bank or cash (not cards) in the period, the
    #: payments a 1099-NEC counts; card payments go on the card's 1099-K.
    bank_paid: Decimal = ZERO


@dataclass
class _Party:
    email: str = ""
    docs: int = 0
    total: Decimal = ZERO
    open_balance: Decimal = ZERO
    overdue: Decimal = ZERO
    currency: str = ""
    last_date: datetime.date = datetime.date.min
    categories: Counter[str] = field(default_factory=Counter)
    bank_paid: Decimal = ZERO


def _bank_paid(side: Side, txn: Transaction) -> Decimal:
    """Money a purchase took out of bank or cash accounts (not cards)."""
    assets = _root_name("name_assets")
    if side.sign > 0 or not any(
        side.is_category(p.account) or side.is_ledger(p.account)
        for p in txn.postings
    ):
        return ZERO
    _, out, _ = _sums(
        txn, lambda a: a.startswith(f"{assets}:") and side.is_money(a)
    )
    return out


def list_parties(side: Side, start: str = "", end: str = "") -> list[QbParty]:
    """Customers or vendors from documents and transactions, biggest first.

    Totals, document counts and bank payments are for the period from
    `start` to `end` (inclusive, open-ended when empty); open and overdue
    balances are as of today.
    """
    g.ledger.changed()
    period = parse_period(start, end)
    today = local_today()
    parties: dict[str, _Party] = {}

    def party(name: str) -> _Party:
        return parties.setdefault(name or "(no name)", _Party())

    for doc in collect(side).values():
        p = party(doc.party)
        p.email = p.email or doc.email
        if in_period(doc.date, period):
            p.docs += 1
            p.total += doc.billed
        balance = doc.billed - doc.paid
        if balance > 0:
            p.open_balance += balance
            if _status(doc, today) == "overdue":
                p.overdue += balance
        p.currency = p.currency or doc.currency
        p.last_date = max(p.last_date, doc.date or p.last_date)
        p.categories.update(doc.categories)
    for txn in g.ledger.all_entries_by_type.Transaction:
        if side.excluded(txn):
            continue
        inside = in_period(txn.date, period)
        bank = _bank_paid(side, txn)
        if bank and inside:
            party(_party(side, txn)).bank_paid += bank
        if _text(txn.meta.get("invoice")):
            continue
        positive, negative, currency = _sums(txn, side.is_category)
        if not currency:
            continue
        p = party(_party(side, txn))
        p.email = p.email or _text(txn.meta.get(f"{side.party}_email"))
        if inside:
            p.total += (
                negative - positive if side.sign > 0 else positive - negative
            )
        p.currency = p.currency or currency
        p.last_date = max(p.last_date, txn.date)
        p.categories.update(
            a.account for a in txn.postings if side.is_category(a.account)
        )
    result = [
        QbParty(
            name,
            p.email,
            p.docs,
            p.total,
            p.open_balance,
            p.overdue,
            p.currency,
            p.last_date,
            p.categories.most_common(1)[0][0] if p.categories else "",
            p.bank_paid,
        )
        for name, p in parties.items()
    ]
    result.sort(key=lambda p: (-p.total, p.name))
    return result


# --- Recording documents ------------------------------------------------


class DocForm(Struct, frozen=True):
    """An invoice or bill to book, as typed or read from a CSV row."""

    party: str
    number: str
    date: str
    amount: str
    #: Income or expense account.
    account: str
    due: str = ""
    memo: str = ""
    email: str = ""
    currency: str = ""


def _parse_form(
    side: Side, form: DocForm
) -> tuple[datetime.date, datetime.date | None, Decimal]:
    """Validated date, due date and amount, or a ValidationError."""
    if not form.party.strip():
        msg = f"enter the {side.party}"
        raise ValidationError(msg)
    if not form.number.strip():
        msg = f"enter the {side.doc} number"
        raise ValidationError(msg)
    key = doc_key(side, form.party.strip(), form.number.strip())
    if key in collect(side):
        msg = f"{side.doc} {form.number.strip()} is already in your books"
        raise ValidationError(msg)
    date = parse_date(form.date, DATE_FORMATS)
    if date is None:
        msg = f"the {side.doc} date '{form.date}' isn't a date"
        raise ValidationError(msg)
    due = parse_date(form.due, DATE_FORMATS) if form.due.strip() else None
    if form.due.strip() and due is None:
        msg = f"the due date '{form.due}' isn't a date"
        raise ValidationError(msg)
    amount = parse_amount(form.amount)
    if amount is None or amount <= 0:
        msg = "the amount must be a positive number"
        raise ValidationError(msg)
    if not side.is_category(form.account):
        msg = f"choose an account under {side.root()}"
        raise ValidationError(msg)
    if form.account not in g.ledger.accounts:
        msg = f"unknown account '{form.account}'"
        raise ValidationError(msg)
    return date, due, amount


def _doc_entry(
    side: Side,
    form: DocForm,
    date: datetime.date,
    due: datetime.date | None,
    amount: Decimal,
) -> Transaction:
    meta: dict[str, object] = {
        "invoice": form.number.strip(),
        side.party: form.party.strip(),
        "due": due or date + DEFAULT_TERMS,
    }
    if form.email.strip():
        meta[f"{side.party}_email"] = form.email.strip()
    currency = form.currency or g.ledger.options["operating_currency"][0]
    narration = f"{side.doc.capitalize()} {form.number.strip()}"
    if form.memo.strip():
        narration += f": {form.memo.strip()}"
    signed = amount * side.sign
    return create.transaction(
        meta,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
        date,
        "*",
        form.party.strip(),
        narration,
        postings=[
            create.posting(
                side.ledger_account(), create.amount(signed, currency)
            ),
            create.posting(form.account, create.amount(-signed, currency)),
        ],
    )


def _payment_entry(
    side: Side,
    number: str,
    party: str,
    date: datetime.date,
    amount: Decimal,
    currency: str,
    account: str,
) -> Transaction:
    signed = amount * side.sign
    return create.transaction(
        {"invoice": number, side.party: party},
        date,
        "*",
        party,
        f"Payment for {side.doc} {number}",
        postings=[
            create.posting(account, create.amount(signed, currency)),
            create.posting(
                side.ledger_account(), create.amount(-signed, currency)
            ),
        ],
    )


def _with_ledger_open(
    side: Side, entries: list[Transaction], first: datetime.date
) -> list[Directive]:
    """Prepend an Open for the receivable or payable account if needed."""
    account = side.ledger_account()
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
    """A recorded document's entry (to attach the PDF to)."""

    entry_hash: str


def record(side: Side, values: dict[str, str]) -> QbRecorded:
    """Book one invoice or bill through the receivable or payable account."""
    ledger = g.ledger
    ledger.changed()
    form = msgspec.convert(values, DocForm)
    date, due, amount = _parse_form(side, form)
    check_open([date])
    entry = _doc_entry(side, form, date, due, amount)
    ledger.file.insert_entries(_with_ledger_open(side, [entry], date))
    ledger.load_file()
    number, party = form.number.strip(), form.party.strip()
    return QbRecorded(
        next(
            hash_entry(txn)
            for txn in ledger.all_entries_by_type.Transaction
            if _text(txn.meta.get("invoice")) == number
            and _party(side, txn) == party
        )
    )


# --- Matching payments --------------------------------------------------


class QbPayment(Struct, frozen=True):
    """A deposit or payment that could settle an invoice or bill."""

    entry_hash: str
    date: datetime.date
    payee: str
    narration: str
    #: Bank, card or Stripe account the money moved through.
    account: str
    #: Positive amount.
    amount: Decimal
    currency: str
    #: The posting that moves to the receivable or payable account.
    category: str
    exact: bool


def _open_doc(side: Side, key: str) -> _Doc:
    doc = collect(side).get(key)
    if doc is None:
        msg = f"no {side.doc} {key}"
        raise ValidationError(msg)
    if doc.billed - doc.paid <= 0:
        msg = f"{side.doc} {doc.number} is already paid"
        raise ValidationError(msg)
    return doc


def _candidate(side: Side, txn: Transaction) -> QbPayment | None:
    """`txn` as a candidate payment, or None.

    A candidate moves money in (sales) or out (purchases) through one
    bank, card or Stripe account, from or to one income, expense or
    uncategorized account, and has no invoice number yet.
    """
    if _text(txn.meta.get("invoice")):
        return None
    money = [
        p
        for p in txn.postings
        if side.is_money(p.account)
        and p.units is not None
        and p.units.number is not None
        and p.units.number * side.sign > 0
    ]
    source = [
        p.account
        for p in txn.postings
        if side.is_category(p.account) or p.account.endswith("Uncategorized")
    ]
    if len(money) != 1 or len(source) != 1:
        return None
    units = money[0].units
    return QbPayment(
        hash_entry(txn),
        txn.date,
        txn.payee or "",
        txn.narration or "",
        money[0].account,
        abs(units.number),
        units.currency,
        source[0],
        exact=False,
    )


def payment_candidates(side: Side, key: str) -> list[QbPayment]:
    """Payments that could settle the document `key`, best match first."""
    g.ledger.changed()
    doc = _open_doc(side, key)
    balance = doc.billed - doc.paid
    start = (doc.date or datetime.date.min) - datetime.timedelta(days=7)
    words = set(re.findall(r"\w{3,}", doc.party.casefold()))
    found = []
    for txn in g.ledger.all_entries_by_type.Transaction:
        if txn.date < start:
            continue
        payment = _candidate(side, txn)
        if payment is None or payment.currency != doc.currency:
            continue
        text = f"{payment.payee} {payment.narration}".casefold()
        named = any(w in text for w in words)
        exact = payment.amount == balance
        found.append(
            (
                (not exact, not named, abs((payment.date - start).days)),
                msgspec.structs.replace(payment, exact=exact),
            )
        )
    found.sort(key=lambda pair: pair[0])
    return [payment for _, payment in found[:20]]


def match_payment(side: Side, key: str, entry_hash: str) -> str:
    """Mark the transaction `entry_hash` as the payment for `key`."""
    ledger = g.ledger
    ledger.changed()
    doc = _open_doc(side, key)
    entry = ledger.get_entry(entry_hash)
    check_open([entry.date])
    payment = (
        _candidate(side, entry) if isinstance(entry, Transaction) else None
    )
    if payment is None:
        msg = f"that transaction isn't a payment that can settle a {side.doc}"
        raise ValidationError(msg)
    # An open document has a ledger posting, so that account is open.
    source, sha256sum = get_entry_slice(entry)
    header, *body = source.split("\n")
    meta = [f'  invoice: "{doc.number}"']
    if side.party not in entry.meta:
        meta.append(f'  {side.party}: "{doc.party}"')
    posting = re.compile(rf"^(\s+){re.escape(payment.category)}(?=\s|$)")
    account = side.ledger_account()
    new_source = "\n".join(
        [
            header,
            *meta,
            *(
                posting.sub(lambda m: m.group(1) + account, line)
                for line in body
            ),
        ]
    )
    ledger.file.save_entry_slice(entry_hash, new_source, sha256sum)
    return f"Matched to {side.doc} {doc.number}."


# --- Importing from a CSV -----------------------------------------------


def _synonyms(side: Side) -> dict[str, tuple[str, ...]]:
    """Fields and header names that mean them, most specific first."""
    doc = side.doc
    return {
        "number": (
            f"{doc} number",
            f"{doc} no",
            f"{doc} #",
            f"{doc} id",
            "invoice number",
            "invoice no",
            "invoice #",
            "reference",
            "ref no",
            "number",
            "no.",
            "num",
            doc,
            "id",
        ),
        "party": side.party_columns,
        "email": (f"{side.party} email", "client email", "email"),
        "date": (
            f"{doc} date",
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
            f"{doc} total",
            "amount",
            "amount due",
            f"{doc} amount",
        ),
        "paid": ("amount paid", "paid amount", "paid"),
        "paid_date": ("paid at (utc)", "paid at", "date paid", "paid date"),
        "status": ("status", f"{doc} status"),
        "currency": ("currency",),
    }


def _read_csv(content: str) -> tuple[list[str], list[list[str]]]:
    rows = [
        row
        for row in csv.reader(io.StringIO(content.lstrip("﻿")))
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        msg = "the file is empty"
        raise ValidationError(msg)
    return [cell.strip() for cell in rows[0]], rows[1:]


def guess_mapping(side: Side, header: list[str]) -> dict[str, str]:
    """Columns for each field, by header name."""
    lowered = {column.casefold(): column for column in header}
    mapping: dict[str, str] = {}
    for field_name, names in _synonyms(side).items():
        for name in names:
            column = lowered.get(name)
            if column is not None and column not in mapping.values():
                mapping[field_name] = column
                break
    return mapping


class QbDocRow(Struct, frozen=True):
    """A CSV row read as an invoice or bill."""

    line: int
    number: str
    party: str
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


class QbDocPreview(Struct, frozen=True):
    """How a CSV of invoices or bills will be imported."""

    header: list[str]
    mapping: dict[str, str]
    rows: list[QbDocRow]


def _rows(
    side: Side, content: str, mapping: dict[str, str] | None
) -> tuple[list[str], dict[str, str], list[QbDocRow]]:
    header, raw_rows = _read_csv(content)
    mapping = {
        k: v
        for k, v in (mapping or guess_mapping(side, header)).items()
        if v in header
    }
    index = {
        field_name: header.index(col) for field_name, col in mapping.items()
    }
    existing = set(collect(side))
    seen: set[str] = set()
    rows = []
    for line, raw in enumerate(raw_rows, start=2):

        def cell(name: str, raw: list[str] = raw) -> str:
            i = index.get(name)
            return raw[i].strip() if i is not None and i < len(raw) else ""

        number, party, status = cell("number"), cell("party"), cell("status")
        date = parse_date(cell("date"), DATE_FORMATS)
        amount = parse_amount(cell("amount"))
        paid = parse_amount(cell("paid"))
        if paid is None:
            paid = amount if status.casefold() == "paid" and amount else ZERO
        missing = [
            name
            for name, value in (
                (f"{side.doc} number", number),
                (side.party, party),
                ("date", date),
                ("amount", amount),
            )
            if not value
        ]
        key = doc_key(side, party, number)
        if status.casefold() in SKIP_STATUSES:
            state, problem = "skipped", f"status is {status}"
        elif missing:
            state, problem = "invalid", "missing " + ", ".join(missing)
        elif key in existing or key in seen:
            state, problem = "duplicate", "already in your books"
        else:
            state, problem = "new", ""
        seen.add(key)
        rows.append(
            QbDocRow(
                line=line,
                number=number,
                party=party,
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


def preview_csv(
    side: Side, content: str, mapping: dict[str, str] | None
) -> QbDocPreview:
    """Read a CSV; `mapping` overrides the guessed columns."""
    g.ledger.changed()
    header, used, rows = _rows(side, content, mapping)
    return QbDocPreview(header, used, rows)


class QbDocImport(Struct, frozen=True):
    """What an import booked."""

    docs: int
    payments: int


def import_csv(
    side: Side,
    content: str,
    mapping: dict[str, str],
    account: str,
    payment_account: str,
) -> QbDocImport:
    """Book the new rows of a CSV.

    With `payment_account`, the paid part of each document is booked as a
    payment through that account (only when those payments aren't
    imported from a bank, card or Stripe as well).
    """
    ledger = g.ledger
    ledger.changed()
    if account not in ledger.accounts or not side.is_category(account):
        msg = f"choose the {side.root()} account for these {side.doc}s"
        raise ValidationError(msg)
    if payment_account and payment_account not in ledger.accounts:
        msg = f"unknown account '{payment_account}'"
        raise ValidationError(msg)
    _, _, rows = _rows(side, content, mapping)
    default_currency = ledger.options["operating_currency"][0]
    entries: list[Transaction] = []
    payments = 0
    for row in rows:
        if row.state != "new" or row.date is None or row.amount is None:
            continue
        currency = row.currency or default_currency
        form = DocForm(
            party=row.party,
            number=row.number,
            date=row.date.isoformat(),
            amount=str(row.amount),
            account=account,
            email=row.email,
            currency=currency,
        )
        entries.append(_doc_entry(side, form, row.date, row.due, row.amount))
        paid = min(row.paid, row.amount)
        if payment_account and paid > 0:
            payments += 1
            entries.append(
                _payment_entry(
                    side,
                    row.number,
                    row.party,
                    row.paid_date or row.date,
                    paid,
                    currency,
                    payment_account,
                )
            )
    if not entries:
        msg = f"there are no new {side.doc}s in this file"
        raise ValidationError(msg)
    check_open(e.date for e in entries)
    ledger.file.insert_entries(
        _with_ledger_open(side, entries, min(e.date for e in entries))
    )
    return QbDocImport(len(entries) - payments, payments)
