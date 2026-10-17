# Favabooks roadmap

What's built, what's next, and what's further out. Checked items are done. Ideas
and bug reports are welcome as GitHub issues.

## Done

- [x] QuickBooks-style shell: top bar, grouped icon nav with a "+ New" menu,
  light and dark theme, Fava's stock pages restyled
- [x] Dashboard: cash, income, expenses and net profit vs last month; bank
  accounts, P&L, expense breakdown, to-do cards
- [x] For review: accept or recategorise imported transactions one by one or in
  bulk, filtered by account
- [x] Register with running balance and inline category changes
- [x] Bulk reclassify across many transactions
- [x] Export for CPA: trial balance, P&L, balance sheet and general ledger as
  CSV or XLSX
- [x] Bank and card CSV importers (Chase, Bank of America, Wells Fargo, Capital
  One, Citi, U.S. Bank, Amex, Discover, Mercury, plus unverified Bluevine,
  Relay, Novo and PNC) and a Stripe payout importer
- [x] Bank & card accounts page: connect accounts in a wizard (bank, ledger
  account, column mapping with live preview for other banks); saved
  automatically, no config editing
- [x] Imported files are filed away automatically after Save
- [x] Expense spreadsheet import with column mapping and receipt filing (like
  QuickBooks' file upload and receipts)
- [x] Year menus and the dashboard follow the years the books have data for
- [x] Demo company ledger, CI, Docker image on ghcr.io, tagged releases
- [x] All transactions, Customers/Invoices, Vendors/Bills, report center with
  charts, chart of accounts with nicknames, QuickBooks Online export

## Next: finish Phase 1

- [x] Release v0.2.0 (importers and the new UI)
- [x] Release v0.3.0 (sales, expenses, reports, month-end)
- [x] Release v0.4.0 (several companies, AI assistant intake)
- [ ] Verify the unverified bank layouts (Bluevine, Relay, Novo, PNC) against
  real downloads; a header row is enough
- [ ] Category suggestions from past choices (smart_importer) so imports arrive
  pre-categorised
- [ ] Bank rules: "payee contains X → category Y", applied on import
- [ ] Payout matching check: every Stripe payout has a bank deposit and the
  other way round
- [ ] Optional Stripe sales-tax split (looks up each invoice's tax with a
  read-only API key)
- [ ] Deployment guide: login at a reverse proxy, git auto-commit, nightly
  backups, go-live checklist
- [ ] ARM (arm64) Docker image as well as amd64

## Phase 2: month-end

- [x] Reconcile: tick transactions against a statement, see the difference, save
  the statement balance
- [x] Close books: lock a period so nothing on or before a date can change
- [ ] Review queue tabs: For review, Accepted, Excluded

## Phase 3: customers and vendors

- [x] Customers and vendors lists built from payment metadata
- [x] A/R and A/P aging (0–30, 31–60, 61–90, 90+ days)
- [x] Invoices and bills: import from CSV or record with the PDF, match payments
  (bookkeeping only; invoices are still sent elsewhere)
- [x] 1099 vendor review (bank and check payments at or above the IRS threshold
  for the year)
- [ ] Read-only vs editor access, enforced at the reverse proxy

## UI

- [x] QuickBooks-style report pages: P&L, balance sheet, debit/credit trial
  balance, general ledger, with charts, print and export toolbar
- [ ] Global search for transactions, payees and accounts
- [ ] Collapsible icon-rail nav
- [x] Notes and empty states for Fava's pages; new Currencies & prices, Business
  details and Statistics pages
- [ ] Favabooks help pages
- [ ] Compact "Filters" button on phones

## Accounting conventions

Each needs an account convention, a check or a report:

- [ ] Owner contributions and draws
- [ ] Intercompany balances between entities (paired accounts that must net to
  zero)
- [ ] Deferred revenue for annual prepaid plans (accrual books)
- [ ] Fixed assets and depreciation entries
- [ ] Tax-line mapping on accounts, grouped in the CPA export
- [ ] Recurring entries (rent, subscriptions) generated monthly

## Later

- [x] Several companies (and personal books) in one Favabooks
- [x] AI assistant intake: AGENTS.md and ai/ tasks (import the inbox, file
  receipts, month-end) in new books, with a Claude Code adapter; an "Add your
  files" popup with directions
- [ ] Receipt and invoice intake inside Favabooks: read PDFs and photos, propose
  an entry, file the document
- [ ] Payroll provider journal import

## Housekeeping

- [ ] Merge upstream Fava monthly
- [ ] Send Fava a fix for building on Python 3.11 (`typing_extensions` missing
  from the build requirements)
