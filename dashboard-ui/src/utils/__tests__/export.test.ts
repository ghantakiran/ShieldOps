import { describe, it, expect } from "vitest";
import { toCSV } from "../export";

describe("toCSV", () => {
  it("returns empty string for empty data", () => {
    expect(toCSV([])).toBe("");
  });

  it("generates header and rows from objects", () => {
    const data = [
      { name: "Alice", score: 95 },
      { name: "Bob", score: 82 },
    ];
    const csv = toCSV(data);
    const lines = csv.split("\n");
    expect(lines[0]).toBe("name,score");
    expect(lines[1]).toBe("Alice,95");
    expect(lines[2]).toBe("Bob,82");
  });

  it("uses custom column labels", () => {
    const data = [{ id: "1", status: "active" }];
    const csv = toCSV(data, [
      { key: "id", label: "ID" },
      { key: "status", label: "Status" },
    ]);
    expect(csv.startsWith("ID,Status")).toBe(true);
  });

  it("escapes commas in values", () => {
    const data = [{ note: "hello, world" }];
    const csv = toCSV(data);
    expect(csv).toContain('"hello, world"');
  });

  it("escapes double quotes in values", () => {
    const data = [{ note: 'he said "hi"' }];
    const csv = toCSV(data);
    expect(csv).toContain('"he said ""hi"""');
  });

  it("handles undefined values gracefully", () => {
    const data = [{ name: "test", value: undefined as unknown }];
    const csv = toCSV(data as Record<string, unknown>[]);
    expect(csv).toContain("test,");
  });
});
