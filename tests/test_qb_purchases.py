from __future__ import annotations

import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Any
from typing import TYPE_CHECKING

import pytest
from beancount import loader

from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from flask.testing import FlaskClient

LEDGER = """
option "title" "Purchases"
option "operating_currency" "USD"

2026-01-01 open Assets:Bank:Checking
2026-01-01 open Assets:Stripe
2026-01-01 open Liabilities:CreditCard:Visa
2026-01-01 open Income:Services
2026-01-01 open Expenses:Software
2026-01-01 open Expenses:Legal
2026-01-01 open Expenses:Fees:Stripe
2026-01-01 open Expenses:Uncategorized

2026-02-01 * "ZenBusiness" "Formation"
  invoice: 1177261
  Expenses:Legal           184.00 USD
  Liabilities:CreditCard:Visa

2026-02-02 * "Telnyx" "Usage from prepaid balance"
  invoice: 3
  Expenses:Software          0.00 USD
  Liabilities:CreditCard:Visa  0.00 USD

2026-02-03 * "Acme" "A sale with a Stripe fee, not a bill"
  invoice: "in_1"
  customer: "Acme"
  Assets:Stripe            970.00 USD
  Expenses:Fees:Stripe      30.00 USD
  Income:Services       -1000.00 USD

2026-02-04 * "Coffee shop" "No invoice number"
  Expenses:Software          5.00 USD
  Assets:Bank:Checking

2026-03-01 * "WIRE TO DESIGN CO" "Payment"
  Assets:Bank:Checking    -500.00 USD
  Expenses:Uncategorized
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    monkeypatch.setattr(
        "fava.qb_docs.local_today", lambda: datetime.date(2026, 3, 10)
    )
    ledger = tmp_path / "purchases.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def call(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, Any]:
    if method == "get":
        response = client.get(f"/purchases/api/{endpoint}", query_string=kw)
    else:
        response = client.put(f"/purchases/api/{endpoint}", json=kw)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def ok(client: FlaskClient, method: str, endpoint: str, **kw: object) -> Any:  # noqa: ANN401
    status, data = call(client, method, endpoint, **kw)
    assert status == HTTPStatus.OK.value, data
    return data


def bills(client: FlaskClient) -> dict[str, dict[str, Any]]:
    return {b["key"]: b for b in ok(client, "get", "qb_bills")["docs"]}


def record(client: FlaskClient, **kw: str) -> tuple[int, Any]:
    form = {
        "party": "Design Co",
        "number": "D-7",
        "date": "2026-02-20",
        "amount": "500",
        "account": "Expenses:Software",
        **kw,
    }
    return call(client, "put", "qb_bill", doc=form)


def test_expenses_with_invoice_numbers_are_paid_bills(
    client: FlaskClient,
) -> None:
    data = ok(client, "get", "qb_bills")
    assert data["ledger_account"] == "Liabilities:AccountsPayable"
    assert data["accounts"][0] == "Expenses:Software"
    found = bills(client)
    assert set(found) == {"ZenBusiness / 1177261", "Telnyx / 3"}
    zen = found["ZenBusiness / 1177261"]
    assert (zen["status"], zen["direct"], zen["amount"]) == (
        "paid",
        True,
        "184.00",
    )
    assert zen["paid_with"] == ["Liabilities:CreditCard:Visa"]
    assert zen["categories"] == ["Expenses:Legal"]
    telnyx = found["Telnyx / 3"]
    assert (telnyx["date"], telnyx["status"]) == ("2026-02-02", "paid")


def test_record_and_pay_a_bill(client: FlaskClient, tmp_path: Path) -> None:
    status, data = record(client)
    assert status == HTTPStatus.OK.value, data
    text = (tmp_path / "purchases.beancount").read_text()
    assert "open Liabilities:AccountsPayable" in text
    bill = bills(client)["Design Co / D-7"]
    assert (bill["status"], bill["balance"], bill["direct"]) == (
        "open",
        "500",
        False,
    )

    # Same number from another vendor is a different bill.
    assert record(client, party="Other Co")[0] == HTTPStatus.OK.value
    status, data = record(client)
    assert status == HTTPStatus.BAD_REQUEST.value
    assert "already in your books" in data["detail"]

    payments = ok(client, "get", "qb_bill_payments", key="Design Co / D-7")
    assert [(p["payee"], p["exact"], p["amount"]) for p in payments] == [
        ("WIRE TO DESIGN CO", True, "500.00"),
    ]
    assert payments[0]["account"] == "Assets:Bank:Checking"
    ok(
        client,
        "put",
        "qb_bill_payment",
        key="Design Co / D-7",
        entry_hash=payments[0]["entry_hash"],
    )
    bill = bills(client)["Design Co / D-7"]
    assert (bill["status"], bill["paid"]) == ("paid", "500.00")
    assert bill["paid_with"] == ["Assets:Bank:Checking"]
    _, errors, _ = loader.load_file(str(tmp_path / "purchases.beancount"))
    assert errors == []


def test_vendors(client: FlaskClient) -> None:
    record(client)
    vendors = {v["name"]: v for v in ok(client, "get", "qb_vendors")}
    assert "Acme" not in vendors
    assert next(iter(vendors)) == "Design Co"
    zen = vendors["ZenBusiness"]
    assert (zen["docs"], Decimal(zen["total"]), zen["category"]) == (
        1,
        Decimal(184),
        "Expenses:Legal",
    )
    coffee = vendors["Coffee shop"]
    assert (coffee["docs"], coffee["total"]) == (0, "5.00")
    assert Decimal(vendors["Design Co"]["open_balance"]) == Decimal(500)


def test_bill_csv_import(client: FlaskClient) -> None:
    content = (
        "Bill No,Vendor,Bill Date,Due Date,Amount,Status\n"
        "B-1,Paper Co,2026-03-01,2026-03-31,40.00,open\n"
        "1177261,ZenBusiness,2026-02-01,,184,paid\n"
    )
    preview = ok(client, "put", "qb_bill_csv_preview", content=content)
    assert preview["mapping"] == {
        "number": "Bill No",
        "party": "Vendor",
        "date": "Bill Date",
        "due": "Due Date",
        "amount": "Amount",
        "status": "Status",
    }
    assert [r["state"] for r in preview["rows"]] == ["new", "duplicate"]
    imported = ok(
        client,
        "put",
        "qb_bill_csv_import",
        content=content,
        mapping=preview["mapping"],
        account="Expenses:Software",
    )
    assert imported == {"docs": 1, "payments": 0}
    bill = bills(client)["Paper Co / B-1"]
    assert (bill["status"], bill["due"]) == ("open", "2026-03-31")
    status, data = call(
        client,
        "put",
        "qb_bill_csv_import",
        content=content,
        mapping=preview["mapping"],
        account="Income:Services",
    )
    assert status == HTTPStatus.BAD_REQUEST.value
    assert "Expenses account" in data["detail"]
