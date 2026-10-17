import { equal, match } from "node:assert/strict";
import { test } from "node:test";

import {
  copy_command,
  detect_os,
  parent_folder,
  steps,
} from "../src/qb/inbox/help.ts";

test("detect the viewer's operating system", () => {
  equal(detect_os("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"), "windows");
  equal(detect_os("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)"), "mac");
  equal(detect_os("Mozilla/5.0 (X11; Linux x86_64)"), "linux");
});

test("parent folder of the inbox", () => {
  equal(parent_folder("/home/me/books/inbox"), "/home/me/books");
  equal(parent_folder("C:\\Users\\me\\books\\inbox"), "C:\\Users\\me\\books");
  equal(parent_folder("books/inbox"), "books");
  equal(parent_folder("inbox"), "inbox");
});

test("steps with a known path paste it", () => {
  const [go, drop] = steps("mac", "/Users/me/books/inbox", "books/inbox");
  match(go ?? "", /Shift-Command-G/);
  match(drop ?? "", /hold Option/);
  match(steps("windows", "C:\\b\\inbox", "")[0] ?? "", /address bar/);
  match(steps("linux", "/b/inbox", "")[1] ?? "", /Shift to move/);
});

test("steps without a path go next to docker-compose.yml", () => {
  for (const os of ["windows", "mac", "linux"] as const) {
    match(
      steps(os, null, "books/second-llc/inbox")[0] ?? "",
      /docker-compose\.yml, then open books → second-llc → inbox\./,
    );
  }
});

test("terminal command to copy CSVs in", () => {
  equal(
    copy_command("windows", "C:\\b\\inbox"),
    'Copy-Item "$HOME\\Downloads\\*.csv" "C:\\b\\inbox"',
  );
  equal(copy_command("linux", "/b/inbox"), 'cp ~/Downloads/*.csv "/b/inbox/"');
});
