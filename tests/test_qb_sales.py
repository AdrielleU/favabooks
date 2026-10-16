from __future__ import annotations

import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Any
from typing import TYPE_CHECKING

import pytest
from beancount import loader

from fava.application import create_app
from fava.qb_docs import guess_mapping
from fava.qb_docs import SALES

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from flask.testing import FlaskClient

LEDGER = """
option "title" "Sales"
option "operating_currency" "USD"

2026-01-01 open Assets:Bank:Checking
2026-01-01 open Assets:Stripe
2026-01-01 open Income:Services
2026-01-01 open Income:Old
2026-01-02 close Income:Old
2026-01-01 open Expenses:Fees:Stripe
2026-01-01 open Expenses:Uncategorized
2026-01-01 open Equity:Opening

2026-02-05 * "Acme Dental" "Invoice in_1 (February)"
  customer: "Acme Dental"
  customer_email: "ap@acme.test"
  invoice: "in_1"
  Assets:Stripe            970.00 USD
  Expenses:Fees:Stripe      30.00 USD
  Income:Services       -1000.00 USD

2026-02-07 * "ZenBusiness" "A vendor's invoice, not a sale"
  invoice: "1177261"
  Expenses:Uncategorized     99.00 USD
  Assets:Bank:Checking

2026-02-10 * "Walk-in" "Cash sale"
  Assets:Bank:Checking      50.00 USD
  Income:Services

2026-02-11 * "Tips"
  Assets:Bank:Checking       5.00 USD
  Income:Services

2026-03-01 * "ACME DENTAL" "Deposit"
  customer: "Acme Dental"
  Assets:Bank:Checking     400.00 USD
  Expenses:Uncategorized

2026-03-02 * "Someone" "Deposit"
  Assets:Bank:Checking     400.00 USD
  Income:Services

2026-03-03 * "Transfer" "Not a payment"
  Assets:Bank:Checking      10.00 USD
  Equity:Opening
"""

