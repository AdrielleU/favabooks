/**
 * qb-fork: where an imported file is filed (no DOM or router imports, so it
 * can be unit tested).
 */
import type { ProcessedImportableFile } from "../../reports/import/index.ts";

/** Account and new name for a file+importer, or null if there is none. */
export function move_target(
  files: readonly ProcessedImportableFile[],
  filename: string,
  importer: string,
  file_accounts: ReadonlyMap<string, string>,
  file_names: ReadonlyMap<string, string>,
): { account: string; new_name: string } | null {
  const file = files.find((f) => f.name === filename);
  const info = file?.importers.find(
    (i) => (i.importer_name ?? "") === importer,
  );
  if (!info) {
    return null;
  }
  const key = `${filename}:${importer}`;
  const account = file_accounts.get(key) ?? info.account;
  const new_name = file_names.get(key) ?? info.new_name;
  return account && new_name ? { account, new_name } : null;
}
