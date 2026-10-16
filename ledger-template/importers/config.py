# Fava runs this file directly; it is not a package.  # noqa: INP001
"""Import config for the Sample Studio LLC demo ledger.

Each line maps one bank download to a ledger account. Formats are listed on
the Bank formats page in Favabooks (Banking → Bank formats).
"""

from __future__ import annotations

from fava.qb_importers import BankCSV
from fava.qb_importers import StripePayouts

CONFIG = [
    # Stripe payouts are booked by the Stripe importer, so leave them out of
    # the bank file.
    BankCSV("chase_checking", "Assets:Bank:Checking", skip=["^STRIPE"]),
    BankCSV("chase_card", "Liabilities:CreditCard:Visa"),
    StripePayouts("Assets:Stripe", bank="Assets:Bank:Checking"),
]
