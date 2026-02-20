import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import Analytics from "../Analytics";

function setupFetchMock() {
  globalThis.fetch = vi.fn((url: string | URL | Request) => {
    const urlStr = typeof url === "string" ? url : url.toString();

    if (urlStr.includes("/analytics/summary")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            total_investigations: 10,
            total_remediations: 5,
            auto_resolved_percent: 80,
            mean_time_to_resolve_seconds: 120,
            investigations_by_status: {},
            remediations_by_status: {},
          }),
      } as Response);
    }

    if (urlStr.includes("/agents/")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      } as Response);
    }

    // Default: return empty for trend/rate/accuracy endpoints
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    } as Response);
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("Analytics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders page title", async () => {
    setupFetchMock();
    renderWithProviders(<Analytics />);
    expect(
      await screen.findByText("Analytics"),
    ).toBeInTheDocument();
  });
});