STRIPE_CSV = """﻿id,Customer Name,Customer Email,Date (UTC),\
Due Date (UTC),Total,Amount Paid,Status,Currency
in_1,Acme Dental,ap@acme.test,2026-02-05 10:00,,1000.00,1000.00,paid,usd
in_2,Bolt Labs,hi@bolt.test,2026-03-04 09:30,2026-04-03,250.00,250.00,paid,usd
in_3,Bolt Labs,,2026-03-05 09:30,,99.00,0.00,draft,usd
in_4,,,2026-03-06 09:30,,,0,open,usd
in_2,Bolt Labs,,2026-03-04 09:30,,250.00,250.00,paid,usd

"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    monkeypatch.setattr(
        "fava.qb_docs.local_today", lambda: datetime.date(2026, 3, 10)
    )
    ledger = tmp_path / "sales.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def call(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, Any]:
    if method == "get":
        response = client.get(f"/sales/api/{endpoint}", query_string=kw)
    else:
        response = client.put(f"/sales/api/{endpoint}", json=kw)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def ok(client: FlaskClient, method: str, endpoint: str, **kw: object) -> Any:  # noqa: ANN401
    status, data = call(client, method, endpoint, **kw)
    assert status == HTTPStatus.OK.value, data
    return data


def error(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> str:
    status, data = call(client, method, endpoint, **kw)
    assert status == HTTPStatus.BAD_REQUEST.value, data
    return str(data["detail"])


def invoices(client: FlaskClient) -> dict[str, dict[str, Any]]:
    return {i["key"]: i for i in ok(client, "get", "qb_invoices")["docs"]}


def record(client: FlaskClient, **kw: str) -> Any:  # noqa: ANN401
    form = {
        "party": "Acme Dental",
        "number": "INV-1",
        "date": "2026-02-20",
        "amount": "400",
        "account": "Income:Services",
        **kw,
    }
    return call(client, "put", "qb_invoice", doc=form)


def test_guess_mapping() -> None:
    assert guess_mapping(
        SALES, ["No.", "Customer", "Date", "Amount", "Name"]
    ) == {
        "number": "No.",
        "party": "Customer",
        "date": "Date",
        "amount": "Amount",
    }


def test_stripe_sale_is_a_paid_invoice(client: FlaskClient) -> None:
    data = ok(client, "get", "qb_invoices")
    assert data["ledger_account"] == "Assets:AccountsReceivable"
    assert data["accounts"] == ["Income:Services"]
    (stripe,) = data["docs"]
    assert stripe["number"] == "in_1"
    assert (stripe["status"], stripe["direct"], stripe["balance"]) == (
        "paid",
        True,
        "0.00",
    )
    assert stripe["party"] == "Acme Dental"


def test_record_and_match(client: FlaskClient, tmp_path: Path) -> None:
    status, data = record(client)
    assert status == HTTPStatus.OK.value, data
    assert data["entry_hash"]
    text = (tmp_path / "sales.beancount").read_text()
    assert "2026-02-05 open Assets:AccountsReceivable" in text
    assert "due: 2026-03-22" in text

    inv = invoices(client)["INV-1"]
    assert (inv["status"], inv["direct"], inv["balance"]) == (
        "open",
        False,
        "400",
    )
    assert inv["due"] == "2026-03-22"

    deposits = ok(client, "get", "qb_invoice_payments", key="INV-1")
    assert [(d["payee"], d["exact"]) for d in deposits] == [
        ("ACME DENTAL", True),
        ("Someone", True),
    ]
    assert deposits[0]["category"] == "Expenses:Uncategorized"
    ok(
        client,
        "put",
        "qb_invoice_payment",
        key="INV-1",
        entry_hash=deposits[0]["entry_hash"],
    )
    inv = invoices(client)["INV-1"]
    assert (inv["status"], inv["paid"]) == ("paid", "400.00")
    assert len(inv["entry_hashes"]) == 2
    _, errors, _ = loader.load_file(str(tmp_path / "sales.beancount"))
    assert errors == []

    # Partly paid, then overdue once the due date passes.
    record(client, number="INV-2", amount="1,000.00", due="2026-12-31")
    someone = ok(client, "get", "qb_invoice_payments", key="INV-2")
    assert [d["payee"] for d in someone] == ["Someone"]
    assert someone[0]["exact"] is False
    ok(
        client,
        "put",
        "qb_invoice_payment",
        key="INV-2",
        entry_hash=someone[0]["entry_hash"],
    )
    assert invoices(client)["INV-2"]["status"] == "partial"
    record(client, number="INV-3", due="03/01/2026", party="Bolt Labs")
    assert invoices(client)["INV-3"]["status"] == "overdue"

    customers = {c["name"]: c for c in ok(client, "get", "qb_customers")}
    acme = customers["Acme Dental"]
    assert acme["email"] == "ap@acme.test"
    assert acme["docs"] == 3
    assert Decimal(acme["total"]) == Decimal(2400)
    assert Decimal(acme["open_balance"]) == Decimal(600)
    assert Decimal(acme["overdue"]) == 0
    assert Decimal(customers["Bolt Labs"]["overdue"]) == Decimal(400)
    assert customers["Walk-in"]["total"] == "50.00"
    assert customers["(no name)"]["total"] == "5.00"
    assert next(iter(customers)) == "Acme Dental"


def test_record_errors(client: FlaskClient) -> None:
    def bad(**kw: str) -> str:
        status, data = record(client, **kw)
        assert status == HTTPStatus.BAD_REQUEST.value, data
        return str(data["detail"])

    assert "already in your books" in bad(number="in_1")
    assert "customer" in bad(party=" ")
    assert "invoice number" in bad(number="")
    assert "isn't a date" in bad(date="soon")
    assert "due date" in bad(due="later")
    assert "positive" in bad(amount="-5")
    assert "under Income" in bad(account="Assets:Stripe")
    assert "unknown account" in bad(account="Income:Nope")


def test_payment_errors(client: FlaskClient) -> None:
    assert "no invoice" in error(
        client, "get", "qb_invoice_payments", key="nope"
    )
    assert "already paid" in error(
        client, "get", "qb_invoice_payments", key="in_1"
    )
    record(client, email="ap@acme.test", memo="March work")
    transfer = next(
        row["entry_hash"]
        for row in ok(client, "get", "qb_transactions")["rows"]
        if row["payee"] == "Transfer"
    )
    assert "isn't a payment" in error(
        client,
        "put",
        "qb_invoice_payment",
        key="INV-1",
        entry_hash=transfer,
    )
    inv = invoices(client)["INV-1"]
    assert inv["memo"] == "Invoice INV-1: March work"


def test_csv_import(client: FlaskClient, tmp_path: Path) -> None:
    preview = ok(client, "put", "qb_invoice_csv_preview", content=STRIPE_CSV)
    assert preview["mapping"]["number"] == "id"
    assert preview["mapping"]["paid"] == "Amount Paid"
    states = [(r["number"], r["state"]) for r in preview["rows"]]
    assert states == [
        ("in_1", "duplicate"),
        ("in_2", "new"),
        ("in_3", "skipped"),
        ("in_4", "invalid"),
        ("in_2", "duplicate"),
    ]
    assert "customer, amount" in preview["rows"][3]["problem"]
    new = preview["rows"][1]
    assert (new["date"], new["due"], new["currency"]) == (
        "2026-03-04",
        "2026-04-03",
        "USD",
    )

    # A custom mapping: without the paid column, "paid" status means paid.
    mapping = {**preview["mapping"], "paid": "Missing"}
    custom = ok(
        client,
        "put",
        "qb_invoice_csv_preview",
        content=STRIPE_CSV,
        mapping=mapping,
    )
    assert "paid" not in custom["mapping"]
    assert custom["rows"][1]["paid"] == "250.00"
    assert custom["rows"][2]["paid"] == "0"

    imported = ok(
        client,
        "put",
        "qb_invoice_csv_import",
        content=STRIPE_CSV,
        mapping=preview["mapping"],
        account="Income:Services",
        payment_account="Assets:Stripe",
    )
    assert imported == {"docs": 1, "payments": 1}
    inv = invoices(client)["in_2"]
    assert (inv["status"], inv["amount"]) == ("paid", "250.00")
    _, errors, _ = loader.load_file(str(tmp_path / "sales.beancount"))
    assert errors == []

    def bad(**kw: object) -> str:
        body = {
            "content": STRIPE_CSV,
            "mapping": preview["mapping"],
            "account": "Income:Services",
            **kw,
        }
        return error(client, "put", "qb_invoice_csv_import", **body)

    assert "no new invoices" in bad()
    assert "Income account" in bad(account="Income:Nope")
    assert "unknown account" in bad(payment_account="Assets:Nope")
    assert "empty" in error(
        client, "put", "qb_invoice_csv_preview", content="\n\n"
    )


def test_csv_import_without_payments(client: FlaskClient) -> None:
    csv_text = (
        "Invoice #,Client,Issue date,Amount\nA-1,Zed,03/09/2026,$75.00\n"
    )
    imported = ok(
        client,
        "put",
        "qb_invoice_csv_import",
        content=csv_text,
        mapping={
            "number": "Invoice #",
            "party": "Client",
            "date": "Issue date",
            "amount": "Amount",
        },
        account="Income:Services",
    )
    assert imported == {"docs": 1, "payments": 0}
    inv = invoices(client)["A-1"]
    assert (inv["party"], inv["status"], inv["due"]) == (
        "Zed",
        "open",
        "2026-04-08",
    )
