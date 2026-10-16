"""Bank connections: set up statement imports from the UI (qb-fork).

The Bank connections page saves connected accounts to favabooks-import.json
next to the ledger's import config (see fava.qb_importers.settings), opens
ledger accounts that don't exist yet, and can turn imports on for a ledger.
"""

from __future__ import annotations

import csv
import datetime
import os
import uuid
from decimal import Decimal
from pathlib import Path
from typing import cast
from typing import TYPE_CHECKING

import msgspec
from beancount.core import account as account_lib
from beancount.core import data
from beancount.parser.grammar import ValueType
from msgspec import Struct

from fava.beans import create
from fava.context import g
from fava.json_api import api_endpoint
from fava.json_api import ValidationError
from fava.qb_importers import BANK_FORMATS
from fava.qb_importers import BankCSV
from fava.qb_importers import StripePayouts
from fava.qb_importers.bank_csv import parse_date
from fava.qb_importers.bank_csv import read_rows
from fava.qb_importers.bank_csv import row_amount
from fava.qb_importers.formats import BANK_FORMATS_BY_KEY
from fava.qb_importers.settings import CONFIG_TEMPLATE
from fava.qb_importers.settings import Connection
from fava.qb_importers.settings import importer_for
from fava.qb_importers.settings import read_settings
from fava.qb_importers.settings import SETTINGS_IMPORT
from fava.qb_importers.settings import settings_path
from fava.qb_importers.settings import write_settings
from fava.util.date import local_today

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Directive
    from fava.qb_importers.formats import BankFormat

#: Rows of a sample file shown for column mapping.
SAMPLE_ROWS = 5
KINDS = {"bank", "custom", "stripe"}


class QbFormatChoice(Struct, frozen=True):
    """One account type a bank exports (first layout of a format key)."""

    key: str
    kind: str
    download: str
    confidence: str


class QbBankChoice(Struct, frozen=True):
    """A bank and the account types it exports."""

    bank: str
    formats: list[QbFormatChoice]


class QbConnectionView(Struct, frozen=True):
    """A saved connection with its bank's display details."""

    connection: Connection
    bank: str
    kind_label: str
    download: str
    #: Latest transaction in the account, and statements filed under it.
    last_date: datetime.date | None = None
    documents: int = 0


class QbInboxFile(Struct, frozen=True):
    """A file waiting in the inbox."""

    filename: str
    basename: str
    #: Importers (connections) that recognise it.
    importers: list[str]
    #: Built-in format keys whose layout matches it.
    detected: list[str]
    #: First row with several cells (for column mapping) and sample rows.
    header: list[str]
    sample: list[list[str]]


class QbImportSetup(Struct, frozen=True):
    """Everything the Bank connections page shows."""

    #: "off" (no import config), "missing" (config file not found),
    #: "managed" (config reads the saved connections) or "custom".
    status: str
    config_file: str
    import_dirs: list[str]
    errors: list[str]
    connections: list[QbConnectionView]
    banks: list[QbBankChoice]
    inbox: list[QbInboxFile]


def _config_file() -> Path | None:
    return g.ledger.ingest.module_path


def _status(config: Path | None) -> str:
    if config is None:
        return "off"
    if not config.exists():
        return "missing"
    text = config.read_text(encoding="utf-8")
    return "managed" if SETTINGS_IMPORT in text else "custom"


def _banks() -> list[QbBankChoice]:
    banks: dict[str, dict[str, QbFormatChoice]] = {}
    for fmt in BANK_FORMATS:
        banks.setdefault(fmt.bank, {}).setdefault(
            fmt.key,
            QbFormatChoice(fmt.key, fmt.kind, fmt.download, fmt.confidence),
        )
    choices = [
        QbBankChoice(bank, list(formats.values()))
        for bank, formats in banks.items()
    ]
    choices.append(
        QbBankChoice(
            "Stripe",
            [
                QbFormatChoice(
                    "stripe_payouts",
                    "Payouts (itemized payout reconciliation)",
                    "Reports → Payouts reconciliation → Download → Itemized",
                    "verified",
                )
            ],
        )
    )
    return choices


def _view(connection: Connection) -> QbConnectionView:
    if connection.kind == "stripe":
        bank, kind, download = (
            "Stripe",
            "Payouts",
            "Reports → Payouts reconciliation → Download → Itemized",
        )
    elif connection.kind == "custom":
        bank, kind, download = "Other bank", "Custom CSV", ""
    else:
        fmt = BANK_FORMATS_BY_KEY[connection.format][0]
        bank, kind, download = fmt.bank, fmt.kind, fmt.download
    ledger = g.ledger
    dates = [
        txn.date
        for txn in ledger.all_entries_by_type.Transaction
        if any(p.account == connection.account for p in txn.postings)
    ]
    documents = sum(
        1
        for doc in ledger.all_entries_by_type.Document
        if doc.account == connection.account
    )
    return QbConnectionView(
        connection, bank, kind, download, max(dates, default=None), documents
    )


