from __future__ import annotations

import datetime
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
option "title" "Close"
option "operating_currency" "USD"

2025-01-01 open Assets:Bank:Checking
2025-01-01 open Assets:Bank:Old
2025-06-30 close Assets:Bank:Old
2025-01-01 open Liabilities:Card
2025-01-01 open Income:Services
2025-01-01 open Expenses:Software
2025-01-01 open Expenses:Office

2025-02-01 balance Assets:Bank:Checking   0.00 USD

2025-03-01 * "Client" "Sale"
  Assets:Bank:Checking   500.00 USD
  Income:Services

2025-04-01 * "SaaS" "Subscription"
  Expenses:Software       20.00 USD
  Liabilities:Card

2025-05-01 * "Move" "Old account emptied"
  Assets:Bank:Old          0.00 USD
  Assets:Bank:Checking     0.00 USD

2026-02-01 * "SaaS" "Next year"
  Expenses:Software       20.00 USD
  Liabilities:Card
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    today = lambda: datetime.date(2026, 3, 15)  # noqa: E731
    monkeypatch.setattr("fava.qb_close.local_today", today)
    ledger = tmp_path / "close.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def call(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, Any]:
    url = f"/close/api/{endpoint}"
    if method == "get":
        response = client.get(url, query_string=kw)
    elif method == "delete":
        response = client.delete(url, query_string=kw)
    else:
        response = client.put(url, json=kw)
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


def test_close_and_reopen(client: FlaskClient, tmp_path: Path) -> None:
    state = ok(client, "get", "qb_close")
    assert state["closed_through"] is None
    assert state["suggested"] == "2025-12-31"
    assert "past" in error(client, "put", "qb_close", date="2026-03-15")
    assert "2025-12-31" in error(client, "put", "qb_close", date="Dec")
    assert "aren't closed" in error(client, "delete", "qb_close")

    message = ok(
        client, "put", "qb_close", date="2025-12-31", note=" Tax  year "
    )
    assert "with 4 balance checks" in message  # Old is closed by then
    text = (tmp_path / "close.beancount").read_text()
    assert 'custom "closed-books" "Tax year"' in text
    assert "2026-01-01 balance Assets:Bank:Checking" in text
    assert "Assets:Bank:Old" not in text.split("closed-books")[-1]
    state = ok(client, "get", "qb_close")
    assert state["closed_through"] == "2025-12-31"
    assert state["history"][0]["checks"] == 4
    assert state["history"][0]["note"] == "Tax year"
    assert state["suggested"] == "2026-02-28"
    assert "already closed through" in error(
        client, "put", "qb_close", date="2025-06-30"
    )
    _, errors, _ = loader.load_file(str(tmp_path / "close.beancount"))
    assert errors == []

    # Tampering with a closed period breaks a balance check.
    tampered = tmp_path / "tampered.beancount"
    tampered.write_text(
        text.replace(
            "20.00 USD\n  Liabilities:Card", "25.00 USD\n  Liabilities:Card", 1
        )
    )
    _, errors, _ = loader.load_file(str(tampered))
    assert any("Balance failed" in e.message for e in errors)

    # A second close, then reopening goes back one step.
    ok(client, "put", "qb_close", date="2026-02-28")
    message = ok(client, "delete", "qb_close")
    assert "still closed through 2025-12-31" in message
    message = ok(client, "delete", "qb_close")
    assert message == "Reopened the books after 2025-12-31."
    text = (tmp_path / "close.beancount").read_text()
    assert "closed-books" not in text
    assert text.count(" balance ") == 1  # only the ledger's own check


def test_closed_period_is_locked(client: FlaskClient) -> None:
    ok(client, "put", "qb_close", date="2025-12-31")
    closed = "the books are closed through 2025-12-31"

    txns = ok(client, "get", "qb_transactions")["rows"]
    saas = next(r for r in txns if r["date"] == "2025-04-01")
    result = ok(
        client,
        "put",
        "qb_reclassify",
        entry_hashes=[saas["entry_hash"]],
        from_account="Expenses:Software",
        to_account="Expenses:Office",
    )
    assert result["changed"] == 0
    assert closed in result["failed"][0]["error"]

    assert closed in error(
        client,
        "put",
        "qb_bill",
        doc={
            "party": "Paper",
            "number": "1",
            "date": "2025-12-01",
            "amount": "5",
            "account": "Expenses:Office",
        },
    )
    assert closed in error(
        client,
        "put",
        "qb_price",
        date="2025-06-01",
        currency="EUR",
        price="1.1",
    )
    data = ok(
        client,
        "get",
        "qb_reconcile",
        account_name="Liabilities:Card",
        end_date="2025-12-31",
    )
    assert closed in error(
        client,
        "put",
        "qb_reconcile",
        account_name="Liabilities:Card",
        end_date="2025-12-31",
        ending_balance="20.00",
        entry_hashes=[data["rows"][0]["entry_hash"]],
    )
    # After the closing date everything still works.
    ok(
        client,
        "put",
        "qb_price",
        date="2026-01-15",
        currency="EUR",
        price="1.1",
    )
    prices = ok(client, "get", "qb_prices")["prices"]
    assert closed in error(
        client,
        "put",
        "qb_price",
        date="2025-01-15",
        currency="EUR",
        price="1.2",
    )
    ok(client, "delete", "qb_price", entry_hash=prices[0]["entry_hash"])
