/** qb-fork: save text as a file in the browser. */
export function download_csv(csv: string, filename: string): void {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}
