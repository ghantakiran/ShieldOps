import { useState, useRef, useEffect } from "react";
import { Download, FileSpreadsheet, FileJson } from "lucide-react";
import clsx from "clsx";
import { exportCSV, exportJSON } from "../utils/export";

interface ExportButtonProps<T extends Record<string, unknown>> {
  data: T[];
  filename: string;
  columns?: { key: keyof T; label: string }[];
  className?: string;
}

export default function ExportButton<T extends Record<string, unknown>>({
  data,
  filename,
  columns,
  className,
}: ExportButtonProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  return (
    <div ref={ref} className={clsx("relative", className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={data.length === 0}
        className="flex items-center gap-1.5 rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Download className="h-4 w-4" />
        Export
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-20 mt-1 w-40 overflow-hidden rounded-lg border border-gray-700 bg-gray-900 shadow-xl">
          <button
            onClick={() => {
              exportCSV(data, filename, columns);
              setIsOpen(false);
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-800"
          >
            <FileSpreadsheet className="h-4 w-4 text-green-400" />
            Export CSV
          </button>
          <button
            onClick={() => {
              exportJSON(data, filename);
              setIsOpen(false);
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-800"
          >
            <FileJson className="h-4 w-4 text-blue-400" />
            Export JSON
          </button>
        </div>
      )}
    </div>
  );
}
