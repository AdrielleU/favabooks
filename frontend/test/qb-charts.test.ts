import { deepEqual, equal } from "node:assert/strict";
import { test } from "node:test";

import type { QbNode, QbStatement } from "../src/qb/api.ts";
import {
  kpis,
  pnl_trend,
  top_slices,
  trend_by,
} from "../src/qb/charts/data.ts";

const d = (iso: string) => new Date(`${iso}T00:00:00Z`);
const leaf = (name: string, amounts: number[]): QbNode => ({
  account: `Expenses:${name}`,
  name,
  amounts,
  children: [],
  own: amounts,
});

const statement: QbStatement = {
  title: "Profit and loss",
  company: "Co",
  currency: "USD",
  columns: [
    { label: "Jan 2025", start: d("2025-01-01"), end: d("2025-01-31") },
    { label: "Feb 2025", start: d("2025-02-01"), end: d("2025-02-28") },
    { label: "Total", start: d("2025-01-01"), end: d("2025-02-28") },
  ],
  blocks: [
    {
      kind: "section",
      key: "income",
      title: "Income",
      amounts: [100, 50, 150],
      node: null,
    },
    {
      kind: "section",
      key: "cogs",
      title: "Cost of goods sold",
      amounts: [10, 0, 10],
      node: null,
    },
    {
      kind: "section",
      key: "expenses",
      title: "Expenses",
      amounts: [30, 20, 50],
      node: {
        account: "Expenses",
        name: "Expenses",
        amounts: [30, 20, 50],
        own: [0, 0, 0],
        children: [
          leaf("A", [10, 10, 20]),
          leaf("B", [20, 10, 30]),
          leaf("C", [0, 0, 0]),
        ],
      },
    },
    {
      kind: "line",
      key: "net",
      title: "Net income",
      amounts: [60, 30, 90],
      node: null,
    },
  ],
  unconverted: [],
};

test("trend and kpis", () => {
  deepEqual(
    pnl_trend(statement).map((p) => [p.label, p.income, p.expenses, p.net]),
    [
      ["Jan 2025", 100, 40, 60],
      ["Feb 2025", 50, 20, 30],
    ],
  );
  deepEqual(kpis(statement, 2), {
    income: 150,
    expenses: 60,
    net: 90,
    margin: 60,
  });
  equal(kpis({ ...statement, blocks: [] }, 0).margin, null);
  const single = { ...statement, columns: statement.columns.slice(2) };
  equal(pnl_trend(single).length, 1);
});

test("slices", () => {
  const node = statement.blocks.find((b) => b.key === "expenses")?.node ?? null;
  deepEqual(
    top_slices(node, 2).map((s) => [s.label, s.value]),
    [
      ["B", 30],
      ["A", 20],
    ],
  );
  deepEqual(
    top_slices(node, 2, 1).map((s) => [s.label, s.value]),
    [["Other (2)", 50]],
  );
  deepEqual(top_slices(null, 0), []);
});

test("trend breakdown", () => {
  equal(trend_by(d("2025-01-01"), d("2025-12-31")), "month");
  equal(trend_by(d("2022-01-01"), d("2025-12-31")), "quarter");
  equal(trend_by(d("2010-01-01"), d("2025-12-31")), "year");
});
