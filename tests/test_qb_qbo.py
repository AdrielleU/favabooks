from __future__ import annotations

from decimal import Decimal
from http import HTTPStatus
from typing import Any
from typing import TYPE_CHECKING

import pytest

from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from flask.testing import FlaskClient

ACCOUNTS = """
Assets:Bank:Checking
Assets:Bank:Savings
Assets:Cash
Assets:AccountsReceivable
Assets:Equipment
Assets:Prepaid
Liabilities:AccountsPayable
Liabilities:CreditCard:Visa
Liabilities:Tax:Sales
Liabilities:Loan:Bank
Liabilities:Other
Equity:Opening-Balances
Equity:Retained-Earnings
Equity:Owner:Draws
Equity:Owner:Capital
Income:Services
Income:Interest
Income:Products
Expenses:COGS:Materials
Expenses:Uncategorized
Expenses:Advertising
Expenses:Software
Expenses:Legal
Expenses:Meals
Expenses:Travel
Expenses:Telephone
Expenses:Utilities
Expenses:Rent
Expenses:Insurance
Expenses:Fees:Stripe
Expenses:Taxes
Expenses:Interest
Expenses:Shipping
Expenses:Repairs:Maintenance
Expenses:Supplies
Expenses:Auto
Expenses:Charity
Expenses:Equipment
Expenses:Misc
"""

LEDGER = (
    'option "title" "QBO"\noption "operating_currency" "USD"\n'
    + "".join(f"2024-01-01 open {a}\n" for a in ACCOUNTS.split() if a)
    + """
2024-01-01 open Assets:Foreign

2024-06-01 * "Client" "Last year's sale"
  Assets:Bank:Checking    300.00 USD
  Income:Services

2025-01-02 * "Owner" "Capital"
  Assets:Bank:Checking   1000.00 USD
  Equity:Owner:Capital

2025-02-01 * "Acme" "Invoice 7"
  customer: "Acme Inc"
  customer_email: "ap@acme.test"
  Assets:AccountsReceivable  500.00 USD
  Income:Services

2025-02-10 * "Paper Co" "Bill 3"
  vendor: "Paper Co"
  Expenses:Supplies        40.00 USD
  Liabilities:AccountsPayable

2025-02-11 * "Prepaid usage" "Nothing charged"
  Expenses:Telephone        0.00 USD
  Liabilities:CreditCard:Visa  0.00 USD

2025-03-01 * "Laptop" "Equipment"
  Assets:Equipment       1200.00 USD
  Expenses:Equipment        1.00 USD
  Liabilities:CreditCard:Visa

2025-03-02 * "Kiosk" "Foreign currency, no price"
  Expenses:Misc            10.00 XYZ
  Assets:Foreign          -10.00 XYZ

2026-01-05 * "Next year" "Not in 2025"
  Expenses:Software        10.00 USD
  Liabilities:CreditCard:Visa
"""
)


@pytest.fixture
def client(tmp_path: Path) -> FlaskClient:
    ledger = tmp_path / "qbo.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def get(client: FlaskClient, **kw: object) -> Any:  # noqa: ANN401
    response = client.get("/qbo/api/qb_qbo_export", query_string=kw)
    assert response.status_code == HTTPStatus.OK.value, response.get_json()
    return response.get_json()["data"]


