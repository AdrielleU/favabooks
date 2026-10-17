from __future__ import annotations

import datetime
from http import HTTPStatus
from typing import Any
from typing import TYPE_CHECKING

import pytest

from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from flask.testing import FlaskClient

LEDGER = """
option "title" "Chart"
option "operating_currency" "USD"

2024-01-01 open Assets:Bank:Checking USD
2024-01-01 open Assets:Bank:Old
2024-01-01 open Liabilities:CreditCard:Visa
2024-01-01 open Income:Services
2024-01-01 open Expenses:Software
2024-01-01 open Expenses:Old
2024-06-30 close Expenses:Old

2024-03-01 * "Client" "Last year"
  Assets:Bank:Checking    300.00 USD
  Income:Services

2025-02-01 * "Client" "This year"
  Assets:Bank:Checking    500.00 USD
  Income:Services

2025-02-10 * "SaaS" "Subscription"
  Expenses:Software        20.00 USD
  Liabilities:CreditCard:Visa

2025-03-01 * "Kiosk" "No price for XYZ"
  Expenses:Software        10.00 XYZ
  Liabilities:CreditCard:Visa

2025-12-01 * "Later" "After today"
  Expenses:Software         5.00 USD
  Liabilities:CreditCard:Visa
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    monkeypatch.setattr(
        "fava.qb_chart.local_today", lambda: datetime.date(2025, 6, 30)
    )
    ledger = tmp_path / "chart.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def call(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, Any]:
    if method == "get":
        response = client.get(f"/chart/api/{endpoint}", query_string=kw)
    else:
        response = client.put(f"/chart/api/{endpoint}", json=kw)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def chart(client: FlaskClient) -> dict[str, dict[str, Any]]:
    status, data = call(client, "get", "qb_chart")
    assert status == HTTPStatus.OK.value, data
    assert data["year_start"] == "2025-01-01"
    assert data["roots"]["assets"] == "Assets"
    return {a["account"]: a for a in data["accounts"]}


def test_chart(client: FlaskClient) -> None:
    accounts = chart(client)
    checking = accounts["Assets:Bank:Checking"]
    assert (checking["type"], checking["detail_type"]) == ("Bank", "Checking")
    assert checking["balance"] == "800.00"
    assert checking["transactions"] == 2
    assert checking["open_date"] == "2024-01-01"
    assert checking["last_date"] == "2025-02-01"
    # Income and expenses: this year so far (not last year, not the future).
    assert accounts["Income:Services"]["balance"] == "-500.00"
    # The XYZ charge has no price, so it isn't in the balance.
    assert accounts["Expenses:Software"]["balance"] == "20.00"
    assert accounts["Expenses:Software"]["transactions"] == 3
    assert accounts["Expenses:Old"]["close_date"] == "2024-06-30"
    assert accounts["Assets:Bank:Old"]["transactions"] == 0


def test_open(client: FlaskClient, tmp_path: Path) -> None:
    def bad(**kw: str) -> str:
        body = {"account": "Assets:Bank:Savings", "date": "2025-01-01", **kw}
        status, data = call(client, "put", "qb_account_open", **body)
        assert status == HTTPStatus.BAD_REQUEST.value, data
        return str(data["detail"])

    assert "isn't a valid account name" in bad(account="Assets:bank savings")
    assert "isn't a valid account name" in bad(account="Stuff:Thing")
    assert "already exists" in bad(account="Assets:Bank:Checking")
    assert "2026-01-31" in bad(date="soon")
    status, data = call(
        client,
        "put",
        "qb_account_open",
        account=" Assets:Bank:Savings ",
        date="2025-01-01",
        currency="usd",
    )
    assert status == HTTPStatus.OK.value, data
    text = " ".join((tmp_path / "chart.beancount").read_text().split())
    assert "2025-01-01 open Assets:Bank:Savings USD" in text
    assert "Assets:Bank:Savings" in chart(client)


def test_close(client: FlaskClient, tmp_path: Path) -> None:
    def bad(account: str, date: str = "2025-06-30") -> str:
        status, data = call(
            client, "put", "qb_account_close", account=account, date=date
        )
        assert status == HTTPStatus.BAD_REQUEST.value, data
        return str(data["detail"])

    assert "unknown account" in bad("Assets:Nope")
    assert "already closed" in bad("Expenses:Old")
    assert "transactions after" in bad("Expenses:Software")
    assert "still has a balance of 800.00" in bad("Assets:Bank:Checking")
    assert "2026-01-31" in bad("Assets:Bank:Old", "June")
    status, data = call(
        client,
        "put",
        "qb_account_close",
        account="Assets:Bank:Old",
        date="2025-06-30",
    )
    assert status == HTTPStatus.OK.value, data
    status, data = call(
        client,
        "put",
        "qb_account_close",
        account="Income:Services",
        date="2025-06-30",
    )
    assert status == HTTPStatus.OK.value, data
    text = (tmp_path / "chart.beancount").read_text()
    assert "2025-06-30 close Assets:Bank:Old" in text
    assert chart(client)["Assets:Bank:Old"]["close_date"] == "2025-06-30"


def test_new_accounts_go_with_the_others(tmp_path: Path) -> None:
    (tmp_path / "accounts.beancount").write_text(
        "2024-01-01 open Assets:Bank:Checking USD\n"
    )
    main = tmp_path / "main.beancount"
    main.write_text(
        'option "title" "Split"\ninclude "accounts.beancount"\n'
        '2024-01-02 * "x"\n  Assets:Bank:Checking 1.00 USD\n'
        "  Assets:Bank:Checking -1.00 USD\n"
    )
    app = create_app([main], load=True)
    app.testing = True
    response = app.test_client().put(
        "/split/api/qb_account_open",
        json={"account": "Assets:Bank:Savings", "date": "2024-01-01"},
    )
    assert response.status_code == HTTPStatus.OK.value, response.get_json()
    assert (
        "Assets:Bank:Savings" in (tmp_path / "accounts.beancount").read_text()
    )
    assert "Assets:Bank:Savings" not in main.read_text()


def test_first_account(tmp_path: Path) -> None:
    main = tmp_path / "main.beancount"
    main.write_text('option "title" "Empty"\n')
    app = create_app([main], load=True)
    app.testing = True
    response = app.test_client().put(
        "/empty/api/qb_account_open",
        json={"account": "Assets:Cash", "date": "2024-01-01"},
    )
    assert response.status_code == HTTPStatus.OK.value, response.get_json()
    assert "open Assets:Cash" in main.read_text()


def test_nicknames(client: FlaskClient, tmp_path: Path) -> None:
    def nick(account: str, nickname: str) -> tuple[int, Any]:
        return call(
            client,
            "put",
            "qb_account_nickname",
            account=account,
            nickname=nickname,
        )

    status, data = nick("Liabilities:CreditCard:Visa", "  Chase   Ink  ")
    assert status == HTTPStatus.OK.value, data
    assert data == "Liabilities:CreditCard:Visa is now called Chase Ink."
    assert (
        chart(client)["Liabilities:CreditCard:Visa"]["nickname"] == "Chase Ink"
    )
    # Replacing keeps one nickname line; quotes are escaped.
    nick("Liabilities:CreditCard:Visa", 'Amex "Gold"')
    text = (tmp_path / "chart.beancount").read_text()
    assert text.count("nickname:") == 1
    assert 'nickname: "Amex \\"Gold\\""' in text
    status, data = call(client, "get", "qb_nicknames")
    assert data == {"Liabilities:CreditCard:Visa": 'Amex "Gold"'}
    status, data = nick("Liabilities:CreditCard:Visa", "")
    assert data == "Removed the nickname of Liabilities:CreditCard:Visa."
    assert "nickname" not in (tmp_path / "chart.beancount").read_text()
    assert call(client, "get", "qb_nicknames")[1] == {}

    status, data = nick("Assets:Nope", "x")
    assert status == HTTPStatus.BAD_REQUEST.value
    assert "unknown account" in data["detail"]
    status, data = nick("Assets:Bank:Checking", "x" * 61)
    assert "under 60" in data["detail"]
