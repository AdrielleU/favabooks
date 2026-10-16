from __future__ import annotations

import shutil
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient

QB_EXAMPLE = Path(__file__).parent / "qb_data" / "qb-example.beancount"

#: A receipt filed as a Document, one that is missing, a tagged card charge,
#: a transaction without amounts, and an empty transaction.
EXTRA = """
2026-01-01 open Liabilities:Card

2026-03-12 document Expenses:Uncategorized "receipts/saas.pdf"

2026-03-20 * "Shop" "Paper" #office
  document: "receipts/paper.pdf"
  Liabilities:Card       -4.00 USD
  Liabilities:Card       -5.00 USD
  Expenses:Software
    document: "receipts/saas.pdf"

2026-03-21 * "Nothing" "No postings"
"""


def make_client(tmp_path: Path) -> FlaskClient:
    ledger = tmp_path / "qb-example.beancount"
    shutil.copy(QB_EXAMPLE, ledger)
    (tmp_path / "receipts").mkdir()
    (tmp_path / "receipts" / "saas.pdf").write_bytes(b"%PDF")
    ledger.write_text(ledger.read_text() + EXTRA)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client()


def get(client: FlaskClient, endpoint: str, **kw: str) -> Any:  # noqa: ANN401
    response = client.get(f"/qb-example/api/{endpoint}", query_string=kw)
    assert response.status_code == HTTPStatus.OK.value
    return response.get_json()["data"]


def test_transactions(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    data = get(client, "qb_transactions")
    assert data["counts"] == {
        "all": 12,
        "expense": 6,
        "income": 2,
        "transfer": 2,
        "other": 2,
        "review": 2,
    }
    rows = {(r["date"], r["payee"] or r["narration"]): r for r in data["rows"]}
    assert data["rows"][0]["date"] == "2026-04-02"  # newest first

    retainer = rows["2026-02-05", "Acme"]
    assert (retainer["kind"], Decimal(retainer["amount"])) == (
        "income",
        Decimal("1000.00"),
    )
    hotel = rows["2026-03-10", "Hotel Berlin"]
    assert (hotel["kind"], hotel["amount"], hotel["currency"]) == (
        "expense",
        "200.00",
        "EUR",
    )
    payout = rows["2026-03-01", "Stripe"]
    assert (payout["kind"], payout["categories"], payout["amount"]) == (
        "transfer",
        [],
        "970.00",
    )
    opening = rows["2026-01-02", "Opening balance"]
    assert (opening["kind"], opening["categories"]) == (
        "other",
        ["Equity:Opening-Balances"],
    )
    assert rows["2026-03-21", "Nothing"]["currency"] == ""

    shop = rows["2026-03-20", "Shop"]
    assert shop["tags"] == ["office"]
    assert shop["paid_with"] == ["Liabilities:Card"]
    receipts = {r["name"]: r["filename"] for r in shop["receipts"]}
    assert receipts["paper.pdf"] == ""
    assert receipts["saas.pdf"].endswith("receipts/saas.pdf")


def test_transactions_filters(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    review = get(client, "qb_transactions", kind="review")
    assert [r["flag"] for r in review["rows"]] == ["!", "!"]
    assert review["total"] == 2
    assert review["counts"]["all"] == 12
    income = get(client, "qb_transactions", kind="income")
    assert {r["kind"] for r in income["rows"]} == {"income"}
    cafe = get(client, "qb_transactions", search="CAFE")
    assert cafe["counts"]["all"] == 2
    by_amount = get(client, "qb_transactions", search="220.00")
    assert by_amount["rows"] == []  # the expense is 200.00 EUR
    by_tag = get(client, "qb_transactions", search="office")
    assert [r["payee"] for r in by_tag["rows"]] == ["Shop"]
    dated = get(client, "qb_transactions", time="2026-03")
    assert dated["counts"]["all"] == 7


def test_categories(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    data = get(client, "qb_categories")
    accounts = [c["account"] for c in data]
    # Expenses first by most transactions, then income.
    assert accounts[:2] == ["Expenses:Fees:Stripe", "Expenses:Meals"]
    assert accounts[-1] == "Income:Services"
    income = data[-1]
    assert (income["count"], Decimal(income["total"])) == (
        2,
        Decimal("2500.00"),
    )
    travel = next(c for c in data if c["account"] == "Expenses:Travel")
    assert (travel["currency"], travel["total"]) == ("EUR", "200.00")
    # The time filter's opening-balance entries are not categories' activity.
    march = get(client, "qb_categories", time="2026-03")
    assert "Equity:Opening-Balances" not in [c["account"] for c in march]
    assert (
        next(c for c in march if c["account"] == "Income:Services")["count"]
        == 1
    )
