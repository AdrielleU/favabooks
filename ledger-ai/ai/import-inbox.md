# Import the inbox

Import the files in `inbox/`, following AGENTS.md.

1. List the inbox with the qb_inbox command from AGENTS.md, and look at every
   file.
1. Bank and card CSVs an importer reads: preview, then `--save`. Then fix the
   categories of the new `Expenses:Uncategorized` entries (money in lands there
   too), using how each payee was booked before.
1. Receipts and invoices (PDFs, photos): read each one. If a matching
   transaction exists (same amount, within a few days), add `document:` to it.
   Otherwise add a new `!` transaction. Then move the file to
   `documents/<account folders>/YYYY-MM-DD short-name.ext`.
1. Anything else (a CSV no importer reads, a statement, a contract): say what it
   is and ask before booking it. Don't delete it.
1. Run the check and fix what it reports.
1. Finish with a short summary: files imported, entries added, categories you
   weren't sure about, files left in the inbox and why. Remind the owner to
   accept the new entries in Favabooks → For review.
