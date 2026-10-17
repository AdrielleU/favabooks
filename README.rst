Favabooks
=========

Favabooks is a bookkeeping UI for small businesses that keep their books in
plain-text `Beancount <https://github.com/beancount/beancount>`__ files. It
adds QuickBooks-like screens for banking, sales, expenses, reports and
month-end alongside every page of the stock Fava UI, and ships as one Docker
image.

**Favabooks is a fork of** `Fava <https://github.com/beancount/fava>`__ **by
Dominik Aumayr and the Fava contributors.** Almost all of this code is
theirs, and the full Fava history is kept in this repository. Fava is MIT
licensed; see ``LICENSE`` and ``NOTICE``. Favabooks is not affiliated with
the Fava or Beancount projects, or with Intuit.

.. image:: screenshots/dashboard.png
   :alt: Favabooks dashboard

What Favabooks adds
-------------------

- **Shell:** QuickBooks-style top bar and grouped icon nav with a "+ New"
  menu, a light/dark theme that also restyles Fava's own pages, and a note on
  each of Fava's pages saying what it's for
- **Dashboard:** cash, income, expenses and net profit vs last month, bank
  balances, top expenses, review and error counts
- **Banking:** a "for review" queue (accept or recategorise imports one by
  one or in bulk), Bank & card accounts (connect each account once in a
  wizard), bank/card/Stripe CSV importers for major US banks, imported files
  filed away automatically, and Reconcile against a statement
- **Transactions:** All transactions (types, search, dates, receipts, CSV
  export), a register per account, and bulk reclassify
- **Sales and expenses:** Customers, Invoices, Vendors and Bills: import them
  from a CSV or record them (with the PDF), match payments, aging, date
  filters, and 1099-NEC review for vendors
- **Reports:** a report center, profit and loss (by month, quarter or year,
  compared with the previous period), balance sheet, trial balance and general
  ledger, with KPI cards, charts, drill-down, CSV export and print
- **Export for CPA:** a year-end checklist, the reports as CSV or Excel, and
  QuickBooks Online import files (chart of accounts, customers, vendors,
  journal entries)
- **Accounting:** a chart of accounts with QuickBooks account types, account
  nicknames, adding and closing accounts, and Close books (locks a period:
  balance checks flag any later change)
- **Advanced:** currencies and prices, business details with dated reminders,
  and book statistics
- **Receipts:** expense spreadsheet import with receipts, and the
  ``fava.qb_receipts`` plugin that checks every receipt a transaction names
- Docker image and compose file (``docker/``)

.. list-table::
   :widths: 50 50

   * - .. image:: screenshots/transactions.png
          :alt: All transactions
     - .. image:: screenshots/invoices.png
          :alt: Invoices
   * - .. image:: screenshots/profit-and-loss.png
          :alt: Profit and loss with charts
     - .. image:: screenshots/balance-sheet.png
          :alt: Balance sheet
   * - .. image:: screenshots/for-review.png
          :alt: For review queue
     - .. image:: screenshots/export-for-cpa.png
          :alt: Export for CPA
   * - .. image:: screenshots/chart-of-accounts.png
          :alt: Chart of accounts
     -

Screenshots show the fictional demo company in ``ledger-template/``. See
`ROADMAP.md <ROADMAP.md>`__ for what's next.

New code lives in ``frontend/src/qb/`` and ``src/fava/qb_api.py``. Changes to
Fava's own files are kept small and marked ``qb-fork``.

Self-hosting with Docker
------------------------

One image has everything: Beancount, Fava and the Favabooks UI. Download
`docker-compose.yml <docker-compose.yml>`__ into an empty folder, then:

.. code-block:: bash

    mkdir books                     # your books live here, as plain files
    FAVABOOKS_COMPANY="Acme LLC" docker compose up -d
    # open http://localhost:5000

On first run it creates new books in ``./books`` with a starter chart of
accounts. Set ``FAVABOOKS_STARTER=demo`` to start with the fictional demo
company instead. Update with ``docker compose pull && docker compose up -d``.
The container runs as user 1000; if ``books`` belongs to another user, see
the comment in the compose file.

Fava has no login, so the compose file only listens on this computer. Before
opening it to a network, put it behind a reverse proxy with a login;
``docker/compose.yaml`` is a production setup (git auto-commit, proxy port).

Several companies, or personal money
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One Favabooks can keep the books of several LLCs and your personal money,
each in its own folder with its own accounts and documents. List one
``main.beancount`` per company in ``LEDGERS`` in the compose file:

.. code-block:: yaml

    LEDGERS: "/books/main.beancount /books/second-llc/main.beancount /books/personal/main.beancount"

then run ``docker compose up -d``. Books that don't exist yet are created
and named after their folder (``second-llc`` becomes "Second LLC"); a folder
named like ``personal``, ``household`` or ``family`` gets a household chart
of accounts (groceries, rent, salary, draws from your business) instead of
a business one. Switch between them from the company name at the top left.
If something is wrong, such as two companies in one folder or with the same
name, the container stops with a message saying what to fix (see
``docker compose logs``).

Everyone who can open Favabooks can open every company in it. To keep
someone out of a company, run it as a separate instance (a second folder
with its own compose file and port) behind its own login.

Without Docker, create books with ``docker/new-books.sh``:

.. code-block:: bash

    docker/new-books.sh ~/books/second-llc            # business, "Second LLC"
    docker/new-books.sh ~/books/personal personal "Our household"
    uv run fava ~/books/main.beancount ~/books/second-llc/main.beancount

Running from source
-------------------

.. code-block:: bash

    make dev                       # needs uv and Node 22.22.2+ / 24.15+
    cp -r ledger-template /tmp/demo-books   # fictional demo company
    uv run fava /tmp/demo-books/main.beancount

----

The original Fava README follows.

----

.. image:: https://img.shields.io/gitter/room/beancount/fava
   :alt: Join the chat at https://gitter.im/beancount/fava
   :target: https://gitter.im/beancount/fava
.. image:: https://img.shields.io/pypi/l/fava
   :alt: PyPI - License
   :target: https://github.com/beancount/fava/blob/main/LICENSE
.. image:: https://img.shields.io/pypi/v/fava
   :alt: PyPI - Version
   :target: https://pypi.org/project/fava/

Fava is a web interface for the double-entry bookkeeping software `Beancount
<http://furius.ca/beancount/>`__ with a focus on features and usability.

Check out the online `demo <https://fava.pythonanywhere.com>`__ and learn more
about Fava on the `website <https://beancount.github.io/fava/>`__.

The `Getting Started
<https://beancount.github.io/fava/usage.html>`__ guide details the installation
and how to get started with Beancount.  If you are already familiar with
Beancount, you can get started with Fava::

    pip3 install fava
    fava ledger.beancount

and visit the web interface at `http://localhost:5000
<http://localhost:5000>`__.

If you want to hack on Fava or run a development version, see the
`Development <https://beancount.github.io/fava/development.html>`__ page on the
website for details. Contributions are very welcome!
