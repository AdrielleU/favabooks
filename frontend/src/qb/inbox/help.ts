/**
 * qb-fork: the "Add your files" popup's directions (no DOM, so it can be
 * unit tested).
 */
import { writable } from "svelte/store";

/** Set to open the popup (the "+ New" menu does). */
export const inbox_help_open = writable(false);

export type Os = "windows" | "mac" | "linux";

export const OS_NAMES: Record<Os, string> = {
  windows: "Windows",
  mac: "Mac",
  linux: "Linux",
};

/** The viewer's operating system, from the browser's user agent. */
export function detect_os(user_agent: string): Os {
  if (/Windows/i.test(user_agent)) {
    return "windows";
  }
  if (/Mac OS|Macintosh|iPhone|iPad/i.test(user_agent)) {
    return "mac";
  }
  return "linux";
}

/** The folder a path is in ("/a/books/inbox" → "/a/books"). */
export function parent_folder(path: string): string {
  const cut = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return cut > 0 ? path.slice(0, cut) : path;
}

/**
 * Steps to put files in the inbox. `path` is the inbox as the computer
 * sees it, or null when unknown (Docker), when `relative` (like
 * "books/inbox") says where it is next to docker-compose.yml.
 */
export function steps(os: Os, path: string | null, relative: string): string[] {
  const parts = relative.split("/").join(" → ");
  const go = {
    windows:
      path === null
        ? `Press Windows key + E to open File Explorer, go to the folder where you saved docker-compose.yml, then open ${parts}.`
        : "Press Windows key + E to open File Explorer. Click the address bar at the top, paste the folder path and press Enter.",
    mac:
      path === null
        ? `Open Finder, go to the folder where you saved docker-compose.yml, then open ${parts}.`
        : "Open Finder and press Shift-Command-G (Go to Folder). Paste the folder path and press Return.",
    linux:
      path === null
        ? `Open your file manager (Files), go to the folder where you saved docker-compose.yml, then open ${parts}.`
        : "Open your file manager (Files) and press Ctrl+L. Paste the folder path and press Enter.",
  }[os];
  const drop = {
    windows:
      "Drag your files (from Downloads, say) into that window. Dragging moves files on the same drive; hold Ctrl while you drop to copy them instead. Or copy them with Ctrl+C and paste with Ctrl+V.",
    mac: "Drag your files (from Downloads, say) into that window. Dragging moves files on the same disk; hold Option while you drop to copy them instead. Or copy them with Command-C and paste with Command-V.",
    linux:
      "Drag your files (from Downloads, say) into that window. Hold Ctrl while you drop to copy them, or Shift to move them. Or copy them with Ctrl+C and paste with Ctrl+V.",
  }[os];
  return [go, drop];
}

/** The terminal (PowerShell on Windows) command that copies CSVs in. */
export function copy_command(os: Os, path: string): string {
  return os === "windows"
    ? `Copy-Item "$HOME\\Downloads\\*.csv" "${path}"`
    : `cp ~/Downloads/*.csv "${path}/"`;
}
