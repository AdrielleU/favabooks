from __future__ import annotations

import shutil
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import Any
from typing import cast
from typing import TYPE_CHECKING

from beancount import loader

from fava.application import create_app
from fava.qb_reconcile import reconciled_key

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient

QB_EXAMPLE = Path(__file__).parent / "qb_data" / "qb-example.beancount"

#: Extra entries: a euro posting (other currency), a deposit split over two
#: postings, and an account without transactions.
EXTRA = """
2026-01-01 open Assets:Bank:Empty
2026-01-01 open Liabilities:Card

2026-01-15 * "FX" "Euro deposit"
  Assets:Bank:Checking   5.00 EUR
  Equity:Opening-Balances

2026-01-20 * "Split" "Two deposits in one"
  Assets:Bank:Checking   3.00 USD
  Assets:Bank:Checking   2.00 USD
  Equity:Opening-Balances

2026-02-01 * "Card" "Charge"
  Liabilities:Card  -9.00 USD
  Expenses:Meals
"""


def make_client(tmp_path: Path) -> tuple[FlaskClient, Path]:
    ledger = tmp_path / "qb-example.beancount"
    shutil.copy(QB_EXAMPLE, ledger)
    ledger.write_text(ledger.read_text() + EXTRA)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client(), ledger


def api(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, Any]:
    if method == "get":
        response = client.get(f"/qb-example/api/{endpoint}", query_string=kw)
    else:
        response = client.put(f"/qb-example/api/{endpoint}", json=kw)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def test_reconciled_key() -> None:
    assert reconciled_key("Liabilities:CreditCard:Card-8360") == (
        "reconciled-liabilities-creditcard-card-8360"
    )


def test_accounts_overview(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    status, data = api(client, "get", "qb_accounts_overview")
    assert status == HTTPStatus.OK.value
    rows = {row["account"]: row for row in data}
    # Assets first, then liabilities; only accounts with transactions.
    assert list(rows)[-1] == "Liabilities:Card"
    assert "Assets:Bank:Empty" not in rows
    checking = rows["Assets:Bank:Checking"]
    assert (checking["currency"], Decimal(checking["balance"])) == (
        "USD",
        Decimal("1700.00"),
    )
    assert checking["transactions"] == 9  # the split deposit counts once
    assert checking["last_date"] == "2026-04-02"


def test_reconcile(tmp_path: Path) -> None:
    client, ledger = make_client(tmp_path)

    def state(end: str = "") -> dict[str, Any]:
        status, data = api(
            client,
            "get",
            "qb_reconcile",
            account_name="Assets:Bank:Checking",
            end_date=end,
        )
        assert status == HTTPStatus.OK.value, data
        return cast("dict[str, Any]", data)

    feb = state("2026-02-28")
    assert Decimal(feb["beginning_balance"]) == 0
    assert Decimal(feb["books_balance"]) == Decimal("1015.00")
    assert [(r["date"], r["amount"]) for r in feb["rows"]] == [
        ("2026-01-02", "1000.00"),
        ("2026-01-10", "50.00"),
        ("2026-01-20", "5.00"),  # both postings of the split deposit
        ("2026-02-20", "-40.00"),
    ]
    # No end date: every open dollar transaction (the euro one is left out).
    assert len(state()["rows"]) == 8

    # Statement: the first three cleared, the -40.00 not yet on it.
    hashes = [r["entry_hash"] for r in feb["rows"][:3]]
    status, result = api(
        client,
        "put",
        "qb_reconcile",
        account_name="Assets:Bank:Checking",
        end_date="2026-02-28",
        ending_balance="$1,055.00",
        entry_hashes=hashes,
    )
    assert status == HTTPStatus.OK.value, result
    assert result == {"reconciled": 3, "balance_assertion": False}
    text = ledger.read_text()
    key = reconciled_key("Assets:Bank:Checking")
    assert text.count(f'{key}: "2026-02-28"') == 3
    assert "Reconciled: statement ending 2026-02-28" in text
    assert "1 outstanding" in text
    assert "balance Assets:Bank:Checking" not in text

    again = state("2026-02-28")
    assert Decimal(again["beginning_balance"]) == Decimal("1055.00")
    assert [r["date"] for r in again["rows"]] == ["2026-02-20"]
    assert [h["date"] for h in again["history"]] == ["2026-02-28"]

    # Next statement clears everything: a balance assertion is added.
    march = state("2026-03-31")
    status, result = api(
        client,
        "put",
        "qb_reconcile",
        account_name="Assets:Bank:Checking",
        end_date="2026-03-31",
        ending_balance="1705.00",
        entry_hashes=[r["entry_hash"] for r in march["rows"]],
    )
    assert result == {"reconciled": 4, "balance_assertion": True}, result
    assert "2026-04-01 balance Assets:Bank:Checking" in ledger.read_text()
    _, errors, _ = loader.load_file(str(ledger))
    assert errors == []

    def bad(**kw: object) -> str:
        body = {
            "account_name": "Assets:Bank:Checking",
            "end_date": "2026-04-30",
            "ending_balance": "0",
            "entry_hashes": [],
            **kw,
        }
        status, data = api(client, "put", "qb_reconcile", **body)
        assert status == HTTPStatus.BAD_REQUEST.value
        return str(data["detail"])

    assert "difference is -1705.00 USD" in bad()
    assert "not open" in bad(entry_hashes=["nope"])
    assert "number" in bad(ending_balance="lots")
    assert "ending date" in bad(end_date="")
    assert "2026-01-31" in bad(end_date="April")
    assert "unknown account" in bad(account_name="Assets:Nope")


def test_reconcile_empty_account(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    status, data = api(
        client, "get", "qb_reconcile", account_name="Assets:Bank:Empty"
    )
    assert status == HTTPStatus.OK.value
    assert (data["currency"], data["rows"], data["history"]) == ("USD", [], [])
