from __future__ import annotations

from http import HTTPStatus
from typing import Any
from typing import TYPE_CHECKING

import pytest

from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from flask.testing import FlaskClient

LEDGER = """
option "title" "Prices"
option "operating_currency" "USD"

2024-01-01 open Assets:Bank:Checking
2024-01-01 open Assets:Bank:Euro
2024-01-01 open Assets:Broker
2024-01-01 open Expenses:Travel

2024-01-01 commodity EUR
  name: "Euro"
2024-01-01 commodity GBP

2025-03-01 price EUR 1.08 USD
2025-06-01 price EUR 1.10 USD
2025-06-01 price AAPL 200.00 USD
2025-06-02 price USD 0.80 GBP

2025-03-05 * "Hotel" "Paris"
  Expenses:Travel           50.00 EUR
  Assets:Bank:Euro

2025-04-01 * "Kiosk" "Tokyo"
  Expenses:Travel         1000 JPY
  Assets:Bank:Checking   -7.00 USD @@ 1000 JPY
"""


@pytest.fixture
def client(tmp_path: Path) -> FlaskClient:
    ledger = tmp_path / "prices.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def call(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, Any]:
    url = f"/prices/api/{endpoint}"
    if method == "get":
        response = client.get(url, query_string=kw)
    elif method == "delete":
        response = client.delete(url, query_string=kw)
    else:
        response = client.put(url, json=kw)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def prices(client: FlaskClient) -> Any:  # noqa: ANN401
    status, data = call(client, "get", "qb_prices")
    assert status == HTTPStatus.OK.value, data
    return data


def test_currencies(client: FlaskClient) -> None:
    data = prices(client)
    assert data["home"] == "USD"
    by = {c["currency"]: c for c in data["currencies"]}
    # JPY is used with no price: listed first, flagged.
    assert data["currencies"][0]["currency"] == "JPY"
    assert by["JPY"]["needs_price"] is True
    euro = by["EUR"]
    assert (euro["name"], euro["postings"], euro["needs_price"]) == (
        "Euro",
        2,
        False,
    )
    assert euro["latest"]["price"] == "1.10"
    assert euro["previous"]["price"] == "1.08"
    assert euro["last_used"] == "2025-03-05"
    assert by["AAPL"]["postings"] == 0
    # GBP: priced against USD the other way round, and named.
    assert by["GBP"]["latest"] is None
    assert by["GBP"]["needs_price"] is False
    assert [p["date"] for p in data["prices"]][:2] == [
        "2025-06-02",
        "2025-06-01",
    ]


def test_add_and_delete(client: FlaskClient, tmp_path: Path) -> None:
    def bad(**kw: str) -> str:
        body = {
            "date": "2025-07-01",
            "currency": "jpy",
            "price": "0.0068",
            **kw,
        }
        status, data = call(client, "put", "qb_price", **body)
        assert status == HTTPStatus.BAD_REQUEST.value, data
        return str(data["detail"])

    assert "2026-01-31" in bad(date="July")
    assert "like EUR" in bad(currency=" ")
    assert "like EUR" in bad(currency="J P Y")
    assert "another currency" in bad(currency="usd")
    assert "positive" in bad(price="free")
    assert "positive" in bad(price="-1")
    status, data = call(
        client,
        "put",
        "qb_price",
        date="2025-07-01",
        currency=" jpy ",
        price="0.0068",
    )
    assert status == HTTPStatus.OK.value, data
    assert (
        "2025-07-01 price JPY" in (tmp_path / "prices.beancount").read_text()
    )
    by = {c["currency"]: c for c in prices(client)["currencies"]}
    assert by["JPY"]["needs_price"] is False
    added = by["JPY"]["latest"]["entry_hash"]

    status, data = call(client, "delete", "qb_price", entry_hash=added)
    assert status == HTTPStatus.OK.value, data
    assert "price JPY" not in (tmp_path / "prices.beancount").read_text()
    status, data = call(client, "delete", "qb_price", entry_hash=added)
    assert status == HTTPStatus.BAD_REQUEST.value
    assert "isn't in the books" in data["detail"]


def test_no_operating_currency(tmp_path: Path) -> None:
    ledger = tmp_path / "plain.beancount"
    ledger.write_text('option "title" "Plain"\n')
    app = create_app([ledger], load=True)
    app.testing = True
    response = app.test_client().get("/plain/api/qb_prices")
    assert response.get_json()["data"]["home"] == "USD"
