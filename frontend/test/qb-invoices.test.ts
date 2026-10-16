import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import {
  add_days,
  days_between,
  in_tab,
  status_label,
  summary,
} from "../src/qb/invoices/helpers.ts";

const d = (iso: string) => new Date(`${iso}T00:00:00Z`);

test("days between and add days", () => {
  equal(days_between(d("2026-03-01"), d("2026-03-31")), 30);
  equal(add_days("2026-02-20", 30), "2026-03-22");
  equal(add_days("nope", 30), "");
});

test("status labels and tabs", () => {
  equal(status_label("partial"), "Partially paid");
  equal(status_label("weird"), "weird");
  equal(in_tab("overdue", "unpaid"), true);
  equal(in_tab("paid", "unpaid"), false);
  equal(in_tab("paid", ""), true);
  equal(in_tab("open", "overdue"), false);
});

test("summary in cents", () => {
  const today = d("2026-03-31");
  deepEqual(
    summary(
      [
        { status: "overdue", balance: 10.1, amount: 20, date: d("2026-01-01") },
        { status: "open", balance: 5, amount: 5, date: d("2026-03-01") },
        { status: "partial", balance: 2.5, amount: 9, date: d("2026-03-01") },
        { status: "paid", balance: 0, amount: 100, date: d("2026-03-15") },
        { status: "paid", balance: 0, amount: 999, date: d("2026-01-15") },
      ],
      today,
    ),
    { overdue: 1010, not_due: 750, paid_30: 10000 },
  );
});
