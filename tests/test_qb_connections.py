from __future__ import annotations

import shutil
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

from fava.application import create_app
from fava.qb_importers.settings import CustomLayout
from fava.qb_importers.settings import importers_from_settings
from fava.qb_importers.settings import read_settings
from fava.qb_importers.settings import Settings

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient

IMPORTS = Path(__file__).parent / "qb_data" / "imports"

LEDGER = """option "title" "QB Connect"
option "operating_currency" "USD"

2026-01-01 open Assets:Bank:Checking
2026-01-01 open Expenses:Uncategorized

2026-02-01 * "Opening"
  Assets:Bank:Checking   10.00 USD
  Expenses:Uncategorized
"""

#: An "unknown bank": its own column names, a bad date and a blank amount.
MYBANK = """When,What,Out,In
02/03/2026,Coffee,4.50,
02/04/2026,Refund,,2.00
2026-13-45,Bad date,1.00,
02/06/2026,No amount,,
"""


def make_client(tmp_path: Path, options: str = "") -> tuple[FlaskClient, Path]:
    main = tmp_path / "main.beancount"
    main.write_text(LEDGER + options)
    app = create_app([main], load=True)
    app.testing = True
    return app.test_client(), main


def api(
    client: FlaskClient, method: str, endpoint: str, **kw: object
) -> tuple[int, object]:
    if method in {"get", "delete"}:
        # Fava reads GET and DELETE parameters from the query string.
        response = client.open(
            f"/qb-connect/api/{endpoint}",
            method=method.upper(),
            query_string=kw,
        )
    else:
        response = client.open(
            f"/qb-connect/api/{endpoint}", method=method.upper(), json=kw
        )
    json = response.get_json()
    return response.status_code, json.get("data", json)


def setup(client: FlaskClient) -> dict[str, Any]:
    status, data = api(client, "get", "qb_import_setup")
    assert status == HTTPStatus.OK.value
    assert isinstance(data, dict)
    return data


