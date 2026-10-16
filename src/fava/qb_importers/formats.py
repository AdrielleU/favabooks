"""CSV download formats of US banks, card issuers and business accounts.

Each format names the columns that identify the file (its header) and which
columns hold the date, description and amount. Header names match without
regard to case. A bank can have several layouts under one key (old and new
exports); the importer tries them in order.

Banks change their exports from time to time. When a file stops being
recognised, fix the layout here, or pass your own `BankFormat` to `BankCSV`
in importers/config.py. Sources for each layout are noted next to it.
"""

from __future__ import annotations

from dataclasses import dataclass

US_DATE = ("%m/%d/%Y", "%m/%d/%y")
ISO_DATE = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


@dataclass(frozen=True)
class BankFormat:
    """How one bank's CSV download is laid out.

    Amounts end up signed from the account holder's side: money out of a
    bank account, and purchases on a card, are negative.
    """

    #: Identifier used in importers/config.py, e.g. "chase_checking".
    key: str
    bank: str
    #: "Checking & savings", "Credit card" or "Business banking".
    kind: str
    #: Where to download the CSV in online banking.
    download: str
    #: Header columns that must all be present to recognise the file.
    #: Empty for header-less files, which use `positional` instead.
    columns: tuple[str, ...]
    date: str
    description: str
    #: A single signed amount column...
    amount: str | None = None
    #: ...or separate debit (money out) and credit (money in) columns;
    #: either may be signed, only the absolute values are used.
    debit: str | None = None
    credit: str | None = None
    #: Flip the sign of `amount` (cards that list purchases as positive).
    negate: bool = False
    #: Column whose value decides the sign of an unsigned `amount`, and the
    #: (lowercase) values that mean money out.
    sign_column: str | None = None
    out_values: tuple[str, ...] = ()
    date_formats: tuple[str, ...] = US_DATE
    #: Columns added to the narration, e.g. a memo or transaction type.
    memo: tuple[str, ...] = ()
    #: Running balance column, used for a statement balance assertion.
    balance: str | None = None
    #: Status column and the (lowercase) values to leave out, e.g. pending.
    status: str | None = None
    skip_status: tuple[str, ...] = ()
    #: Columns that must NOT be in the header (to tell similar files apart).
    absent: tuple[str, ...] = ()
    #: Column names, in order, for files without a header row.
    positional: tuple[str, ...] = ()
    #: "verified" (header confirmed from published samples or importer
    #: code) or "unverified" (no published header: check your download).
    confidence: str = "verified"


