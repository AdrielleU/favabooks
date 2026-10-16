# Fava runs this file directly; it is not a package.  # noqa: INP001
"""Import config used by tests/test_qb_api.py."""

from __future__ import annotations

from beangulp.importer import Importer

from fava.qb_importers import BankCSV
from fava.qb_importers import StripePayouts


class Other(Importer):
    """An importer that isn't one of Favabooks'."""

    def identify(self, filepath: str) -> bool:  # noqa: ARG002
        """Never matches."""
        return False

    def account(self, filepath: str) -> str:  # noqa: ARG002
        """A fixed account."""
        return "Assets:Other"


CONFIG = [
    BankCSV("chase_checking", "Assets:Bank:Chase", skip=["^STRIPE"]),
    StripePayouts("Assets:Stripe", bank="Assets:Bank:Chase"),
    Other(),
]
