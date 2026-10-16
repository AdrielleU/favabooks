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
- [x] Bank formats page with a config snippet builder
- [x] Demo company ledger, CI, Docker image on ghcr.io, tagged releases

## Next: finish Phase 1

- [x] Release v0.2.0 (importers and the new UI)
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

- [ ] Reconcile: tick transactions against a statement, see the difference, save
  the statement balance
- [ ] Close books: lock a period so nothing on or before a date can change
- [ ] Review queue tabs: For review, Accepted, Excluded

## Phase 3: customers and vendors

- [ ] Customers and vendors lists built from payment metadata
- [ ] A/R and A/P aging (0–30, 31–60, 61–90, 90+ days)
- [ ] Invoices and bills (only where Stripe doesn't already cover invoicing)
- [ ] 1099 vendor report (payees at or above the IRS threshold)
- [ ] Read-only vs editor access, enforced at the reverse proxy

## UI

- [ ] QuickBooks-style report pages: single-column P&L, debit/credit trial
  balance, print and export toolbar
- [ ] Global search for transactions, payees and accounts
- [ ] Collapsible icon-rail nav
- [ ] Empty states for Documents, Commodities, Events and Errors
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

- [ ] Receipt and invoice intake: read PDFs and photos, propose an entry, file
  the document
- [ ] Payroll provider journal import

## Housekeeping

- [ ] Merge upstream Fava monthly
- [ ] Send Fava a fix for building on Python 3.11 (`typing_extensions` missing
  from the build requirements)
