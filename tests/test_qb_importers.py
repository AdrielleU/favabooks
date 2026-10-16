from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from beancount.core import data

from fava.qb_importers import BANK_FORMATS
from fava.qb_importers import BankCSV
from fava.qb_importers import BankFormat
from fava.qb_importers import StripePayouts
from fava.qb_importers.bank_csv import parse_amount
from fava.qb_importers.bank_csv import parse_date
from fava.qb_importers.bank_csv import read_rows
from fava.qb_importers.formats import BANK_FORMATS_BY_KEY

if TYPE_CHECKING:  # pragma: no cover
    from beancount.core.amount import Amount

IMPORTS = Path(__file__).parent / "qb_data" / "imports"


def units(posting: data.Posting) -> Amount:
    """The posting's units (always set on the bank leg)."""
    assert posting.units is not None
    return posting.units


#: file -> (format key, [(date, payee, amount)], closing balance or None)
EXPECTED = {
    "chase_checking.csv": (
        "chase_checking",
        [
            ("2026-10-14", "AMAZON MKTPLACE PMTS", "-64.18"),
            ("2026-10-12", "STRIPE TRANSFER ST-ABC123", "2038.50"),
            ("2026-10-01", "MESA PROPERTIES RENT", "-1800.00"),
        ],
        ("2026-10-15", "4935.82"),
    ),
    "chase_card.csv": (
        "chase_card",
        [
            ("2026-10-13", "UBER *TRIP", "-23.40"),
            ("2026-10-10", "Payment Thank You-Mobile", "500.00"),
        ],
        None,
    ),
    "bofa_checking.csv": (
        "bofa_checking",
        [
            ("2026-10-03", "ZELLE PAYMENT FROM ACME DENTAL", "1200.00"),
            ("2026-10-09", "COMCAST BUSINESS", "-315.25"),
        ],
        ("2026-10-10", "5884.75"),
    ),
    "bofa_card.csv": (
        "bofa_card",
        [
            ("2026-10-08", "STAPLES 0123", "-42.10"),
            ("2026-10-02", "PAYMENT - THANK YOU", "250.00"),
        ],
        None,
    ),
    "wells_fargo-legacy.csv": (
        "wells_fargo",
        [
            ("2026-10-14", "SHELL OIL 57444 PHOENIX AZ", "-48.12"),
            ("2026-10-05", "ONLINE TRANSFER FROM SAVINGS", "1500.00"),
        ],
        None,
    ),
    "wells_fargo-2026.csv": (  # the pending row is left out
        "wells_fargo",
        [("2026-10-14", "OFFICE DEPOT #123", "-142.77")],
        None,
    ),
    "capital_one_360.csv": (
        "capital_one_360",
        [
            ("2026-10-11", "Deposit from ACME DENTAL", "900.00"),
            ("2026-10-04", "Debit Card Purchase - GITHUB", "-21.00"),
        ],
        ("2026-10-12", "3400.00"),
    ),
    "capital_one_card.csv": (
        "capital_one_card",
        [
            ("2026-10-07", "GOOGLE *WORKSPACE", "-14.00"),
            ("2026-10-03", "CAPITAL ONE MOBILE PYMT", "300.00"),
        ],
        None,
    ),
    "citi_card.csv": (  # negative credit, pending row left out
        "citi_card",
        [
            ("2026-10-06", "FIGMA", "-15.00"),
            ("2026-10-02", "PAYMENT THANK YOU", "41.00"),
        ],
        None,
    ),
    "us_bank.csv": (
        "us_bank",
        [
            ("2026-10-09", "ADOBE *CREATIVE CLD", "-54.99"),
            ("2026-10-01", "ELECTRONIC DEPOSIT ACME", "2400.00"),
        ],
        None,
    ),
    "amex.csv": (
        "amex",
        [
            ("2026-10-12", "DELTA AIR LINES", "-412.30"),
            ("2026-10-05", "AUTOPAY PAYMENT - THANK YOU", "300.00"),
        ],
        None,
    ),
    "discover_card.csv": (
        "discover_card",
        [
            ("2026-10-11", "BAGEL BARN", "-18.75"),
            ("2026-10-03", "INTERNET PAYMENT - THANK YOU", "100.00"),
        ],
        None,
    ),
    "mercury.csv": (  # failed row left out
        "mercury",
        [
            ("2026-10-13", "Vercel", "-20.00"),
            ("2026-10-12", "Acme Dental", "1500.00"),
        ],
        None,
    ),
    "mercury-2022.csv": (
        "mercury",
        [("2022-10-03", "Stripe", "980.00")],
        None,
    ),
    "bluevine.csv": (
        "bluevine",
        [
            ("2026-10-10", "WIRE FROM COPPER LEAF YOGA", "2400.00"),
            ("2026-10-02", "ACH TO JORDAN LEE", "-1100.00"),
        ],
        ("2026-10-11", "8400.00"),
    ),
    "relay.csv": (
        "relay",
        [("2026-10-09", "GUSTO PAYROLL", "-3200.00")],
        None,
    ),
    "novo.csv": (
        "novo",
        [("2026-10-08", "SQUARESPACE", "-23.00")],
        ("2026-10-09", "1977.00"),
    ),
    "pnc.csv": (
        "pnc",
        [
            ("2026-10-06", "POS PURCHASE STAPLES", "-25.10"),
            ("2026-10-02", "DIRECT DEPOSIT CLIENT", "1000.00"),
        ],
        ("2026-10-07", "4974.90"),
    ),
}

