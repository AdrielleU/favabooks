/**
 * qb-fork: CSV files in QuickBooks Online's import layouts (no DOM imports,
 * so they can be unit tested).
 */
import type { QbQboExport } from "../api.ts";
import { iso, to_csv } from "../docs/periods.ts";

/** "MM/DD/YYYY", QuickBooks Online's (US) import date format. */
export function us_date(date: Date): string {
  const [y = "", m = "", d = ""] = iso(date).split("-");
  return `${m}/${d}/${y}`;
}

const amount = (n: number) => (n ? n.toFixed(2) : "");

/** The four import files: [file name, CSV text]. */
export function qbo_files(data: QbQboExport): [string, string][] {
  const year = data.year.toString();
  return [
    [
      `1-chart-of-accounts-${year}.csv`,
      to_csv([
        ["Account Name", "Type", "Detail Type", "Description"],
        ...data.accounts.map((a) => [
          a.name,
          a.type,
          a.detail_type,
          `Favabooks: ${a.account}`,
        ]),
      ]),
    ],
    [
      `2-customers-${year}.csv`,
      to_csv([
        ["Name", "Email"],
        ...data.customers.map((c) => [c.name, c.email]),
      ]),
    ],
    [
      `3-vendors-${year}.csv`,
      to_csv([
        ["Name", "Email"],
        ...data.vendors.map((v) => [v.name, v.email]),
      ]),
    ],
    [
      `4-journal-entries-${year}.csv`,
      to_csv([
        [
          "Journal No.",
          "Journal Date",
          "Account Name",
          "Debits",
          "Credits",
          "Description",
          "Name",
        ],
        ...data.lines.map((l) => [
          l.journal_no,
          us_date(l.date),
          l.account,
          amount(l.debit),
          amount(l.credit),
          l.description,
          l.name,
        ]),
      ]),
    ],
  ];
}
