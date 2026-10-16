import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import {
  aging,
  data_months,
  data_years,
  in_period,
  month_period,
  nec_threshold,
  presets,
  resolve_period,
  sort_by,
  to_csv,
} from "../src/qb/docs/periods.ts";

const d = (iso: string) => new Date(`${iso}T00:00:00Z`);
const today = d("2026-02-15");
const month = (key: string) => {
  const period = month_period(key);
  if (period === null) {
    throw new Error(`not a month: ${key}`);
  }
  return period;
};

test("presets", () => {
  const p = Object.fromEntries(
    presets(today).map((x) => [x.key, [x.start, x.end]]),
  );
  deepEqual(p.all, ["", ""]);
  deepEqual(p["this-month"], ["2026-02-01", "2026-02-28"]);
  deepEqual(p["last-month"], ["2026-01-01", "2026-01-31"]);
  deepEqual(p["this-quarter"], ["2026-01-01", "2026-03-31"]);
  deepEqual(p["last-quarter"], ["2025-10-01", "2025-12-31"]);
  deepEqual(p["last-year"], ["2025-01-01", "2025-12-31"]);
  deepEqual(p["last-12"], ["2025-03-01", "2026-02-28"]);
});

test("months, years and resolving", () => {
  deepEqual(month_period("2025-12"), {
    key: "2025-12",
    label: "December 2025",
    start: "2025-12-01",
    end: "2025-12-31",
  });
  equal(month_period("2025-13"), null);
  equal(month_period("nope"), null);
  const dates = [d("2025-11-03"), d("2025-12-31"), d("2025-11-20")];
  deepEqual(
    data_months(dates).map((p) => p.key),
    ["2025-12", "2025-11"],
  );
  deepEqual(
    data_years([...dates, d("2024-01-01")]).map((p) => p.key),
    ["2025", "2024"],
  );
  equal(resolve_period("2025-11", "", "", today).end, "2025-11-30");
  equal(resolve_period("2025", "", "", today).start, "2025-01-01");
  deepEqual(
    resolve_period("custom", "2025-01-05", "", today).start,
    "2025-01-05",
  );
  equal(resolve_period("this-year", "", "", today).end, "2026-12-31");
  equal(resolve_period("bogus", "", "", today).key, "all");
  equal(in_period(d("2025-11-30"), month("2025-11")), true);
  equal(in_period(d("2025-12-01"), month("2025-11")), false);
  equal(in_period(d("1999-01-01"), resolve_period("all", "", "", today)), true);
});

test("aging buckets", () => {
  deepEqual(
    aging(
      [
        { balance: 1, due: null, status: "open" },
        { balance: 2, due: d("2026-02-20"), status: "open" },
        { balance: 3, due: d("2026-02-01"), status: "overdue" },
        { balance: 4, due: d("2025-12-20"), status: "overdue" },
        { balance: 5, due: d("2025-11-20"), status: "overdue" },
        { balance: 6, due: d("2025-01-01"), status: "overdue" },
        { balance: 0, due: null, status: "paid" },
      ],
      today,
    ),
    [300, 300, 400, 500, 600],
  );
});

test("sort and csv", () => {
  const rows = [
    { a: "b", n: 2, d: null },
    { a: "a", n: 10, d: d("2025-01-01") },
    { a: "c", n: 2, d: d("2026-01-01") },
  ];
  deepEqual(
    sort_by(rows, (r) => r.n, true).map((r) => r.a),
    ["a", "b", "c"],
  );
  deepEqual(
    sort_by(rows, (r) => r.a, false).map((r) => r.a),
    ["a", "b", "c"],
  );
  deepEqual(
    sort_by(rows, (r) => r.d, true).map((r) => r.a),
    ["c", "a", "b"],
  );
  deepEqual(
    sort_by(rows, (r) => r.d, false).map((r) => r.a),
    ["a", "c", "b"],
  );
  equal(
    to_csv([
      ["a", 1],
      ['say "hi", ok', 2.5],
    ]),
    'a,1\n"say ""hi"", ok",2.5\n',
  );
});

test("1099-NEC threshold by year", () => {
  equal(nec_threshold(month("2025-12"), today), 600);
  equal(nec_threshold(resolve_period("2026", "", "", today), today), 2000);
  equal(
    nec_threshold(resolve_period("all", "", "", today), d("2025-06-01")),
    600,
  );
});
