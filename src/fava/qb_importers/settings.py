"""Bank connections saved from the Favabooks UI.

The "Bank connections" page writes the accounts you connect to
`favabooks-import.json` next to the ledger's import config. The config
builds importers from it with one line::

    from fava.qb_importers.settings import importers_from_settings

    CONFIG = importers_from_settings(__file__)
    # Hand-written importers can still be added: CONFIG += [...]
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from fava.qb_importers.bank_csv import BankCSV
from fava.qb_importers.formats import BankFormat
from fava.qb_importers.formats import ISO_DATE
from fava.qb_importers.formats import US_DATE
from fava.qb_importers.stripe_payouts import StripePayouts

if TYPE_CHECKING:  # pragma: no cover
    from beangulp.importer import Importer

SETTINGS_FILE = "favabooks-import.json"

#: The line that makes an import config read the saved connections.
SETTINGS_IMPORT = "importers_from_settings"

CONFIG_TEMPLATE = '''"""Import config for Favabooks.

Accounts connected on the Bank connections page are saved in
favabooks-import.json next to this file and loaded here.
"""

from fava.qb_importers.settings import importers_from_settings

CONFIG = importers_from_settings(__file__)
# Hand-written importers can be added below, e.g.:
# CONFIG += [MyImporter()]
'''


class CustomLayout(msgspec.Struct, frozen=True, kw_only=True):
    """Column mapping for a bank that isn't one of the built-in formats."""

    date: str
    description: str
    #: One signed amount column...
    amount: str = ""
    #: ...or money-out and money-in columns.
    debit: str = ""
    credit: str = ""
    #: The amount column lists money out (purchases) as positive.
    negate: bool = False
    #: strptime format; empty tries common US and ISO formats.
    date_format: str = ""
    balance: str = ""

    def to_format(self, key: str, bank: str) -> BankFormat:
        """The BankFormat the importer uses."""
        columns = [self.date, self.description]
        columns += [c for c in (self.amount, self.debit, self.credit) if c]
        return BankFormat(
            key=key,
            bank=bank,
            kind="Custom CSV",
            download="",
            columns=tuple(columns),
            date=self.date,
            description=self.description,
            amount=self.amount or None,
            debit=self.debit or None,
            credit=self.credit or None,
            negate=self.negate,
            date_formats=(
                (self.date_format,)
                if self.date_format
                else (*US_DATE, *ISO_DATE)
            ),
            balance=self.balance or None,
        )


class Connection(msgspec.Struct, frozen=True, kw_only=True):
    """One connected account: which files to import and where to book them."""

    #: "bank" (a built-in format), "custom" (a column mapping) or "stripe".
    kind: str
    #: Ledger account the file belongs to.
    account: str
    #: Assigned when first saved.
    id: str = ""
    #: Display name, e.g. "Chase Sapphire 1234".
    name: str = ""
    #: Built-in format key (kind "bank").
    format: str = ""
    #: Column mapping (kind "custom").
    layout: CustomLayout | None = None
    #: Text the file name must contain, to tell accounts apart.
    filename: str = ""
    #: Leave out Stripe payouts (the Stripe connection books them).
    skip_stripe: bool = False
    #: Where Stripe payouts land (kind "stripe").
    payout_account: str = ""
    currency: str = "USD"


class Settings(msgspec.Struct, kw_only=True):
    """Everything saved on the Bank connections page."""

    version: int = 1
    connections: list[Connection] = msgspec.field(default_factory=list)


def settings_path(config_file: str | Path) -> Path:
    """The settings file next to an import config."""
    return Path(config_file).parent / SETTINGS_FILE


def read_settings(path: Path) -> Settings:
    """Saved settings, or empty ones if the file doesn't exist yet."""
    if not path.exists():
        return Settings()
    return msgspec.json.decode(path.read_bytes(), type=Settings)


def write_settings(path: Path, settings: Settings) -> None:
    """Save settings (pretty-printed, so they diff well in git)."""
    data = msgspec.json.format(msgspec.json.encode(settings), indent=2)
    path.write_bytes(data + b"\n")


def importer_for(connection: Connection) -> Importer:
    """The importer for one connection."""
    if connection.kind == "stripe":
        return StripePayouts(
            connection.account,
            bank=connection.payout_account or "Assets:Bank:Checking",
            filename=connection.filename or None,
        )
    if connection.kind == "custom" and connection.layout is not None:
        fmt: str | BankFormat = connection.layout.to_format(
            f"custom-{connection.id}", connection.name or "Custom CSV"
        )
    else:
        fmt = connection.format
    return BankCSV(
        fmt,
        connection.account,
        currency=connection.currency,
        filename=connection.filename or None,
        skip=["^STRIPE"] if connection.skip_stripe else (),
    )


def importers_from_settings(config_file: str | Path) -> list[Importer]:
    """Importers for every connection saved next to `config_file`."""
    settings = read_settings(settings_path(config_file))
    return [importer_for(c) for c in settings.connections]
