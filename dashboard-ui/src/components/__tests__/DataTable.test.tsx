import { render, screen, fireEvent } from "@testing-library/react";
import DataTable, { type Column } from "../DataTable";

interface TestRow {
  id: string;
  name: string;
  value: number;
}

const columns: Column<TestRow>[] = [
  { key: "name", header: "Name", render: (row) => row.name },
  { key: "value", header: "Value", render: (row) => row.value },
];

const sampleData: TestRow[] = [
  { id: "1", name: "Alpha", value: 10 },
  { id: "2", name: "Beta", value: 20 },
];

describe("DataTable", () => {
  it("renders empty message when data is empty", () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        keyExtractor={(r) => r.id}
        emptyMessage="Nothing here"
      />,
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders default empty message", () => {
    render(
      <DataTable columns={columns} data={[]} keyExtractor={(r) => r.id} />,
    );
    expect(screen.getByText("No data available")).toBeInTheDocument();
  });

  it("renders correct headers from columns", () => {
    render(
      <DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} />,
    );
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
  });

  it("renders rows using render functions", () => {
    render(
      <DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} />,
    );
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("fires onRowClick when a row is clicked", () => {
    const onClick = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={sampleData}
        keyExtractor={(r) => r.id}
        onRowClick={onClick}
      />,
    );
    fireEvent.click(screen.getByText("Alpha"));
    expect(onClick).toHaveBeenCalledWith(sampleData[0]);
  });

  it("adds cursor-pointer class when onRowClick is provided", () => {
    const { container } = render(
      <DataTable
        columns={columns}
        data={sampleData}
        keyExtractor={(r) => r.id}
        onRowClick={() => {}}
      />,
    );
    const rows = container.querySelectorAll("tbody tr");
    expect(rows[0].className).toContain("cursor-pointer");
  });

  it("does not add cursor-pointer when no onRowClick", () => {
    const { container } = render(
      <DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} />,
    );
    const rows = container.querySelectorAll("tbody tr");
    expect(rows[0].className).not.toContain("cursor-pointer");
  });
});
