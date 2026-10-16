"""Bank, card and Stripe CSV importers for Favabooks (beangulp).

Use them in the ledger's importers/config.py::

    from fava.qb_importers import BankCSV, StripePayouts

    CONFIG = [
        BankCSV("chase_checking", "Assets:Bank:Checking", skip=["STRIPE"]),
        BankCSV("amex", "Liabilities:CreditCard:Amex"),
        StripePayouts("Assets:Stripe", bank="Assets:Bank:Checking"),
    ]

Expense spreadsheets with receipts: see ``fava.qb_importers.expense_csv``.

The Bank formats page in Favabooks lists every format key.
"""

from __future__ import annotations

from fava.qb_importers.bank_csv import BankCSV
from fava.qb_importers.expense_csv import ExpenseColumns
from fava.qb_importers.expense_csv import ExpenseCSV
from fava.qb_importers.expense_csv import ExpenseReceipts
from fava.qb_importers.formats import BANK_FORMATS
from fava.qb_importers.formats import BankFormat
from fava.qb_importers.stripe_payouts import StripePayouts

__all__ = [
    "BANK_FORMATS",
    "BankCSV",
    "BankFormat",
    "ExpenseCSV",
    "ExpenseColumns",
    "ExpenseReceipts",
    "StripePayouts",
]
