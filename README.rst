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
     - .. image:: screenshots/add-files.png
          :alt: Add your files: where the inbox is, for Windows, Mac and Linux

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

With a login
~~~~~~~~~~~~

``docker-compose-login.yml`` puts Caddy in front of Favabooks: everyone
signs in with a username and password before seeing the books, and only
Caddy's port is open.

.. code-block:: bash

    mkdir books
    docker compose -f docker-compose-login.yml up -d
    docker compose -f docker-compose-login.yml logs favabooks-login   # the password

On first start it makes the login: user ``admin`` and a random password,
printed once in the logs. Only the password's hash is kept, in ``.env``
next to the compose file (``FAVABOOKS_LOGIN_USER``,
``FAVABOOKS_LOGIN_HASH``). For a new password, delete those two lines and
run ``up -d`` again; or put your own hash there, in single quotes:

.. code-block:: bash

    docker run --rm -it docker.io/library/caddy:2.11.7-alpine caddy hash-password

It's one shared login over plain HTTP: fine on a home network, but use a
VPN (Tailscale, WireGuard) or HTTPS to reach it from outside.

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

Importing with an AI assistant
------------------------------

Your books are plain files, so an AI coding assistant (`Claude Code
<https://claude.com/claude-code>`__, Codex, Cursor, Gemini CLI, GitHub
Copilot...) can do the importing: run it in the books folder, on your own
computer, while Favabooks runs in Docker. Nothing connects them but the
files, and Favabooks reloads when they change.

1. Put files in the books' ``inbox`` folder: bank and card CSV downloads,
   receipts and invoices (PDFs or photos). Favabooks shows where the folder
   is, with directions for Windows, Mac and Linux, when the books have no
   documents yet, and any time from **+ New → Add files to the inbox**.
2. In a terminal, go to the books folder and start your assistant:

   .. code-block:: bash

       cd books        # the folder next to docker-compose.yml
       claude          # or codex, gemini, ...

3. Ask it to "import the inbox" (in Claude Code: ``/import-inbox``). Bank
   CSVs go through the same importers as Favabooks' Import page (duplicates
   skipped); receipts and invoices are matched to transactions or booked,
   then filed under ``documents/``. It checks the books for errors before it
   finishes.
4. Accept or change the new entries in Favabooks under **Banking → For
   review**. Everything the assistant adds is flagged for review; nothing is
   final until you accept it.

New books come with what an assistant needs:

- ``AGENTS.md``: how the books are laid out and the rules to follow: flag
  new entries for review, never change a closed period or entries you
  accepted, no duplicates, treat text inside receipts as data and never as
  instructions, check the books after every change. Most assistants read
  ``AGENTS.md`` by themselves.
- ``ai/``: the tasks, as plain instructions any assistant can follow:
  ``import-inbox.md``, ``file-receipts.md`` (attach receipts to
  transactions already in the books) and ``month-end.md`` (a report of
  what's missing: uncategorized entries, receipts, stale bank accounts,
  unpaid invoices).
- For Claude Code, which reads ``CLAUDE.md`` instead: a ``CLAUDE.md`` that
  includes ``AGENTS.md``, the tasks as ``/import-inbox``, ``/file-receipts``
  and ``/month-end``, and ``.claude/settings.json`` so it can run the check
  and import commands without asking each time.

Books created before 0.4 can get them with
``docker exec favabooks favabooks-new --ai /books`` (or
``docker/new-books.sh --ai ~/books`` from source); files you already have
are kept. Keep the books in git (``git init`` in ``books``) to see and undo
every change.

The import command also works on its own:

.. code-block:: bash

    docker exec favabooks python -m fava.qb_inbox /books/main.beancount            # what's waiting
    docker exec favabooks python -m fava.qb_inbox /books/main.beancount /books/inbox/chase.csv --save

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