def _sample(path: Path) -> tuple[list[str], list[list[str]]]:
    """First row with three or more cells, and the rows after it."""
    if path.suffix.lower() not in {".csv", ".txt"}:
        return [], []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rows = [
        r for r in csv.reader(text.splitlines()) if any(c.strip() for c in r)
    ]
    for index, row in enumerate(rows):
        if len(row) >= 3:
            body = rows[index + 1 : index + 1 + SAMPLE_ROWS]
            return [c.strip() for c in row], body
    return [], []


def _detect(path: str) -> list[str]:
    keys = [
        k for k in BANK_FORMATS_BY_KEY if BankCSV(k, "Assets:X").identify(path)
    ]
    if StripePayouts().identify(path):
        keys.append("stripe_payouts")
    return keys


@api_endpoint
def get_qb_import_setup() -> QbImportSetup:
    """Connections, supported banks and the inbox, for the setup page."""
    ledger = g.ledger
    ledger.changed()
    config = _config_file()
    status = _status(config)
    connections = (
        read_settings(settings_path(config)).connections
        if config is not None and status != "missing"
        else []
    )
    inbox = [
        QbInboxFile(
            filename=str(file.name),
            basename=file.basename,
            importers=[i.importer_name for i in file.importers],
            detected=_detect(str(file.name)),
            header=(sample := _sample(Path(file.name)))[0],
            sample=sample[1],
        )
        for file in ledger.ingest.import_data()
    ]
    return QbImportSetup(
        status=status,
        config_file=str(config) if config else "",
        import_dirs=[
            str(ledger.join_path(d)) for d in ledger.fava_options.import_dirs
        ],
        errors=[error.message for error in ledger.ingest.errors],
        connections=[_view(c) for c in connections],
        banks=_banks(),
        inbox=inbox,
    )


def _open_if_missing(accounts: list[str]) -> None:
    """Open accounts the ledger doesn't have yet (as of its first year)."""
    ledger = g.ledger
    missing = [a for a in dict.fromkeys(accounts) if a not in ledger.accounts]
    for account in missing:
        if not account_lib.is_valid(account):
            msg = f"'{account}' is not a valid account name"
            raise ValidationError(msg)
    if not missing:
        return
    txns = ledger.all_entries_by_type.Transaction
    year = min([local_today().year, *(t.date.year for t in txns[:1])])
    ledger.file.insert_entries(
        [
            create.open({}, datetime.date(year, 1, 1), account, [])
            for account in missing
        ]
    )


def _reload_config(config: Path) -> None:
    """Make Fava reload the import config (it watches the file's mtime)."""
    os.utime(config)
    g.ledger.ingest.load_file()


def _managed_config() -> Path:
    g.ledger.changed()
    config = _config_file()
    if config is None or _status(config) != "managed":
        msg = "turn on Bank connections first"
        raise ValidationError(msg)
    return config


def _validate(connection: Connection) -> None:
    if connection.kind not in KINDS:
        msg = f"unknown connection kind '{connection.kind}'"
        raise ValidationError(msg)
    if (
        connection.kind == "bank"
        and connection.format not in BANK_FORMATS_BY_KEY
    ):
        msg = f"unknown bank format '{connection.format}'"
        raise ValidationError(msg)
    layout = connection.layout
    if connection.kind == "custom" and (
        layout is None
        or not layout.date
        or not layout.description
        or not (layout.amount or (layout.debit and layout.credit))
    ):
        msg = "map the date, description and amount columns"
        raise ValidationError(msg)


@api_endpoint
def put_qb_connection(connection: dict[str, object]) -> str:
    """Save (add or update) a connection; returns its id.

    Takes a plain object: Fava resolves endpoint parameter types in its own
    module, so the Connection struct is converted here.
    """
    config = _managed_config()
    try:
        parsed = msgspec.convert(connection, Connection)
    except msgspec.ValidationError as error:
        raise ValidationError(str(error)) from error
    _validate(parsed)
    _open_if_missing(
        [parsed.account]
        + ([parsed.payout_account] if parsed.payout_account else [])
    )
    path = settings_path(config)
    settings = read_settings(path)
    saved = msgspec.structs.replace(
        parsed, id=parsed.id or uuid.uuid4().hex[:8]
    )
    settings.connections = [
        c for c in settings.connections if c.id != saved.id
    ] + [saved]
    write_settings(path, settings)
    _reload_config(config)
    return saved.id


@api_endpoint
def delete_qb_connection(connection_id: str) -> str:
    """Remove a connection (files already imported stay booked)."""
    config = _managed_config()
    path = settings_path(config)
    settings = read_settings(path)
    settings.connections = [
        c for c in settings.connections if c.id != connection_id
    ]
    write_settings(path, settings)
    _reload_config(config)
    return connection_id


