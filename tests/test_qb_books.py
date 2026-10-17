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
option "title" "Books"
option "operating_currency" "USD"

2025-01-01 open Assets:Bank:Checking
2025-01-01 open Assets:Bank:Idle
2025-01-01 open Liabilities:Card
2025-01-01 open Expenses:Software
2025-01-01 open Assets:Old
2025-02-01 close Assets:Old

2025-01-01 event "address" "1 Main St, Phoenix, AZ"
2025-05-01 event "address" "9 Oak Ave, Tempe, AZ"
2025-03-01 event "tax-status" "Single-member LLC"
2025-12-31 event "business-license" "Renew city license"

2025-01-10 * "SaaS" "January"
  Expenses:Software   10.00 USD
  Liabilities:Card

2025-02-10 ! "SaaS" "February"
  Expenses:Software   10.00 USD
  Liabilities:Card

2025-02-20 * "Owner" "Deposit"
  Assets:Bank:Checking   100.00 USD
  Liabilities:Card
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    today = lambda: datetime.date(2025, 6, 1)  # noqa: E731
    monkeypatch.setattr("fava.qb_books.local_today", today)
    ledger = tmp_path / "books.beancount"
    ledger.write_text(LEDGER)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def call(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, Any]:
    url = f"/books/api/{endpoint}"
    if method == "get":
        response = client.get(url, query_string=kw)
    elif method == "delete":
        response = client.delete(url, query_string=kw)
    else:
        response = client.put(url, json=kw)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def test_events(client: FlaskClient, tmp_path: Path) -> None:
    status, data = call(client, "get", "qb_events")
    assert status == HTTPStatus.OK.value
    types = {t["type"]: t for t in data["types"]}
    assert types["address"]["current"]["description"] == "9 Oak Ave, Tempe, AZ"
    assert types["address"]["count"] == 2
    assert types["business-license"]["current"] is None
    assert types["business-license"]["upcoming"]["date"] == "2025-12-31"
    assert types["address"]["upcoming"] is None
    assert data["events"][0]["type"] == "business-license"
    assert "address" not in data["suggestions"]
    assert "registered-agent" in data["suggestions"]

    def bad(**kw: str) -> str:
        body = {"date": "2025-06-01", "type": "bank", "description": "x", **kw}
        status, data = call(client, "put", "qb_event", **body)
        assert status == HTTPStatus.BAD_REQUEST.value, data
        return str(data["detail"])

    assert "2026-01-31" in bad(date="June")
    assert "type and the description" in bad(type=" ")
    assert "type and the description" in bad(description="  ")
    status, data = call(
        client,
        "put",
        "qb_event",
        date="2025-06-01",
        type="Registered Agent",
        description="  ZenBusiness   Inc ",
    )
    assert status == HTTPStatus.OK.value, data
    text = (tmp_path / "books.beancount").read_text()
    assert 'event "registered-agent" "ZenBusiness Inc"' in text
    status, data = call(client, "get", "qb_events")
    added = next(e for e in data["events"] if e["type"] == "registered-agent")[
        "entry_hash"
    ]
    status, data = call(client, "delete", "qb_event", entry_hash=added)
    assert status == HTTPStatus.OK.value, data
    assert "registered-agent" not in (tmp_path / "books.beancount").read_text()
    status, data = call(client, "delete", "qb_event", entry_hash=added)
    assert "isn't in the books" in data["detail"]


def test_statistics(client: FlaskClient) -> None:
    status, data = call(client, "get", "qb_statistics")
    assert status == HTTPStatus.OK.value, data
    assert (data["transactions"], data["to_review"]) == (3, 1)
    assert (data["first_date"], data["last_date"]) == (
        "2025-01-10",
        "2025-02-20",
    )
    assert data["open_accounts"] == 4
    assert data["entries"]["Event"] == 4
    assert [
        (m["month"], m["transactions"], m["to_review"]) for m in data["months"]
    ] == [
        ("2025-01-01", 1, 0),
        ("2025-02-01", 2, 1),
    ]
    accounts = [(a["account"], a["days"]) for a in data["accounts"]]
    # Never used first, then the stalest.
    assert accounts == [
        ("Assets:Bank:Idle", None),
        ("Assets:Bank:Checking", 101),
        ("Liabilities:Card", 101),
    ]
    assert data["postings"][0] == ["Liabilities:Card", 3]


def test_statistics_empty(tmp_path: Path) -> None:
    ledger = tmp_path / "empty.beancount"
    ledger.write_text('option "title" "Empty"\n')
    app = create_app([ledger], load=True)
    app.testing = True
    data = app.test_client().get("/empty/api/qb_statistics").get_json()["data"]
    assert (data["first_date"], data["transactions"]) == (None, 0)
