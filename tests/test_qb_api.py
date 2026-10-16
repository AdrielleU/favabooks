from __future__ import annotations

import shutil
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from fava.application import create_app
from fava.core.file import get_entry_slice

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient

    from fava.beans.abc import Directive


#: Kept out of tests/data, whose file listing is snapshot-tested upstream.
QB_DATA_DIR = Path(__file__).parent / "qb_data"


@pytest.fixture(scope="module")
def qb_client() -> FlaskClient:
    app = create_app([QB_DATA_DIR / "qb-example.beancount"], load=True)
    app.testing = True
    return app.test_client()


def get_dashboard(client: FlaskClient, time: str = "") -> object:
    response = client.get(
        "/qb-example/api/qb_dashboard", query_string={"time": time}
    )
    assert response.status_code == HTTPStatus.OK.value
    data = response.get_json()["data"]
    assert isinstance(data, dict)
    return _decimals(data)


def _decimals(value: object) -> object:
    """Turn the amount strings in a response into Decimals for comparison."""
    if isinstance(value, dict):
        return {
            k: Decimal(v)
            if k in {"amount", "income", "expenses", "net"}
            else _decimals(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_decimals(v) for v in value]
    return value


def test_dashboard_month_from_time_filter(qb_client: FlaskClient) -> None:
    data = get_dashboard(qb_client, "2026-03")
    assert isinstance(data, dict)

    assert data["currency"] == "USD"
    assert data["balances_date"] == "2026-03-31"
    # Assets:Bank:Old closed in January; Assets:Cash is not a bank account.
    assert data["balances"] == [
        {"account": "Assets:Bank:Checking", "amount": Decimal("1700.00")},
        {"account": "Assets:Stripe", "amount": Decimal("1455.00")},
    ]
    # EUR 200 converted at the 2026-03-31 price of 1.10.
    assert data["this_month"] == {
        "month": "2026-03",
        "income": Decimal("1500.00"),
        "expenses": Decimal("337.000"),
        "net": Decimal("1163.000"),
    }
    assert data["last_month"] == {
        "month": "2026-02",
        "income": Decimal("1000.00"),
        "expenses": Decimal("70.00"),
        "net": Decimal("930.00"),
    }
    assert data["top_expenses"] == [
        {"account": "Expenses:Travel", "amount": Decimal("220.000")},
        {"account": "Expenses:Uncategorized", "amount": Decimal("60.00")},
        {"account": "Expenses:Fees:Stripe", "amount": Decimal("45.00")},
        {"account": "Expenses:Meals", "amount": Decimal("12.00")},
    ]
    assert data["review_count"] == 2
    assert data["error_count"] == 0


def test_dashboard_defaults_to_latest_data(qb_client: FlaskClient) -> None:
    data = get_dashboard(qb_client)
    assert isinstance(data, dict)

    # No time filter: the month of the last transaction (2026-04-02), not
    # today's month, which has no data.
    this_month = data["this_month"]
    assert isinstance(this_month, dict)
    assert this_month["month"] == "2026-04"
    assert data["review_count"] == 2


# --- Review queue, accept and reclassify ------------------------------------


@pytest.fixture
def review(tmp_path: Path) -> tuple[FlaskClient, Path]:
    """A client on a writable copy of qb-review.beancount, and its path."""
    ledger = tmp_path / "qb-review.beancount"
    shutil.copy(QB_DATA_DIR / "qb-review.beancount", ledger)
    app = create_app([ledger], load=True)
    app.testing = True
    return app.test_client(), ledger


def get_review(client: FlaskClient, time: str = "") -> list[dict[str, object]]:
    response = client.get(
        "/qb-review/api/qb_review", query_string={"time": time}
    )
    assert response.status_code == HTTPStatus.OK.value
    rows = response.get_json()["data"]["rows"]
    assert isinstance(rows, list)
    return rows


def entry_hash(client: FlaskClient, day: str) -> str:
    """Hash of the transaction on `day` (one per day in the fixture)."""
    response = client.get(
        "/qb-review/api/query",
        query_string={
            "query_string": f"SELECT DISTINCT id WHERE date = {day}"
        },
    )
    rows = response.get_json()["data"]["rows"]
    assert len(rows) == 1
    return str(rows[0][0])


def put(
    client: FlaskClient, endpoint: str, **body: object
) -> tuple[int, object]:
    response = client.put(f"/qb-review/api/{endpoint}", json=body)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def test_review_rows(review: tuple[FlaskClient, Path]) -> None:
    client, _ = review
    rows = get_review(client)

    assert [(r["date"], r["payee"], r["account"]) for r in rows] == [
        # No Assets or Liabilities posting: falls back to the first posting.
        ("2026-03-06", "", "Expenses:Meals"),
        ("2026-03-05", "Hardware Store", "Assets:Bank:Checking"),
        ("2026-03-02", "SaaS Co", "Liabilities:Card"),
        ("2026-03-01", "Cafe", "Assets:Bank:Checking"),
    ]
    assert rows[1]["categories"] == ["Expenses:Meals", "Expenses:Software"]
    assert rows[2]["categories"] == ["Expenses:Uncategorized"]
    assert Decimal(str(rows[2]["amount"])) == Decimal("-20.00")
    assert rows[2]["currency"] == "USD"
    assert rows[2]["entry_hash"] == entry_hash(client, "2026-03-02")

    accounts = client.get("/qb-review/api/qb_review").get_json()["data"][
        "accounts"
    ]
    assert accounts == [
        {
            "account": "Assets:Bank:Checking",
            "balance": "-130.00",
            "currency": "USD",
            "to_review": 2,
        },
        {
            "account": "Expenses:Meals",
            "balance": "35.00",
            "currency": "USD",
            "to_review": 1,
        },
        {
            "account": "Liabilities:Card",
            "balance": "-20.00",
            "currency": "USD",
            "to_review": 1,
        },
    ]

    # The header's time filter narrows the queue.
    assert [r["date"] for r in get_review(client, "2026-03-02")] == [
        "2026-03-02"
    ]


def test_accept_and_recategorise(review: tuple[FlaskClient, Path]) -> None:
    client, ledger = review
    status, data = put(
        client,
        "qb_accept",
        entry_hashes=[entry_hash(client, "2026-03-01")],
        from_account="Expenses:Uncategorized",
        to_account="Expenses:Meals",
    )

    assert status == HTTPStatus.OK.value
    assert data == {"changed": 1, "failed": []}
    text = ledger.read_text("utf-8")
    assert '2026-03-01 * "Cafe" "Lunch"\n' in text
    assert "  Assets:Bank:Checking  -10.00 USD\n  Expenses:Meals\n" in text
    assert [r["date"] for r in get_review(client)][-1] == "2026-03-02"


def test_accept_only(review: tuple[FlaskClient, Path]) -> None:
    client, ledger = review
    hashes = [
        entry_hash(client, "2026-03-05"),
        entry_hash(client, "2026-03-02"),
    ]
    status, data = put(client, "qb_accept", entry_hashes=hashes)

    assert status == HTTPStatus.OK.value
    assert data == {"changed": 2, "failed": []}
    text = ledger.read_text("utf-8")
    assert '2026-03-05 * "Hardware Store" "Split"' in text
    assert '2026-03-02 * "SaaS Co" "Card charge"' in text
    # Categories untouched, other queued entries still flagged.
    assert "  Expenses:Uncategorized   20.00 USD" in text
    assert '2026-03-01 ! "Cafe"' in text


def test_reclassify_many(review: tuple[FlaskClient, Path]) -> None:
    client, ledger = review
    days = ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04"]
    status, data = put(
        client,
        "qb_reclassify",
        entry_hashes=[entry_hash(client, day) for day in days],
        from_account="Expenses:Uncategorized",
        to_account="Expenses:Software",
    )

    assert status == HTTPStatus.OK.value
    # 2026-03-03 only has the sub-account, so it is left alone.
    assert data == {"changed": 3, "failed": []}
    text = ledger.read_text("utf-8")
    assert "  Expenses:Uncategorized:Old\n" in text
    assert "  ! Expenses:Software  40.00 USD\n" in text
    assert "  Expenses:Software   20.00 USD\n" in text
    assert "  Assets:Bank:Checking  -10.00 USD\n  Expenses:Software\n" in text
    # Reclassify doesn't accept.
    assert '2026-03-01 ! "Cafe"' in text


def test_edit_validation(review: tuple[FlaskClient, Path]) -> None:
    client, ledger = review
    before = ledger.read_text("utf-8")
    hashes = [entry_hash(client, "2026-03-01")]

    status, _ = put(
        client,
        "qb_reclassify",
        entry_hashes=hashes,
        from_account="Expenses:Uncategorized",
        to_account="Expenses:Nope",
    )
    assert status == HTTPStatus.BAD_REQUEST.value
    status, _ = put(
        client, "qb_accept", entry_hashes=hashes, to_account="Expenses:Meals"
    )
    assert status == HTTPStatus.BAD_REQUEST.value
    assert ledger.read_text("utf-8") == before


def test_edit_failures_are_reported(
    review: tuple[FlaskClient, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, ledger = review
    good = entry_hash(client, "2026-03-01")

    status, data = put(client, "qb_accept", entry_hashes=["missing", good])
    assert status == HTTPStatus.OK.value
    assert isinstance(data, dict)
    assert data["changed"] == 1
    assert [f["entry_hash"] for f in data["failed"]] == ["missing"]

    # A save that fails the sha check (file changed since it was read).
    def stale_slice(entry: Directive) -> tuple[str, str]:
        source, _ = get_entry_slice(entry)
        return source, "stale"

    monkeypatch.setattr("fava.qb_api.get_entry_slice", stale_slice)
    before = ledger.read_text("utf-8")
    status, data = put(
        client, "qb_accept", entry_hashes=[entry_hash(client, "2026-03-02")]
    )
    assert isinstance(data, dict)
    assert data["changed"] == 0
    assert len(data["failed"]) == 1
    assert ledger.read_text("utf-8") == before


# --- Bulk reclassify search, register and exports ---------------------------


def get_json(
    client: FlaskClient, endpoint: str, **params: object
) -> tuple[int, object]:
    response = client.get(f"/qb-example/api/{endpoint}", query_string=params)
    json = response.get_json()
    return response.status_code, json.get("data", json)


def test_postings_search(
    qb_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def search(**params: object) -> list[tuple[str, str]]:
        status, data = get_json(
            qb_client, "qb_postings", account_name="Expenses:Meals", **params
        )
        assert status == HTTPStatus.OK.value
        assert isinstance(data, dict)
        return [(row["date"], row["amount"]) for row in data["rows"]]

    assert search() == [("2026-03-14", "12.00"), ("2026-02-20", "40.00")]
    assert search(payee="COFFEE") == [("2026-03-14", "12.00")]
    assert search(min_amount="20") == [("2026-02-20", "40.00")]
    assert search(max_amount="20") == [("2026-03-14", "12.00")]
    assert search(time="2026-02") == [("2026-02-20", "40.00")]

    _, data = get_json(qb_client, "qb_postings", account_name="Expenses:Meals")
    assert isinstance(data, dict)
    assert data["rows"][0]["others"] == ["Assets:Cash"]
    assert data["rows"][0]["payee"] == "Cafe"

    monkeypatch.setattr("fava.qb_api.POSTINGS_LIMIT", 1)
    _, data = get_json(qb_client, "qb_postings", account_name="Expenses:Meals")
    assert isinstance(data, dict)
    assert (len(data["rows"]), data["total"]) == (1, 2)


def test_postings_search_validation(qb_client: FlaskClient) -> None:
    status, _ = get_json(
        qb_client, "qb_postings", account_name="Expenses:Nope"
    )
    assert status == HTTPStatus.BAD_REQUEST.value
    status, _ = get_json(
        qb_client, "qb_postings", account_name="Expenses:Meals", min_amount="x"
    )
    assert status == HTTPStatus.BAD_REQUEST.value


def test_register(qb_client: FlaskClient) -> None:
    def register(time: str = "") -> dict[str, object]:
        status, data = get_json(
            qb_client,
            "qb_register",
            account_name="Assets:Bank:Checking",
            time=time,
        )
        assert status == HTTPStatus.OK.value
        assert isinstance(data, dict)
        return data

    data = register()
    assert data["account"] == "Assets:Bank:Checking"
    assert data["opening"] == []
    rows = data["rows"]
    assert isinstance(rows, list)
    assert [(r["date"], r["balance"]) for r in rows] == [
        ("2026-04-02", "1695.00"),
        ("2026-03-12", "1700.00"),
        ("2026-03-10", "1760.00"),
        ("2026-03-01", "1980.00"),
        ("2026-02-20", "1010.00"),
        ("2026-01-10", "1050.00"),
        ("2026-01-02", "1000.00"),
    ]
    assert rows[2]["categories"] == ["Expenses:Travel"]
    assert rows[1]["flag"] == "!"

    # The time filter limits rows; the balance carries everything before.
    data = register("2026-03")
    assert data["opening"] == [{"currency": "USD", "amount": "1010.00"}]
    assert isinstance(data["rows"], list)
    assert [r["date"] for r in data["rows"]] == [
        "2026-03-12",
        "2026-03-10",
        "2026-03-01",
    ]
    # A range with no postings still shows the opening balance.
    data = register("2026-06")
    assert data["rows"] == []
    assert data["opening"] == [{"currency": "USD", "amount": "1695.00"}]

    status, _ = get_json(qb_client, "qb_register", account_name="Assets:Nope")
    assert status == HTTPStatus.BAD_REQUEST.value


def test_exports(qb_client: FlaskClient) -> None:
    status, data = get_json(qb_client, "qb_exports")
    assert status == HTTPStatus.OK.value
    assert isinstance(data, dict)
    # Only years with transactions; the latest is the default.
    assert (data["year"], data["years"]) == (2026, [2026])
    _, other_year = get_json(qb_client, "qb_exports", year=2025)
    assert isinstance(other_year, dict)
    assert other_year["year"] == 2025
    data = data["exports"]
    assert isinstance(data, list)
    assert [e["key"] for e in data] == [
        "trial_balance",
        "profit_loss",
        "balance_sheet",
        "general_ledger",
    ]
    assert "2026-01-01" in data[0]["query"]
    for export in data:
        response = qb_client.get(
            "/qb-example/api/query",
            query_string={"query_string": export["query"]},
        )
        result = response.get_json()["data"]
        assert result["rows"], export["key"]


# --- Bank formats and the import config --------------------------------------

IMPORT_LEDGER = QB_DATA_DIR / "import-ledger"


@pytest.fixture(scope="module")
def import_client() -> FlaskClient:
    app = create_app(
        [
            IMPORT_LEDGER / "main.beancount",
            IMPORT_LEDGER / "missing-config.beancount",
        ],
        load=True,
    )
    app.testing = True
    return app.test_client()


def test_bank_formats(import_client: FlaskClient) -> None:
    response = import_client.get("/qb-import/api/qb_bank_formats")
    assert response.status_code == HTTPStatus.OK.value
    data = response.get_json()["data"]

    by_key: dict[str, list[dict[str, object]]] = {}
    for fmt in data["formats"]:
        by_key.setdefault(fmt["key"], []).append(fmt)
    assert len(by_key["wells_fargo"]) == 2  # 2026 header and header-less
    assert by_key["wells_fargo"][1]["columns"] == []
    assert by_key["chase_checking"][0]["has_balance"] is True
    assert by_key["stripe_payouts"][0]["bank"] == "Stripe"
    amounts = {key: fmts[0]["amounts"] for key, fmts in by_key.items()}
    assert amounts["chase_checking"] == '"Amount", negative is money out'
    assert str(amounts["amex"]).endswith("(flipped on import)")
    assert str(amounts["capital_one_card"]).startswith('"Debit" is money out')
    assert "Transaction Type" in str(amounts["capital_one_360"])

    assert data["importers"] == [
        {
            "name": "chase_checking:Assets:Bank:Chase",
            "key": "chase_checking",
            "account": "Assets:Bank:Chase",
        },
        {
            "name": "stripe_payouts:Assets:Stripe",
            "key": "stripe_payouts",
            "account": "Assets:Stripe",
        },
        {"name": "<run_path>.Other", "key": "", "account": ""},
    ]
    assert data["config_file"].endswith("import-ledger/config.py")
    assert data["import_dirs"][0].endswith("import-ledger/inbox")
    assert data["errors"] == []

    # Fava's own Import page uses the importer: the Stripe transfer is
    # skipped and the statement balance comes along.
    files = import_client.get("/qb-import/api/imports").get_json()["data"]
    (inbox_file,) = [f for f in files if f["importers"]]
    assert [i["importer_name"] for i in inbox_file["importers"]] == [
        "chase_checking:Assets:Bank:Chase"
    ]
    extracted = import_client.get(
        "/qb-import/api/extract",
        query_string={
            "filename": inbox_file["name"],
            "importer": "chase_checking:Assets:Bank:Chase",
        },
    ).get_json()["data"]
    assert [e["t"] for e in extracted] == [
        "Transaction",
        "Transaction",
        "Balance",
    ]


def test_bank_formats_without_config(
    import_client: FlaskClient, qb_client: FlaskClient
) -> None:
    data = qb_client.get("/qb-example/api/qb_bank_formats").get_json()["data"]
    assert (data["importers"], data["config_file"], data["errors"]) == (
        [],
        "",
        [],
    )
    data = import_client.get(
        "/qb-import-missing/api/qb_bank_formats"
    ).get_json()["data"]
    assert data["errors"] == ["Import config does not exist"]
