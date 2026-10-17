from __future__ import annotations

import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Any
from typing import TYPE_CHECKING

import pytest

from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from flask.testing import FlaskClient

LEDGER = """
option "title" "Reports Co"
option "operating_currency" "USD"

2024-01-01 open Assets:Bank:Checking
2024-01-01 open Liabilities:CreditCard:Visa
2024-01-01 open Equity:Opening-Balances
2024-01-01 open Income:Sales
2024-01-01 open Expenses:COGS:Materials
2024-01-01 open Expenses:Software
2024-01-01 open Expenses:Travel
2024-01-01 open Expenses:Uncategorized

2024-01-01 * "Owner" "Opening balance"
  Assets:Bank:Checking   1000.00 USD
  Equity:Opening-Balances

2024-06-01 * "Client" "Last year's sale"
  Assets:Bank:Checking    300.00 USD
  Income:Sales

2025-01-15 * "Client" "January sale"
  Assets:Bank:Checking    500.00 USD
  Income:Sales

2025-01-20 * "Supplier" "Materials"
  Expenses:COGS:Materials 100.00 USD
  Assets:Bank:Checking

2025-02-10 ! "SaaS" "Subscription"
  Expenses:Software        20.00 USD
  Liabilities:CreditCard:Visa

2025-03-05 * "Hotel" "Trip"
  Expenses:Travel          50.00 EUR @@ 55.00 USD
  Liabilities:CreditCard:Visa  -55.00 USD

2025-03-06 * "Kiosk" "Paid in a currency without prices"
  Expenses:Travel          10.00 XYZ
  Assets:Cash:XYZ         -10.00 XYZ

2025-03-07 * "Designer" "Logo"
  Expenses:Uncategorized  700.00 USD
  Assets:Bank:Checking

2025-03-08 * "Cafe" "Lunch"
  document: "lunch.pdf"
  Expenses:Travel          10.00 GBP
  Assets:Bank:Checking    -13.00 USD

2025-03-09 * "Broker" "Shares at cost"
  Assets:Broker              2 STOCK {50.00 USD}
  Assets:Bank:Checking    -100.00 USD

2025-03-01 price GBP 1.30 USD
2024-01-01 open Assets:Cash:XYZ
2024-01-01 open Assets:Broker
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    monkeypatch.setattr(
        "fava.qb_reports.local_today", lambda: datetime.date(2025, 3, 31)
    )
    ledger = tmp_path / "reports.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def slug(client: FlaskClient) -> str:
    """The ledger's URL slug (from its title)."""
    response = client.get("/")
    return response.headers["Location"].strip("/").split("/")[-2]


def call(client: FlaskClient, endpoint: str, **kw: object) -> tuple[int, Any]:
    response = client.get(f"/{slug(client)}/api/{endpoint}", query_string=kw)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def ok(client: FlaskClient, endpoint: str, **kw: object) -> Any:  # noqa: ANN401
    status, data = call(client, endpoint, **kw)
    assert status == HTTPStatus.OK.value, data
    return data


def blocks(data: Any) -> dict[str, Any]:  # noqa: ANN401
    return {b["key"]: b for b in data["blocks"]}


def numbers(values: list[str]) -> list[Decimal]:
    return [Decimal(v) for v in values]


def test_profit_loss(client: FlaskClient) -> None:
    data = ok(client, "qb_profit_loss", start="2025-01-01", end="2025-12-31")
    assert (data["title"], data["company"], data["currency"]) == (
        "Profit and loss",
        "Reports Co",
        "USD",
    )
    b = blocks(data)
    assert numbers(b["income"]["amounts"]) == [Decimal(500)]
    assert numbers(b["cogs"]["amounts"]) == [Decimal(100)]
    assert numbers(b["gross"]["amounts"]) == [Decimal(400)]
    # Software 20 + travel 55 (at price) + 13 (GBP at 1.30) + uncategorized.
    assert numbers(b["expenses"]["amounts"]) == [Decimal("788.00")]
    assert numbers(b["net"]["amounts"]) == [Decimal("-388.00")]
    travel = next(
        n for n in b["expenses"]["node"]["children"] if n["name"] == "Travel"
    )
    assert numbers(travel["amounts"]) == [Decimal("68.00")]
    assert data["unconverted"] == ["10.00 XYZ"]
    cogs = b["cogs"]["node"]
    assert [c["name"] for c in cogs["children"]] == ["COGS"]

    # No dates: from the first to the last transaction; no COGS lines.
    all_time = blocks(ok(client, "qb_profit_loss", end="2024-12-31"))
    assert "gross" not in all_time
    assert numbers(all_time["income"]["amounts"]) == [Decimal(300)]


