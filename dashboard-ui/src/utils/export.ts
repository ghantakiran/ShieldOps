/**
 * Utilities for exporting dashboard data.
 */

/**
 * Convert an array of objects to a CSV string.
 */
export function toCSV<T extends Record<string, unknown>>(
  data: T[],
  columns?: { key: keyof T; label: string }[],
): string {
  if (data.length === 0) return "";

  const cols = columns ?? Object.keys(data[0]).map((k) => ({ key: k as keyof T, label: k as string }));

  const header = cols.map((c) => escapeCSV(c.label)).join(",");
  const rows = data.map((row) =>
    cols.map((c) => escapeCSV(String(row[c.key] ?? ""))).join(","),
  );

  return [header, ...rows].join("\n");
}

function escapeCSV(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

/**
 * Trigger a browser download of a string as a file.
 */
export function downloadFile(content: string, filename: string, mimeType = "text/csv"): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Export data as CSV file download.
 */
export function exportCSV<T extends Record<string, unknown>>(
  data: T[],
  filename: string,
  columns?: { key: keyof T; label: string }[],
): void {
  const csv = toCSV(data, columns);
  downloadFile(csv, filename.endsWith(".csv") ? filename : `${filename}.csv`);
}

/**
 * Export data as JSON file download.
 */
export function exportJSON<T>(data: T, filename: string): void {
  const json = JSON.stringify(data, null, 2);
  downloadFile(json, filename.endsWith(".json") ? filename : `${filename}.json`, "application/json");
}
