import clsx from "clsx";
import { useMediaQuery } from "../hooks/useMediaQuery";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  keyExtractor: (row: T) => string;
  emptyMessage?: string;
}

export default function DataTable<T>({
  columns,
  data,
  onRowClick,
  keyExtractor,
  emptyMessage = "No data available",
}: DataTableProps<T>) {
  const isMobile = useMediaQuery("(max-width: 767px)");

  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center">
        <p className="text-sm text-gray-500">{emptyMessage}</p>
      </div>
    );
  }

  // Mobile: stacked cards
  if (isMobile) {
    return (
      <div className="space-y-3">
        {data.map((row) => (
          <div
            key={keyExtractor(row)}
            onClick={() => onRowClick?.(row)}
            className={clsx(
              "rounded-xl border border-gray-800 bg-gray-900 p-4",
              onRowClick && "cursor-pointer hover:border-gray-700",
            )}
          >
            {columns.map((col) => (
              <div key={col.key} className="flex items-baseline justify-between py-1.5">
                <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
                  {col.header}
                </span>
                <span className={clsx("text-sm text-gray-200", col.className)}>
                  {col.render(row)}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  }

  // Desktop: standard table
  return (
    <div className="overflow-hidden rounded-xl border border-gray-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 bg-gray-900">
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(
                  "px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500",
                  col.className,
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800 bg-gray-950">
          {data.map((row) => (
            <tr
              key={keyExtractor(row)}
              onClick={() => onRowClick?.(row)}
              className={clsx(
                "transition-colors",
                onRowClick && "cursor-pointer hover:bg-gray-900",
              )}
            >
              {columns.map((col) => (
                <td key={col.key} className={clsx("px-4 py-3", col.className)}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
