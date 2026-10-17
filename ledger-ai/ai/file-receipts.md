# File receipts

Match the receipts and invoices in `inbox/` (PDFs, images) to transactions that
are already in the books, following AGENTS.md.

For each file: read the vendor, date and total. Find the transaction with the
same amount within a few days (card charges post a day or two later). If exactly
one matches, add `document: "<new name>"` to it and move the file to that
transaction's account folder in `documents/` as `YYYY-MM-DD short-name.ext`. If
several match, or none, don't guess: list them for the owner. Don't create new
transactions unless the owner asks.

Run the check at the end. Summarize: filed, ambiguous, no match.
