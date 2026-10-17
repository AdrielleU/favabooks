"""Currencies and prices (qb-fork).

Which currencies (and other commodities) the books use, their prices in
the home currency, and which ones are missing a price, so reports would
leave their amounts out. Prices are Beancount `price` directives; adding
and deleting them edits the ledger like any other entry.
"""

from __future__ import annotations

import datetime
from collections import Counter
from decimal import Decimal
from decimal import InvalidOperation
from typing import cast
from typing import TYPE_CHECKING

from beancount.core import data
from beancount.core.amount import Amount
from msgspec import Struct

from fava.beans.funcs import hash_entry
from fava.context import g
from fava.core.file import get_entry_slice
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.qb_close import check_open

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Directive


class QbPrice(Struct, frozen=True):
    """A price entry: one `currency` costs `price` `quote`."""

    entry_hash: str
    date: datetime.date
    currency: str
    price: Decimal
    quote: str


class QbCurrency(Struct, frozen=True):
    """A currency or commodity the books use."""

    currency: str
    #: Its name from a `commodity` entry ("Euro"), or "".
    name: str
    postings: int
    last_used: datetime.date | None
    #: Latest and previous price in the home currency (None if none).
    latest: QbPrice | None
    previous: QbPrice | None
    #: Used in postings but has no price to convert it for reports.
    needs_price: bool


class QbPrices(Struct, frozen=True):
    """The home currency, every other currency used, and all prices."""

    home: str
    currencies: list[QbCurrency]
    prices: list[QbPrice]


def _home() -> str:
    currencies = g.ledger.options["operating_currency"]
    return currencies[0] if currencies else "USD"


def _prices() -> list[QbPrice]:
    return [
        QbPrice(
            hash_entry(p),
            p.date,
            p.currency,
            p.amount.number,
            p.amount.currency,
        )
        for p in g.ledger.all_entries_by_type.Price
    ]


@api_endpoint
def get_qb_prices() -> QbPrices:
    """Currencies used (other than the home one) and every price."""
    g.ledger.changed()
    home = _home()
    used: Counter[str] = Counter()
    last: dict[str, datetime.date] = {}
    for txn in g.ledger.all_entries_by_type.Transaction:
        for posting in txn.postings:
            units = posting.units
            if units is None or units.currency == home:
                continue
            used[units.currency] += 1
            last[units.currency] = txn.date
    prices = _prices()
    names = {
        c.currency: str(c.meta.get("name", ""))
        for c in g.ledger.all_entries_by_type.Commodity
        if c.meta
    }
    priced = {p.currency for p in prices} | {
        p.quote for p in prices if p.currency == home
    }
    currencies = []
    for currency in sorted(set(used) | priced | set(names)):
        if currency == home:
            continue
        history = sorted(
            (p for p in prices if p.currency == currency and p.quote == home),
            key=lambda p: p.date,
        )
        currencies.append(
            QbCurrency(
                currency=currency,
                name=names.get(currency, ""),
                postings=used[currency],
                last_used=last.get(currency),
                latest=history[-1] if history else None,
                previous=history[-2] if len(history) > 1 else None,
                needs_price=bool(used[currency]) and currency not in priced,
            )
        )
    currencies.sort(key=lambda c: (not c.needs_price, -c.postings, c.currency))
    prices.sort(key=lambda p: (p.date, p.currency), reverse=True)
    return QbPrices(home, currencies, prices)


def _currency(value: str, label: str) -> str:
    currency = value.strip().upper()
    if (
        not currency
        or not currency.replace(".", "").replace("_", "").isalnum()
    ):
        msg = f"enter the {label}, like EUR or AAPL"
        raise ValidationError(msg)
    return currency


@api_endpoint
def put_qb_price(date: str, currency: str, price: str, quote: str = "") -> str:
    """Add a price: on `date`, one `currency` costs `price` `quote`."""
    ledger = g.ledger
    ledger.changed()
    try:
        day = datetime.date.fromisoformat(date)
    except ValueError:
        msg = "the date looks like 2026-01-31"
        raise ValidationError(msg) from None
    check_open([day])
    base = _currency(currency, "currency")
    target = _currency(quote or _home(), "price currency")
    if base == target:
        msg = "a currency's price must be in another currency"
        raise ValidationError(msg)
    try:
        number = Decimal(price.replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        number = Decimal(0)
    if number <= 0:
        msg = "the price must be a positive number"
        raise ValidationError(msg)
    entry = data.Price({}, day, base, Amount(number, target))
    ledger.file.insert_entries([cast("Directive", entry)])
    return f"Added the price of {base} on {day}: {number} {target}."


@api_endpoint
def delete_qb_price(entry_hash: str) -> str:
    """Delete a price entry."""
    ledger = g.ledger
    ledger.changed()
    entry = next(
        (
            p
            for p in ledger.all_entries_by_type.Price
            if hash_entry(p) == entry_hash
        ),
        None,
    )
    if entry is None:
        msg = "that price isn't in the books (any more)"
        raise ValidationError(msg)
    check_open([entry.date])
    _, sha256sum = get_entry_slice(entry)
    ledger.file.delete_entry_slice(entry_hash, sha256sum)
    return f"Deleted the price of {entry.currency} on {entry.date}."
