/**
 * qb-fork: pure helpers for the report pages (no DOM imports, so they can
 * be unit tested).
 */
import type { QbNode } from "../api.ts";
import { iso } from "../docs/periods.ts";

/** A row of a statement table. */
export interface ReportRow {
  /**
   * "section" heading, "account", "group" (parent heading), "total", or a
   * computed "line" (gross profit, net income).
   */
  kind: "section" | "account" | "group" | "total" | "line";
  key: string;
  /** Account name for drill-down ("" for computed rows). */
  account: string;
  label: string;
  depth: number;
  /** Empty for headings without amounts. */
  amounts: number[];
  /** Parent accounts can collapse into one row. */
  collapsible: boolean;
  collapsed: boolean;
}

const has_amounts = (amounts: readonly number[]) =>
  amounts.some((n) => n !== 0);

/**
 * Rows for a section's account tree, QuickBooks style: a parent shows as a
 * heading, then its children, then "Total <parent>"; a collapsed parent is
 * one row with its total. Postings to a parent itself show as a child row.
 */
export function tree_rows(
  title: string,
  root: QbNode | null,
  collapsed: ReadonlySet<string>,
  section_amounts: number[],
): ReportRow[] {
  const rows: ReportRow[] = [];
  const row = (
    kind: ReportRow["kind"],
    node: QbNode,
    depth: number,
    label: string,
    amounts: number[],
  ): ReportRow => ({
    kind,
    key: `${kind}:${node.account || node.name}`,
    account: node.account,
    label,
    depth,
    amounts,
    collapsible: node.children.length > 0,
    collapsed: collapsed.has(node.account),
  });

  function walk(node: QbNode, depth: number) {
    if (node.children.length === 0) {
      rows.push(row("account", node, depth, node.name, node.amounts));
      return;
    }
    if (collapsed.has(node.account)) {
      rows.push(row("account", node, depth, node.name, node.amounts));
      return;
    }
    rows.push(row("group", node, depth, node.name, []));
    if (has_amounts(node.own)) {
      rows.push({
        ...row("account", node, depth + 1, `${node.name} (other)`, node.own),
        key: `own:${node.account}`,
        collapsible: false,
        collapsed: false,
      });
    }
    for (const child of node.children) {
      walk(child, depth + 1);
    }
    rows.push({
      ...row("total", node, depth, `Total ${node.name}`, node.amounts),
      collapsible: false,
    });
  }

  rows.push({
    kind: "section",
    key: `section:${title}`,
    account: root?.account ?? "",
    label: title,
    depth: 0,
    amounts: [],
    collapsible: false,
    collapsed: false,
  });
  if (root) {
    if (has_amounts(root.own)) {
      rows.push({
        ...row("account", root, 1, `${title} (other)`, root.own),
        key: `own:${root.account}`,
        collapsible: false,
        collapsed: false,
      });
    }
    for (const child of root.children) {
      walk(child, 1);
    }
  }
  rows.push({
    kind: "total",
    key: `total:${title}`,
    account: root?.account ?? "",
    label: `Total ${title.toLowerCase()}`,
    depth: 0,
    amounts: section_amounts,
    collapsible: false,
    collapsed: false,
  });
  return rows;
}

/** Every parent account in a tree (to collapse all). */
export function parents(node: QbNode | null): string[] {
  if (!node) {
    return [];
  }
  return node.children.flatMap((child) =>
    child.children.length ? [child.account, ...parents(child)] : [],
  );
}

/** Percent change from `previous` to `current`, or null. */
export function pct_change(current: number, previous: number): number | null {
  if (previous === 0) {
    return null;
  }
  return ((current - previous) / Math.abs(previous)) * 100;
}

/** "As of" choices for the balance sheet and trial balance. */
export function as_of_choices(
  today: Date,
  years: readonly number[],
): { key: string; label: string; date: string }[] {
  const y = today.getUTCFullYear();
  const m = today.getUTCMonth();
  const day = (yy: number, mm: number, dd: number) =>
    iso(new Date(Date.UTC(yy, mm, dd)));
  const q = Math.floor(m / 3) * 3;
  return [
    { key: "today", label: "Today", date: iso(today) },
    { key: "last-month", label: "End of last month", date: day(y, m, 0) },
    { key: "last-quarter", label: "End of last quarter", date: day(y, q, 0) },
    { key: "last-year", label: "End of last year", date: day(y, 0, 0) },
    ...years
      .filter((yy) => yy !== y - 1)
      .map((yy) => ({
        key: `end-${yy.toString()}`,
        label: `End of ${yy.toString()}`,
        date: `${yy.toString()}-12-31`,
      })),
  ];
}

/** "January 1 – December 31, 2025" (UTC dates). */
export function date_range_label(start: Date | null, end: Date): string {
  const long = (d: Date, year: boolean) =>
    d.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      ...(year ? { year: "numeric" } : {}),
      timeZone: "UTC",
    });
  if (start === null) {
    return `As of ${long(end, true)}`;
  }
  const same_year = start.getUTCFullYear() === end.getUTCFullYear();
  return `${long(start, !same_year)} – ${long(end, true)}`;
}

/** First days of months up to `today` in the given years (for pickers). */
export function months_of_years(years: readonly string[], today: Date): Date[] {
  return years.flatMap((year) =>
    Array.from(
      { length: 12 },
      (_, m) => new Date(Date.UTC(Number(year), m, 1)),
    ).filter((d) => d <= today),
  );
}

/** CSV rows (label with indentation, then amounts) for a statement. */
export function statement_rows(
  columns: readonly string[],
  sections: readonly ReportRow[][],
): (string | number)[][] {
  return [
    ["", ...columns],
    ...sections
      .flat()
      .map((row) => [
        `${"  ".repeat(row.depth)}${row.label}`,
        ...row.amounts.map((n) => n.toFixed(2)),
      ]),
  ];
}

/** A computed line (gross profit, net income) as a row. */
export function line_row(
  key: string,
  label: string,
  amounts: number[],
): ReportRow {
  return {
    kind: "line",
    key: `line:${key}`,
    account: "",
    label,
    depth: 0,
    amounts,
    collapsible: false,
    collapsed: false,
  };
}
