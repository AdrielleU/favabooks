/**
 * qb-fork: file an import's source document away once it has been imported,
 * like QuickBooks (an uploaded statement doesn't stay in an inbox).
 *
 * Uses the same account and file name the Import page's "Move" button would
 * (the importer's suggestion, or what was typed in the file list).
 */
import { move_document } from "../../api/index.ts";
import { notify } from "../../notifications.ts";
import type { ProcessedImportableFile } from "../../reports/import/index.ts";
import { move_target } from "./move_target.ts";

/** Move the imported file into the documents folder (or say why not). */
export async function archive_imported_file(
  files: readonly ProcessedImportableFile[],
  filename: string,
  importer: string,
  file_accounts: ReadonlyMap<string, string>,
  file_names: ReadonlyMap<string, string>,
): Promise<boolean> {
  const target = move_target(
    files,
    filename,
    importer,
    file_accounts,
    file_names,
  );
  if (!target) {
    notify(
      "Imported. The file stays in the inbox: no account to file it under.",
      "warning",
    );
    return false;
  }
  return move_document(filename, target.account, target.new_name);
}