def test_profit_loss_columns(client: FlaskClient) -> None:
    months = ok(
        client,
        "qb_profit_loss",
        start="2025-01-10",
        end="2025-03-31",
        by="month",
    )
    assert [c["label"] for c in months["columns"]] == [
        "Jan 2025",
        "Feb 2025",
        "Mar 2025",
        "Total",
    ]
    assert months["columns"][0]["start"] == "2025-01-10"
    assert numbers(blocks(months)["income"]["amounts"]) == [
        Decimal(500),
        0,
        0,
        Decimal(500),
    ]
    quarters = ok(
        client,
        "qb_profit_loss",
        start="2024-05-01",
        end="2025-03-31",
        by="quarter",
    )
    assert [c["label"] for c in quarters["columns"]] == [
        "Q2 2024",
        "Q3 2024",
        "Q4 2024",
        "Q1 2025",
        "Total",
    ]
    years = ok(client, "qb_profit_loss", by="year")
    assert [c["label"] for c in years["columns"]] == ["2024", "2025", "Total"]
    compared = ok(
        client,
        "qb_profit_loss",
        start="2025-01-01",
        end="2025-12-31",
        compare="1",
    )
    assert compared["columns"][1] == {
        "label": "Previous period",
        "start": "2024-01-01",
        "end": "2024-12-31",
    }
    assert numbers(blocks(compared)["income"]["amounts"]) == [
        Decimal(500),
        Decimal(300),
    ]
    # Not whole months: the same number of days before.
    days = ok(
        client,
        "qb_profit_loss",
        start="2025-03-10",
        end="2025-03-19",
        compare="1",
    )
    assert days["columns"][1]["start"] == "2025-02-28"
    assert days["columns"][1]["end"] == "2025-03-09"
    status, data = call(
        client, "qb_profit_loss", start="2025-02-01", end="2025-01-01"
    )
    assert status == HTTPStatus.BAD_REQUEST.value
    assert "before the start" in data["detail"]


def test_balance_sheet(client: FlaskClient) -> None:
    data = ok(client, "qb_balance_sheet", as_of="2025-03-31", compare="1")
    assert [c["label"] for c in data["columns"]] == [
        "As of 2025-03-31",
        "As of 2024-03-31",
    ]
    b = blocks(data)
    assets = numbers(b["assets"]["amounts"])
    total = numbers(b["liabilities_equity"]["amounts"])
    # Cash in XYZ can't be converted, so only checking counts here.
    assert assets == [Decimal("987.00"), Decimal(1000)]
    assert total == assets
    equity = {n["name"]: n for n in b["equity"]["node"]["children"]}
    assert numbers(equity["Retained earnings"]["amounts"]) == [Decimal(300), 0]
    assert numbers(equity["Net income"]["amounts"]) == [
        Decimal("-388.00"),
        0,
    ]
    assert numbers(b["liabilities"]["amounts"]) == [Decimal(75), 0]
    leap = ok(client, "qb_balance_sheet", as_of="2024-02-29", compare="1")
    assert leap["columns"][1]["end"] == "2023-02-28"
    # Default: today (or the last transaction, whichever is later).
    assert ok(client, "qb_balance_sheet")["columns"][0]["end"] == "2025-03-31"


def test_trial_balance(client: FlaskClient) -> None:
    data = ok(client, "qb_trial_balance", as_of="2025-03-31")
    assert data["fiscal_start"] == "2025-01-01"
    assert data["debit"] == data["credit"]
    rows = {r["account"]: r for r in data["rows"]}
    assert rows["Equity:Retained-Earnings (computed)"]["credit"] == "300.00"
    january = ok(client, "qb_trial_balance", as_of="2025-01-31")
    assert "Expenses:Software" not in {r["account"] for r in january["rows"]}
    assert rows["Income:Sales"]["credit"] == "500.00"
    assert rows["Expenses:Software"]["debit"] == "20.00"


