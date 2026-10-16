from __future__ import annotations

from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from fava.application import create_app

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient


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


def test_dashboard_defaults_to_today(qb_client: FlaskClient) -> None:
    data = get_dashboard(qb_client)
    assert isinstance(data, dict)

    this_month = data["this_month"]
    assert isinstance(this_month, dict)
    assert this_month["month"] >= "2026-10"
    assert data["review_count"] == 2