def test_account_types(client: FlaskClient) -> None:
    from fava.context import g  # noqa: PLC0415
    from fava.qb_qbo import qbo_type  # noqa: PLC0415

    client.get("/qbo/api/qb_qbo_export", query_string={"year": 2025})
    app = client.application
    with app.test_request_context("/qbo/"):
        app.preprocess_request()
        types = {a: qbo_type(a) for a in ACCOUNTS.split() if a}
        assert g.ledger.options["name_assets"] == "Assets"
    assert types["Assets:Bank:Checking"] == ("Bank", "Checking")
    assert types["Assets:Bank:Savings"] == ("Bank", "Savings")
    assert types["Assets:Cash"] == ("Bank", "Cash on hand")
    assert types["Assets:AccountsReceivable"][0] == "Accounts receivable (A/R)"
    assert types["Assets:Equipment"] == (
        "Fixed Assets",
        "Machinery & Equipment",
    )
    assert types["Assets:Prepaid"][0] == "Other Current Assets"
    assert types["Liabilities:AccountsPayable"][0] == "Accounts payable (A/P)"
    assert types["Liabilities:CreditCard:Visa"] == (
        "Credit Card",
        "Credit Card",
    )
    assert types["Liabilities:Tax:Sales"][1] == "Sales Tax Payable"
    assert types["Liabilities:Loan:Bank"][0] == "Long Term Liabilities"
    assert types["Liabilities:Other"][0] == "Other Current Liabilities"
    assert types["Equity:Opening-Balances"][1] == "Opening Balance Equity"
    assert types["Equity:Retained-Earnings"][1] == "Retained Earnings"
    assert types["Equity:Owner:Draws"][1] == "Owner's Equity"
    assert types["Equity:Owner:Capital"][1] == "Owner's Equity"
    assert types["Income:Services"] == ("Income", "Service/Fee Income")
    assert types["Income:Interest"] == ("Other Income", "Interest Earned")
    assert types["Income:Products"][1] == "Sales of Product Income"
    assert types["Expenses:COGS:Materials"][0] == "Cost of Goods Sold"
    assert (
        types["Expenses:Uncategorized"][1]
        == "Other Miscellaneous Service Cost"
    )
    details = {a: t[1] for a, t in types.items() if a.startswith("Expenses:")}
    assert details["Expenses:Software"] == "Dues & subscriptions"
    assert details["Expenses:Legal"] == "Legal & Professional Fees"
    assert details["Expenses:Meals"] == "Travel Meals"
    assert details["Expenses:Telephone"] == "Communication"
    assert details["Expenses:Fees:Stripe"] == "Bank Charges"
    assert details["Expenses:Equipment"] == (
        "Office/General Administrative Expenses"
    )
    assert details["Expenses:Misc"] == "Other Business Expenses"


def test_transactions(client: FlaskClient) -> None:
    data = get(client, year=2025)
    assert data["currency"] == "USD"
    lines = data["lines"]
    journals: dict[str, list[dict[str, Any]]] = {}
    for line in lines:
        journals.setdefault(line["journal_no"], []).append(line)
    # Each journal balances.
    for journal in journals.values():
        assert (
            sum(Decimal(x["debit"]) - Decimal(x["credit"]) for x in journal)
            == 0
        )
    opening = journals["FB2025-0001"]
    assert opening[0]["description"] == "Opening balances carried in to 2025"
    assert {(x["account"], x["debit"], x["credit"]) for x in opening} == {
        ("Bank - Checking", "300.00", "0"),
        ("Retained Earnings", "0", "300.00"),
    }
    # The $0 entry and the unconvertible one are left out; 2026 isn't in.
    assert data["journals"] == 5
    assert len(data["skipped"]) == 1
    assert "Kiosk" in data["skipped"][0]
    ar = next(x for x in lines if x["account"] == "AccountsReceivable")
    assert ar["name"] == "Acme Inc"
    assert data["customers"] == [{"name": "Acme Inc", "email": "ap@acme.test"}]
    assert data["vendors"] == [{"name": "Paper Co", "email": ""}]
    names = {a["name"] for a in data["accounts"]}
    # Assets:Equipment and Expenses:Equipment would clash.
    assert {"Equipment (Assets)", "Equipment (Expenses)"} <= names
    assert "Retained Earnings" not in names
    assert lines[1]["date"] == "2025-01-01"


def test_balances(client: FlaskClient) -> None:
    data = get(client, year=2025, mode="balances")
    assert data["journals"] == 1
    totals = {x["account"]: (x["debit"], x["credit"]) for x in data["lines"]}
    assert totals["Bank - Checking"] == ("1300.00", "0")
    assert totals["Retained Earnings"] == ("0", "759.00")
    assert data["lines"][0]["date"] == "2025-12-31"
    response = client.get(
        "/qbo/api/qb_qbo_export", query_string={"year": 2025, "mode": "x"}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST.value


def test_first_and_last_years(client: FlaskClient) -> None:
    first = get(client, year=2024)
    assert first["journals"] == 1  # nothing carried in yet
    assert first["lines"][0]["journal_no"] == "FB2024-0001"
    last = get(client, year=2026)
    assert last["lines"][0]["description"].startswith("Opening balances")