#: Unverified layouts that look alike; tell them apart with `filename=`.
LOOKALIKES = {
    "amex": "relay",
    "relay": "amex",
    "bluevine": "novo",
    "novo": "bluevine",
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_bank_csv(name: str) -> None:
    key, rows, closing = EXPECTED[name]
    path = str(IMPORTS / name)
    importer = BankCSV(key, "Assets:Bank:Test")

    assert importer.identify(path)
    assert importer.account(path) == "Assets:Bank:Test"
    assert importer.name == f"{key}:Assets:Bank:Test"
    entries = importer.extract(path, [])
    txns = [e for e in entries if isinstance(e, data.Transaction)]
    assert [
        (str(t.date), t.payee, str(units(t.postings[0]).number)) for t in txns
    ] == rows
    assert all(t.flag == "!" for t in txns)
    assert all(t.postings[1].account == "Expenses:Uncategorized" for t in txns)
    assert all(t.postings[1].units is None for t in txns)
    assert importer.date(path) == max(t.date for t in txns)

    balances = [e for e in entries if isinstance(e, data.Balance)]
    if closing is None:
        assert balances == []
    else:
        assert [(str(b.date), str(b.amount.number)) for b in balances] == [
            closing
        ]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_files_are_recognised_by_their_own_format(name: str) -> None:
    key = EXPECTED[name][0]
    path = str(IMPORTS / name)
    matches = {
        other
        for other in BANK_FORMATS_BY_KEY
        if BankCSV(other, "Assets:X").identify(path)
    }
    assert matches - {LOOKALIKES.get(key)} == {key}
    assert not StripePayouts().identify(path)


def test_formats_are_documented() -> None:
    for fmt in BANK_FORMATS:
        assert fmt.download
        assert fmt.confidence in {"verified", "unverified"}
        assert fmt.amount or (fmt.debit and fmt.credit)


def test_bank_csv_deduplicate() -> None:
    path = str(IMPORTS / "chase_checking.csv")
    importer = BankCSV("chase_checking", "Assets:Bank:Chase")
    existing = importer.extract(path, [])
    again = importer.extract(path, [])
    importer.deduplicate(again, existing)
    assert all(entry.meta.get("__duplicate__") for entry in again)
    # The same balance for another account is new.
    fresh = BankCSV("chase_checking", "Assets:Bank:Other").extract(path, [])
    importer.deduplicate(fresh, existing)
    assert not fresh[-1].meta.get("__duplicate__")


def test_bank_csv_deduplicate_is_exact(tmp_path: Path) -> None:
    importer = BankCSV("chase_card", "Liabilities:Card")
    path = tmp_path / "card.csv"
    path.write_text(
        "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
        "10/14/2026,10/14/2026,UBER,Travel,Sale,-23.40,\n"
    )
    existing = importer.extract(str(path), [])
    path.write_text(
        "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
        "10/15/2026,10/16/2026,CAFE ROMA,Food,Sale,-22.40,\n"
        "10/16/2026,10/16/2026,UBER POSTED,Travel,Sale,-23.40,\n"
        "10/16/2026,10/16/2026,UBER AGAIN,Travel,Sale,-23.40,\n"
        "10/30/2026,10/30/2026,UBER LATER,Travel,Sale,-23.40,\n"
    )
    entries = importer.extract(str(path), [])
    importer.deduplicate(entries, existing)
    # Within 5% but not equal: new. Equal within 2 days: duplicate, once.
    assert [bool(e.meta.get("__duplicate__")) for e in entries] == [
        False,
        True,
        False,
        False,
    ]


def test_bank_csv_options(tmp_path: Path) -> None:
    path = str(IMPORTS / "chase_checking.csv")
    importer = BankCSV(
        "chase_checking",
        "Assets:Bank:Chase",
        filename="chase_checking",
        skip=["^stripe transfer"],
        uncategorized="Income:Uncategorized",
        flag="*",
        balance=False,
        currency="CAD",
    )
    entries = importer.extract(path, [])
    assert len(entries) == 2
    assert all(isinstance(e, data.Transaction) for e in entries)
    txn = entries[0]
    assert isinstance(txn, data.Transaction)
    assert txn.flag == "*"
    assert txn.narration == "DEBIT_CARD"
    assert units(txn.postings[0]).currency == "CAD"
    assert txn.postings[1].account == "Income:Uncategorized"

    assert not BankCSV("chase_checking", "A:B", filename="1234").identify(path)
    txt = tmp_path / "chase.pdf"
    txt.write_text(Path(path).read_text())
    assert not importer.identify(str(txt))


def test_bank_csv_unknown_and_custom_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Known formats: amex"):
        BankCSV("my_bank", "Assets:Bank")

    custom = BankFormat(
        key="my_credit_union",
        bank="My Credit Union",
        kind="Checking",
        download="Export",
        columns=("When", "What", "Out", "In"),
        date="When",
        description="What",
        debit="Out",
        credit="In",
        date_formats=("%d.%m.%Y",),
    )
    path = tmp_path / "cu.csv"
    path.write_text(
        "When,What,Out,In\n"
        "03.10.2026,Coffee,4.50,\n"
        "04.10.2026,Refund,,(2.00)\n"
        "05.10.2026,Nothing,,\n"
        "not a date,Broken,1.00,\n"
    )
    importer = BankCSV(custom, "Assets:Bank:CU")
    assert importer.name == "my_credit_union:Assets:Bank:CU"
    entries = importer.extract(str(path), [])
    amounts = [
        units(e.postings[0]).number
        for e in entries
        if isinstance(e, data.Transaction)
    ]
    # "(2.00)" in a credit column still counts as money in.
    assert amounts == [Decimal("-4.50"), Decimal("2.00")]


def test_bank_csv_unreadable_or_other_files(tmp_path: Path) -> None:
    importer = BankCSV("wells_fargo", "Assets:Bank:WF")
    assert not importer.identify(str(tmp_path / "missing.csv"))
    assert importer.extract(str(tmp_path / "missing.csv"), []) == []
    assert importer.date(str(tmp_path / "missing.csv")) is None

    empty = tmp_path / "empty.csv"
    empty.write_text("\n\n")
    assert not importer.identify(str(empty))
    other = tmp_path / "other.csv"
    other.write_text('"not","a","bank","file","!"\n')
    assert not importer.identify(str(other))


def test_parsers() -> None:
    assert parse_amount("$1,234.56") == Decimal("1234.56")
    assert parse_amount("(12.00)") == Decimal("-12.00")
    assert parse_amount("\N{MINUS SIGN}12.00") == Decimal("-12.00")
    assert parse_amount("  ") is None
    assert parse_amount("n/a") is None
    assert parse_date("10/14/26", ("%m/%d/%Y", "%m/%d/%y")) == datetime.date(
        2026, 10, 14
    )
    assert parse_date("yesterday", ("%m/%d/%Y",)) is None
    fmt = BANK_FORMATS_BY_KEY["chase_checking"][0]
    assert read_rows(str(IMPORTS / "amex.csv"), fmt) is None


# --- Stripe ------------------------------------------------------------------


def stripe_entries() -> list[data.Transaction]:
    """The Stripe fixture's entries (all transactions)."""
    importer = StripePayouts(
        "Assets:Stripe", bank="Assets:Bank:Chase", income="Income:Sales"
    )
    entries = importer.extract(str(IMPORTS / "stripe-itemized.csv"), [])
    txns = [e for e in entries if isinstance(e, data.Transaction)]
    assert len(txns) == len(entries)
    return txns


def postings(txn: data.Transaction) -> list[tuple[str, str]]:
    return [(p.account, str(units(p).number)) for p in txn.postings]


def test_stripe_payouts() -> None:
    importer = StripePayouts()
    path = str(IMPORTS / "stripe-itemized.csv")
    assert importer.identify(path)
    assert importer.name == "stripe_payouts:Assets:Stripe"
    assert importer.account(path) == "Assets:Stripe"
    assert importer.date(path) == datetime.date(2026, 10, 10)

    charge, refund, fee, dispute, payout1, payout2 = stripe_entries()
    assert (charge.flag, charge.payee, charge.narration) == (
        "*",
        "Acme Dental",
        "Invoice 10-03",
    )
    assert charge.meta["invoice"] == "in_1"
    assert charge.meta["payout"] == "po_1A"
    assert charge.meta["stripe_txn"] == "txn_1"
    assert postings(charge) == [
        ("Assets:Stripe", "1455.20"),
        ("Expenses:Fees:Stripe", "44.80"),
        ("Income:Sales", "-1500.00"),
    ]
    assert postings(refund) == [
        ("Assets:Stripe", "-100.00"),
        ("Income:Sales", "100.00"),
    ]
    assert (fee.payee, postings(fee)) == (
        None,
        [("Assets:Stripe", "-15.00"), ("Expenses:Fees:Stripe", "15.00")],
    )
    assert dispute.flag == "!"
    assert postings(dispute)[-1] == ("Expenses:Uncategorized", "900.00")

    # One transfer per payout, dated when it lands, net of everything in it.
    assert (payout1.date, payout1.narration) == (
        datetime.date(2026, 10, 6),
        "Payout po_1A",
    )
    assert postings(payout1) == [
        ("Assets:Stripe", "-1340.20"),
        ("Assets:Bank:Chase", "1340.20"),
    ]
    # The "payout" row itself is skipped; a dispute can make a payout negative.
    assert postings(payout2) == [
        ("Assets:Stripe", "915.00"),
        ("Assets:Bank:Chase", "-915.00"),
    ]


def test_stripe_deduplicate() -> None:
    importer = StripePayouts()
    existing: data.Entries = [*stripe_entries()[:1], stripe_entries()[-2]]
    entries: data.Entries = list(stripe_entries())
    importer.deduplicate(entries, existing)
    assert [bool(e.meta.get("__duplicate__")) for e in entries] == [
        True,
        False,
        False,
        False,
        True,
        False,
    ]


def test_stripe_other_files(tmp_path: Path) -> None:
    importer = StripePayouts(filename="itemized")
    assert not importer.identify(str(IMPORTS / "amex.csv"))
    assert not importer.identify(str(tmp_path / "stripe.xlsx"))
    renamed = tmp_path / "stripe-report.csv"
    text = (IMPORTS / "stripe-itemized.csv").read_text()
    renamed.write_text(text)
    assert not importer.identify(str(renamed))  # name lacks "itemized"
    assert importer.extract(str(renamed), []) == []
    assert importer.date(str(renamed)) is None

    # Minimal columns: no customer, payout or invoice; email as payee.
    minimal = tmp_path / "itemized-min.csv"
    minimal.write_text(
        "balance_transaction_id,created_utc,reporting_category,gross,fee,net,"
        "customer_email\n"
        "txn_9,2026-10-01 10:00:00,charge,50.00,1.75,48.25,a@b.example\n"
        "txn_10,bad date,charge,50.00,1.75,48.25,\n"
    )
    (txn,) = importer.extract(str(minimal), [])
    assert isinstance(txn, data.Transaction)
    assert txn.payee == "a@b.example"
    assert txn.narration == "charge"
    assert "payout" not in txn.meta