BANK_FORMATS: tuple[BankFormat, ...] = (
    # Sources: github.com/mcintalmo/personal-finance docs/source-schemas.md,
    # github.com/LaunchPlatform/beanhub-extract (chase.py).
    BankFormat(
        key="chase_checking",
        bank="Chase",
        kind="Checking & savings",
        download="Account → Activity → download icon → CSV (desktop site)",
        columns=("Details", "Posting Date", "Description", "Amount"),
        date="Posting Date",
        description="Description",
        amount="Amount",
        memo=("Type",),
        balance="Balance",
    ),
    BankFormat(
        key="chase_card",
        bank="Chase",
        kind="Credit card",
        download="Card → Activity → download icon → CSV",
        columns=("Transaction Date", "Post Date", "Description", "Amount"),
        date="Transaction Date",
        description="Description",
        amount="Amount",
        memo=("Memo",),
    ),
    # Source: github.com/openaccountant/wilson (data/csv/bofa-*).
    BankFormat(
        key="bofa_checking",
        bank="Bank of America",
        kind="Checking & savings",
        download='Account → Download → "Microsoft Excel" format (.csv)',
        columns=("Date", "Description", "Amount", "Running Bal."),
        date="Date",
        description="Description",
        amount="Amount",
        balance="Running Bal.",
    ),
    BankFormat(
        key="bofa_card",
        bank="Bank of America",
        kind="Credit card",
        download="Card → Download transactions → CSV",
        columns=("Posted Date", "Reference Number", "Payee", "Amount"),
        date="Posted Date",
        description="Payee",
        amount="Amount",
    ),
    # Sources: github.com/ddgarrett/load_statements (2026 header change),
    # beancount.io/tools/csv-to-beancount/wells-fargo. Checking, savings and
    # cards share one layout; the old one has no header row.
    BankFormat(
        key="wells_fargo",
        bank="Wells Fargo",
        kind="Checking, savings & cards",
        download='Account activity → Download Account Activity → "Comma '
        'Delimited"',
        columns=("Date", "Description", "Amount", "Check #"),
        date="Date",
        description="Description",
        amount="Amount",
        status="Status",
        skip_status=("pending",),
    ),
    BankFormat(
        key="wells_fargo",
        bank="Wells Fargo",
        kind="Checking, savings & cards",
        download='Account activity → Download Account Activity → "Comma '
        'Delimited"',
        columns=(),
        positional=("Date", "Amount", "Star", "Check", "Description"),
        date="Date",
        description="Description",
        amount="Amount",
    ),
    # Sources: github.com/nozzlegear/foxy-balance, github.com/tomthehare/
    # moneypit. Amounts are positive; Transaction Type says the direction.
    BankFormat(
        key="capital_one_360",
        bank="Capital One",
        kind="Checking & savings (360)",
        download="Account → Download transactions → CSV",
        columns=(
            "Transaction Date",
            "Transaction Description",
            "Transaction Amount",
            "Transaction Type",
        ),
        date="Transaction Date",
        description="Transaction Description",
        amount="Transaction Amount",
        sign_column="Transaction Type",
        out_values=("debit",),
        balance="Balance",
    ),
    # Source: beancount.io/tools/csv-to-beancount/capital-one.
    BankFormat(
        key="capital_one_card",
        bank="Capital One",
        kind="Credit card",
        download="Card → View transactions → Download Transactions → CSV",
        columns=("Transaction Date", "Posted Date", "Card No.", "Debit"),
        date="Transaction Date",
        description="Description",
        debit="Debit",
        credit="Credit",
        date_formats=ISO_DATE,
        memo=("Category",),
    ),
    # Source: the Citi extractor in github.com/LaunchPlatform/beanhub-extract.
    # Payments and refunds are listed as negative credits.
    BankFormat(
        key="citi_card",
        bank="Citi",
        kind="Credit card",
        download="Account Details → Transactions → Export → CSV",
        columns=("Status", "Date", "Description", "Debit", "Credit"),
        date="Date",
        description="Description",
        debit="Debit",
        credit="Credit",
        status="Status",
        skip_status=("pending",),
    ),
    # Source: beancount.io/tools/csv-to-beancount/us-bank.
    BankFormat(
        key="us_bank",
        bank="U.S. Bank",
        kind="Checking & cards",
        download="Account → Download transactions → CSV (desktop site)",
        columns=("Date", "Transaction", "Name", "Memo", "Amount"),
        date="Date",
        description="Name",
        amount="Amount",
        date_formats=("%Y-%m-%d", *US_DATE),
    ),
    # Sources: beancount.io/tools/csv-to-beancount/amex,
    # github.com/openaccountant/wilson. Purchases are positive.
    BankFormat(
        key="amex",
        bank="American Express",
        kind="Credit card",
        download="Statements & Activity → Download → CSV",
        columns=("Date", "Description", "Amount"),
        absent=("Running Bal.", "Balance", "Status", "Transaction"),
        date="Date",
        description="Description",
        amount="Amount",
        negate=True,
    ),
    # Source: github.com/redstreet/beancount_reds_importers (discover).
    BankFormat(
        key="discover_card",
        bank="Discover",
        kind="Credit card",
        download="Activity → Download → CSV",
        columns=("Trans. Date", "Post Date", "Description", "Amount"),
        date="Trans. Date",
        description="Description",
        amount="Amount",
        negate=True,
        memo=("Category",),
    ),
    # Sources: github.com/LaunchPlatform/beanhub-extract (mercury.py),
    # github.com/mtlynch/beancount-mercury. "Date" before November 2022.
    BankFormat(
        key="mercury",
        bank="Mercury",
        kind="Business banking",
        download="Transactions → filter → Export → CSV",
        columns=("Date (UTC)", "Description", "Amount", "Status"),
        date="Date (UTC)",
        description="Description",
        amount="Amount",
        date_formats=("%m-%d-%Y", "%m-%d-%Y %H:%M:%S", *US_DATE),
        memo=("Note",),
        status="Status",
        skip_status=("failed", "cancelled", "canceled", "pending"),
    ),
    BankFormat(
        key="mercury",
        bank="Mercury",
        kind="Business banking",
        download="Transactions → filter → Export → CSV",
        columns=("Date", "Description", "Amount", "Status", "Reference"),
        date="Date",
        description="Description",
        amount="Amount",
        date_formats=("%m-%d-%Y", *US_DATE),
        memo=("Note",),
        status="Status",
        skip_status=("failed", "cancelled", "canceled", "pending"),
    ),
    # No published header rows for these; the layouts follow the banks'
    # help pages (Bluevine: support.bluevine.com "export ... CSV"). Check a
    # download against the Bank formats page, or pass your own BankFormat.
    BankFormat(
        key="bluevine",
        bank="Bluevine",
        kind="Business banking",
        download="Checking → Export → pick dates (not today) → CSV (web only)",
        columns=("Date", "Description", "Amount", "Balance"),
        absent=("Running Bal.", "Status", "Transaction"),
        date="Date",
        description="Description",
        amount="Amount",
        date_formats=(*ISO_DATE, *US_DATE),
        balance="Balance",
        confidence="unverified",
    ),
    BankFormat(
        key="relay",
        bank="Relay",
        kind="Business banking",
        download="Accounts → Statements → Export → CSV",
        columns=("Date", "Description", "Amount"),
        absent=("Running Bal.", "Balance", "Status", "Transaction"),
        date="Date",
        description="Description",
        amount="Amount",
        date_formats=(*US_DATE, *ISO_DATE),
        confidence="unverified",
    ),
    BankFormat(
        key="novo",
        bank="Novo",
        kind="Business banking",
        download="Activity → Download CSV → pick dates",
        columns=("Date", "Description", "Amount", "Balance"),
        absent=("Running Bal.", "Status", "Transaction"),
        date="Date",
        description="Description",
        amount="Amount",
        date_formats=(*US_DATE, *ISO_DATE),
        balance="Balance",
        confidence="unverified",
    ),
    BankFormat(
        key="pnc",
        bank="PNC",
        kind="Checking & savings",
        download="Account → Transaction history → Download → CSV (90 days)",
        columns=("Date", "Description", "Withdrawals", "Deposits"),
        date="Date",
        description="Description",
        debit="Withdrawals",
        credit="Deposits",
        balance="Balance",
        confidence="unverified",
    ),
)

#: Layouts by key; a key with several layouts accepts any of them.
BANK_FORMATS_BY_KEY: dict[str, tuple[BankFormat, ...]] = {}
for _fmt in BANK_FORMATS:
    BANK_FORMATS_BY_KEY[_fmt.key] = (
        *BANK_FORMATS_BY_KEY.get(_fmt.key, ()),
        _fmt,
    )
