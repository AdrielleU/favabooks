Favabooks
=========

Favabooks is a bookkeeping UI for small businesses that keep their books in
plain-text `Beancount <https://github.com/beancount/beancount>`__ files. It
adds QuickBooks-like screens (a dashboard, a bank "for review" queue, an
account register, bulk reclassify) alongside every page of the stock Fava UI,
and ships as one Docker image.

**Favabooks is a fork of** `Fava <https://github.com/beancount/fava>`__ **by
Dominik Aumayr and the Fava contributors.** Almost all of this code is
theirs, and the full Fava history is kept in this repository. Fava is MIT
licensed; see ``LICENSE`` and ``NOTICE``. Favabooks is not affiliated with
the Fava or Beancount projects, or with Intuit.

What Favabooks adds
-------------------

- Grouped left navigation and a light/dark theme (``frontend/css/qb-theme.css``)
- Dashboard: bank balances, profit and loss this month vs last, top expenses,
  review and error counts
- For review: accept or recategorise imported transactions, one by one or in bulk
- Register: per-account register with running balance and inline category edits
- Bulk reclassify: move postings between accounts across many transactions
- Export for CPA: trial balance, P&L, balance sheet and general ledger as
  CSV or XLSX for a chosen year
- Placeholders for screens in progress (reconcile, customers, vendors, …)
- Docker image and compose file (``docker/``)

New code lives in ``frontend/src/qb/`` and ``src/fava/qb_api.py``. Changes to
Fava's own files are kept small and marked ``qb-fork``.

Running it
----------

.. code-block:: bash

    make dev                       # needs uv and Node 22.22.2+ / 24.15+
    cp -r ledger-template /tmp/demo-books   # fictional demo company
    uv run fava /tmp/demo-books/main.beancount

or with Docker: ``cd docker && docker compose up -d --build``. Fava has no
login, so put it behind an authenticating reverse proxy before exposing it.

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