def test_fiscal_year(tmp_path: Path) -> None:
    ledger = tmp_path / "reports.beancount"
    ledger.write_text(
        LEDGER
        + '\n2024-01-01 custom "fava-option" "fiscal-year-end" "06-30"\n'
    )
    app = create_app([ledger], load=True)
    app.testing = True
    client = app.test_client()
    early = ok(client, "qb_trial_balance", as_of="2025-03-31")
    assert early["fiscal_start"] == "2024-07-01"
    late = ok(client, "qb_trial_balance", as_of="2025-08-01")
    assert late["fiscal_start"] == "2025-07-01"


def test_general_ledger(client: FlaskClient) -> None:
    data = ok(
        client, "qb_general_ledger", start="2025-03-01", end="2025-03-31"
    )
    accounts = {a["account"]: a for a in data["accounts"]}
    checking = accounts["Assets:Bank:Checking"]
    assert Decimal(checking["opening"]) == Decimal(1700)
    assert [r["amount"] for r in checking["rows"]] == [
        "-700.00",
        "-13.00",
        "-100.00",
    ]
    assert Decimal(checking["closing"]) == Decimal(887)
    assert accounts["Assets:Broker"]["rows"][0]["amount"] == "100.00"
    assert checking["rows"][0]["split"] == ["Expenses:Uncategorized"]
    # Income: the fiscal year so far; last year's sale isn't in the opening.
    assert Decimal(accounts["Income:Sales"]["opening"]) == Decimal(-500)
    assert accounts["Income:Sales"]["rows"] == []
    only = ok(
        client,
        "qb_general_ledger",
        start="2025-01-01",
        end="2025-12-31",
        account="Expenses",
    )
    assert {a["account"].split(":")[0] for a in only["accounts"]} == {
        "Expenses"
    }


def test_empty_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "reports.beancount"
    ledger.write_text('option "title" "Empty"\n')
    app = create_app([ledger], load=True)
    app.testing = True
    client = app.test_client()
    data = ok(client, "qb_profit_loss")
    assert data["currency"] == "USD"
    assert numbers(blocks(data)["net"]["amounts"]) == [0]
    assert blocks(ok(client, "qb_balance_sheet"))["assets"]["node"] is None


def test_year_checks(client: FlaskClient, tmp_path: Path) -> None:
    checks = {c["key"]: c for c in ok(client, "qb_year_checks", year=2025)}
    assert not checks["review"]["ok"]
    assert checks["review"]["params"] == {"period": "2025", "kind": "review"}
    assert "Expenses:Uncategorized" in checks["uncategorized"]["detail"]
    assert checks["uncategorized"]["params"] == {
        "account_name": "Expenses:Uncategorized"
    }
    assert not checks["reconciled"]["ok"]
    assert "5 expenses without a receipt" in checks["receipts"]["detail"]
    assert checks["errors"]["ok"] is False  # lunch.pdf doesn't exist
    assert "Designer" in checks["contractors"]["detail"]

    clean = {c["key"]: c for c in ok(client, "qb_year_checks", year=2023)}
    assert all(
        clean[key]["ok"]
        for key in ("review", "uncategorized", "reconciled", "receipts")
    )
    assert clean["contractors"]["ok"]

    # Reconciled through year end: the account passes.
    ledger = tmp_path / "reconciled.beancount"
    ledger.write_text(
        LEDGER
        + "\n".join(
            f'2025-12-31 note {a} "Reconciled: statement ending 2025-12-31"'
            for a in (
                "Assets:Bank:Checking",
                "Liabilities:CreditCard:Visa",
                "Assets:Cash:XYZ",
                "Assets:Broker",
            )
        )
    )
    app = create_app([ledger], load=True)
    app.testing = True
    again = {
        c["key"]: c for c in ok(app.test_client(), "qb_year_checks", year=2025)
    }
    assert again["reconciled"]["ok"]


def test_balance_trend(client: FlaskClient) -> None:
    points = ok(client, "qb_balance_trend", as_of="2025-03-15", months=3)
    assert [p["date"] for p in points] == [
        "2025-01-31",
        "2025-02-28",
        "2025-03-15",
    ]
    last = points[-1]
    assert Decimal(last["assets"]) == Decimal("987.00")
    assert Decimal(last["liabilities"]) == Decimal(75)
    assert Decimal(last["equity"]) == Decimal("912.00")
    assert Decimal(points[0]["liabilities"]) == 0
    one = ok(client, "qb_balance_trend", as_of="2024-01-01", months=0)
    assert [p["date"] for p in one] == ["2024-01-01"]
