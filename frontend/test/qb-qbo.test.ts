import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import { qbo_files, us_date } from "../src/qb/exports/qbo.ts";

const d = (iso: string) => new Date(`${iso}T00:00:00Z`);

test("us date", () => {
  equal(us_date(d("2025-03-07")), "03/07/2025");
});

test("qbo files", () => {
  const files = qbo_files({
    year: 2025,
    mode: "transactions",
    currency: "USD",
    accounts: [
      {
        name: "Legal - Startup",
        type: "Expenses",
        detail_type: "Legal & Professional Fees",
        account: "Expenses:Legal:Startup",
      },
    ],
    customers: [{ name: "Acme, Inc", email: "" }],
    vendors: [],
    lines: [
      {
        journal_no: "FB2025-0001",
        date: d("2025-01-03"),
        account: "Legal - Startup",
        debit: 184,
        credit: 0,
        description: "ZenBusiness",
        name: "",
      },
    ],
    journals: 1,
    skipped: [],
  });
  deepEqual(
    files.map(([name]) => name),
    [
      "1-chart-of-accounts-2025.csv",
      "2-customers-2025.csv",
      "3-vendors-2025.csv",
      "4-journal-entries-2025.csv",
    ],
  );
  equal(
    files[0]?.[1],
    "Account Name,Type,Detail Type,Description\nLegal - Startup,Expenses,Legal & Professional Fees,Favabooks: Expenses:Legal:Startup\n",
  );
  equal(files[1]?.[1], 'Name,Email\n"Acme, Inc",\n');
  equal(
    files[3]?.[1].split("\n")[1],
    "FB2025-0001,01/03/2025,Legal - Startup,184.00,,ZenBusiness,",
  );
});