def test_connections_flow(tmp_path: Path) -> None:  # noqa: PLR0915
    client, main = make_client(tmp_path)
    data = setup(client)
    assert (data["status"], data["inbox"], data["connections"]) == (
        "off",
        [],
        [],
    )
    assert {b["bank"] for b in data["banks"]} >= {"Chase", "Mercury", "Stripe"}

    # Saving needs the managed config first.
    status, _ = api(client, "put", "qb_connection", connection={})
    assert status == HTTPStatus.BAD_REQUEST.value

    status, message = api(client, "put", "qb_import_enable")
    assert status == HTTPStatus.OK.value
    assert "Bank connections are on" in str(message)
    assert (tmp_path / "importers" / "config.py").exists()
    assert (tmp_path / "importers" / "favabooks-import.json").exists()
    assert '"import-config" "importers/config.py"' in main.read_text()
    assert setup(client)["status"] == "managed"
    _, message = api(client, "put", "qb_import_enable")
    assert message == "Bank connections are already on."

    inbox = tmp_path / "inbox"
    shutil.copy(IMPORTS / "chase_checking.csv", inbox / "Chase1234.csv")
    shutil.copy(IMPORTS / "stripe-itemized.csv", inbox / "stripe.csv")
    (inbox / "mybank.csv").write_text(MYBANK)
    (inbox / "notes.pdf").write_text("not a statement")
    (inbox / "two-columns.csv").write_text("a,b\n1,2\n")
    (inbox / "no-amount.csv").write_text(
        "When,What,Out,In\n02/06/2026,Nothing,,\n"
    )
    files = {f["basename"]: f for f in setup(client)["inbox"]}
    assert files["Chase1234.csv"]["detected"] == ["chase_checking"]
    assert files["Chase1234.csv"]["importers"] == []
    assert files["stripe.csv"]["detected"] == ["stripe_payouts"]
    assert files["mybank.csv"]["header"] == ["When", "What", "Out", "In"]
    assert files["mybank.csv"]["sample"][0] == [
        "02/03/2026",
        "Coffee",
        "4.50",
        "",
    ]
    assert files["notes.pdf"]["header"] == []
    assert files["two-columns.csv"]["header"] == []

    def preview(name: str, **connection: object) -> dict[str, Any]:
        status, data = api(
            client,
            "put",
            "qb_connection_preview",
            filename=str(inbox / name),
            connection=connection,
        )
        assert status == HTTPStatus.OK.value, data
        assert isinstance(data, dict)
        return data

    chase = preview("Chase1234.csv", kind="bank", format="chase_checking")
    assert (
        chase["matches"],
        chase["total"],
        chase["parsed"],
        chase["problem"],
    ) == (
        True,
        3,
        3,
        "",
    )
    assert chase["rows"][0]["amount"] == "-64.18"
    stripe = preview("stripe.csv", kind="stripe")
    assert stripe["matches"] is True
    assert stripe["problem"] == ""

    layout = {
        "date": "When",
        "description": "What",
        "debit": "Out",
        "credit": "In",
    }
    custom = preview("mybank.csv", kind="custom", layout=layout)
    assert (custom["total"], custom["parsed"]) == (4, 2)
    assert [r["amount"] for r in custom["rows"]] == ["-4.50", "2.00"]
    assert custom["problem"] == "Line 4: can't read date '2026-13-45'"
    iso = preview(
        "mybank.csv",
        kind="custom",
        layout={**layout, "date_format": "%Y-%m-%d"},
    )
    assert iso["parsed"] == 0
    assert iso["problem"].startswith("Line 2: can't read date")
    no_date_issue = preview(
        "mybank.csv",
        kind="custom",
        layout={
            "date": "What",
            "description": "When",
            "debit": "Out",
            "credit": "In",
            "date_format": "%b",
        },
    )
    assert no_date_issue["parsed"] == 0
    blank = preview("no-amount.csv", kind="custom", layout=layout)
    assert blank["problem"] == "Line 2: no amount"
    # A layout that doesn't fit the file at all.
    wrong = preview("mybank.csv", kind="bank", format="amex")
    assert (wrong["matches"], wrong["rows"]) == (False, [])
    assert wrong["problem"] == "The file's columns don't match this layout."
    status, _ = api(
        client,
        "put",
        "qb_connection_preview",
        filename="/etc/passwd",
        connection={"kind": "bank", "format": "amex"},
    )
    assert status == HTTPStatus.BAD_REQUEST.value
    status, _ = api(
        client,
        "put",
        "qb_connection_preview",
        filename=str(inbox / "mybank.csv"),
        connection={"kind": 3},
    )
    assert status == HTTPStatus.BAD_REQUEST.value

    # Save: a new ledger account is opened for it.
    status, conn_id = api(
        client,
        "put",
        "qb_connection",
        connection={
            "kind": "bank",
            "format": "chase_checking",
            "account": "Liabilities:CreditCard:Chase-1234",
            "name": "Chase 1234",
            "filename": "1234",
            "skip_stripe": True,
        },
    )
    assert status == HTTPStatus.OK.value, conn_id
    assert isinstance(conn_id, str)
    assert "open Liabilities:CreditCard:Chase-1234" in main.read_text()
    api(
        client,
        "put",
        "qb_connection",
        connection={
            "kind": "custom",
            "account": "Assets:Bank:Checking",
            "name": "My bank",
            "layout": layout,
        },
    )
    api(
        client,
        "put",
        "qb_connection",
        connection={
            "kind": "stripe",
            "account": "Assets:Stripe",
            "payout_account": "Assets:Bank:Checking",
        },
    )
    data = setup(client)
    views = {v["bank"]: v for v in data["connections"]}
    assert set(views) == {"Chase", "Other bank", "Stripe"}
    assert views["Chase"]["kind_label"] == "Checking & savings"
    assert views["Other bank"]["last_date"] == "2026-02-01"
    files = {f["basename"]: f for f in data["inbox"]}
    assert files["Chase1234.csv"]["importers"] == [
        "chase_checking:Liabilities:CreditCard:Chase-1234:1234"
    ]
    assert files["mybank.csv"]["importers"] == [
        "custom-{}:Assets:Bank:Checking".format(
            views["Other bank"]["connection"]["id"]
        )
    ]

    # Updating keeps the id; deleting removes it.
    status, same_id = api(
        client,
        "put",
        "qb_connection",
        connection={
            **views["Chase"]["connection"],
            "name": "Chase card",
        },
    )
    assert same_id == conn_id
    status, _ = api(client, "delete", "qb_connection", connection_id=conn_id)
    assert status == HTTPStatus.OK.value
    assert {v["bank"] for v in setup(client)["connections"]} == {
        "Other bank",
        "Stripe",
    }

    for bad in (
        {"kind": "nope", "account": "Assets:X"},
        {"kind": "bank", "format": "nope", "account": "Assets:X"},
        {"kind": "custom", "account": "Assets:X"},
        {"kind": "bank", "format": "amex", "account": "not an account"},
        {"kind": "bank"},
    ):
        status, _ = api(client, "put", "qb_connection", connection=bad)
        assert status == HTTPStatus.BAD_REQUEST.value, bad


def test_enable_with_existing_config(tmp_path: Path) -> None:
    config = tmp_path / "config.py"
    config.write_text("CONFIG = []\n")
    client, _ = make_client(
        tmp_path,
        '2026-01-01 custom "fava-option" "import-config" "config.py"\n',
    )
    assert setup(client)["status"] == "custom"
    status, message = api(client, "put", "qb_import_enable")
    assert status == HTTPStatus.OK.value
    assert "Added saved connections" in str(message)
    assert "CONFIG += importers_from_settings(__file__)" in config.read_text()
    assert setup(client)["status"] == "managed"


def test_enable_with_missing_config(tmp_path: Path) -> None:
    client, _ = make_client(
        tmp_path,
        '2026-01-01 custom "fava-option" "import-config" "imp/c.py"\n',
    )
    data = setup(client)
    assert (data["status"], data["connections"]) == ("missing", [])
    api(client, "put", "qb_import_enable")
    assert (tmp_path / "imp" / "c.py").exists()
    assert setup(client)["status"] == "managed"


def test_settings_helpers(tmp_path: Path) -> None:
    assert read_settings(tmp_path / "none.json") == Settings()
    assert importers_from_settings(tmp_path / "config.py") == []
    fmt = CustomLayout(
        date="D",
        description="X",
        amount="A",
        negate=True,
        date_format="%d.%m.%Y",
    ).to_format("k", "Bank")
    assert (fmt.amount, fmt.debit, fmt.negate, fmt.date_formats) == (
        "A",
        None,
        True,
        ("%d.%m.%Y",),
    )
    assert fmt.columns == ("D", "X", "A")
    _ = Decimal  # used by the API's amounts