@api_endpoint
def put_qb_import_enable() -> str:
    """Turn on Bank connections for this ledger.

    With no import config: create importers/config.py, the settings file and
    an inbox/ folder next to the ledger, and add the import-config and
    import-dirs options. With a hand-written config: add the line that
    loads saved connections to its end.
    """
    ledger = g.ledger
    ledger.changed()
    config = _config_file()
    status = _status(config)
    if status == "managed":
        return "Bank connections are already on."
    if config is not None and status == "custom":
        with config.open("a", encoding="utf-8") as file:
            file.write(
                "\n\n# Accounts connected on the Bank connections page.\n"
                "from fava.qb_importers.settings import "
                "importers_from_settings  # noqa: E402\n\n"
                "CONFIG += importers_from_settings(__file__)\n"
            )
        _reload_config(config)
        return f"Added saved connections to {config}."
    if config is None:
        base = Path(ledger.beancount_file_path).parent
        config = base / "importers" / "config.py"
        inbox = base / "inbox"
        txns = ledger.all_entries_by_type.Transaction
        year = min([local_today().year, *(t.date.year for t in txns[:1])])
        day = datetime.date(year, 1, 1)
        options = [
            data.Custom(
                {},
                day,
                "fava-option",
                [ValueType(key, str), ValueType(value, str)],
            )
            for key, value in (
                ("import-config", "importers/config.py"),
                ("import-dirs", "inbox"),
            )
        ]
        ledger.file.insert_entries(cast("list[Directive]", options))
        inbox.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    write_settings(settings_path(config), read_settings(settings_path(config)))
    return f"Bank connections are on: {config}."


class QbPreviewRow(Struct, frozen=True):
    """A transaction as a draft connection would import it."""

    date: datetime.date
    payee: str
    amount: Decimal
    currency: str


class QbPreview(Struct, frozen=True):
    """What a draft connection makes of a file in the inbox."""

    #: The connection recognises the file.
    matches: bool
    #: First rows as they would be imported.
    rows: list[QbPreviewRow]
    #: Data rows in the file, and how many become transactions.
    total: int
    parsed: int
    #: The first row that can't be read, in words ("" if none).
    problem: str


def _inbox_file(filename: str) -> Path:
    """A file in the inbox (only those: this reads files from disk)."""
    g.ledger.changed()
    names = {str(f.name) for f in g.ledger.ingest.import_data()}
    if filename not in names:
        msg = "not a file in the import folders"
        raise ValidationError(msg)
    return Path(filename)


def _problem(path: Path, connection: Connection) -> str:
    """The first data row a bank layout can't read."""
    if connection.kind == "stripe":
        return ""
    layouts: tuple[BankFormat, ...]
    if connection.kind == "custom" and connection.layout is not None:
        layouts = (connection.layout.to_format("preview", "Custom"),)
    else:
        layouts = BANK_FORMATS_BY_KEY[connection.format]
    for fmt in layouts:
        rows = read_rows(str(path), fmt)
        if rows is None:
            continue
        for row in rows:
            if parse_date(row.get(fmt.date), fmt.date_formats) is None:
                return (
                    f"Line {row.lineno}: can't read date '{row.get(fmt.date)}'"
                )
            if row_amount(row, fmt) is None:
                return f"Line {row.lineno}: no amount"
        return ""
    return "The file's columns don't match this layout."


@api_endpoint
def put_qb_connection_preview(
    filename: str, connection: dict[str, object]
) -> QbPreview:
    """Preview a draft connection on a file waiting in the inbox."""
    path = _inbox_file(filename)
    try:
        draft = msgspec.convert(
            {"id": "preview", "account": "Assets:Preview", **connection},
            Connection,
        )
    except msgspec.ValidationError as error:
        raise ValidationError(str(error)) from error
    _validate(draft)
    importer = importer_for(draft)
    if not importer.identify(str(path)):
        return QbPreview(
            matches=False,
            rows=[],
            total=0,
            parsed=0,
            problem=_problem(path, draft),
        )
    txns = [
        e
        for e in importer.extract(str(path), [])
        if isinstance(e, data.Transaction)
    ]
    # Bank files: rows that are kept or skipped on purpose count as data.
    total = len(txns)
    if draft.kind != "stripe":
        layout = (
            draft.layout.to_format("preview", "Custom")
            if draft.kind == "custom" and draft.layout is not None
            else next(
                f
                for f in BANK_FORMATS_BY_KEY[draft.format]
                if read_rows(str(path), f) is not None
            )
        )
        total = len(read_rows(str(path), layout) or [])
    return QbPreview(
        matches=True,
        rows=[
            QbPreviewRow(
                t.date,
                t.payee or t.narration or "",
                *_first_amount(t),
            )
            for t in txns[:10]
        ],
        total=total,
        parsed=len(txns),
        problem=_problem(path, draft),
    )


def _first_amount(txn: data.Transaction) -> tuple[Decimal, str]:
    units = txn.postings[0].units
    return (
        (units.number, units.currency)
        if units is not None and units.number is not None
        else (Decimal(), "")
    )
