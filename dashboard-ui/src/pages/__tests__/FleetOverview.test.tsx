import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FleetOverview from "../FleetOverview";

// Mock navigate
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => vi.fn() };
});

// Mock fetch globally
const mockFetchResponses: Record<string, unknown> = {};

function setupFetchMock(responses: Record<string, unknown>) {
  Object.assign(mockFetchResponses, responses);
  globalThis.fetch = vi.fn((url: string | URL | Request) => {
    const urlStr = typeof url === "string" ? url : url.toString();
    for (const [path, data] of Object.entries(mockFetchResponses)) {
      if (urlStr.includes(path)) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(data),
        } as Response);
      }
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    } as Response);
  });
}

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <FleetOverview />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("FleetOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading spinner initially", () => {
    // Never resolve fetch to keep loading state
    globalThis.fetch = vi.fn(() => new Promise<Response>(() => {}));

    const { container } = renderWithProviders();
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("renders metric cards and agent health grid when data loads", async () => {
    setupFetchMock({
      "/analytics/summary": {
        total_investigations: 42,
        total_remediations: 18,
        auto_resolved_percent: 78.5,
        mean_time_to_resolve_seconds: 320,
        investigations_by_status: {},
        remediations_by_status: {},
      },
      "/agents/": [
        {
          id: "a1",
          agent_type: "investigation",
          environment: "production",
          status: "running",
          last_heartbeat: "2026-02-19T00:00:00Z",
          registered_at: "2026-01-01T00:00:00Z",
        },
      ],
      "/investigations/": [
        {
          id: "inv-1",
          alert_id: "alert-1",
          alert_name: "High CPU",
          severity: "high",
          resource_id: "pod-1",
          status: "completed",
          root_cause: null,
          confidence: null,
          started_at: "2026-02-19T00:00:00Z",
          completed_at: null,
          duration_seconds: null,
        },
      ],
      "/remediations/": [],
    });

    renderWithProviders();

    // Wait for data to load
    expect(await screen.findByText("Fleet Overview")).toBeInTheDocument();
    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("Total Investigations")).toBeInTheDocument();
    expect(screen.getByText("Agent Health")).toBeInTheDocument();
    expect(screen.getByText("Recent Investigations")).toBeInTheDocument();
    expect(screen.getByText("Recent Remediations")).toBeInTheDocument();
  });

  it("renders investigation data in the table", async () => {
    setupFetchMock({
      "/analytics/summary": {
        total_investigations: 1,
        total_remediations: 0,
        auto_resolved_percent: 100,
        mean_time_to_resolve_seconds: 60,
        investigations_by_status: {},
        remediations_by_status: {},
      },
      "/agents/": [],
      "/investigations/": [
        {
          id: "inv-1",
          alert_id: "alert-1",
          alert_name: "Memory Leak Detected",
          severity: "critical",
          resource_id: "svc-api",
          status: "in_progress",
          root_cause: null,
          confidence: null,
          started_at: "2026-02-19T10:00:00Z",
          completed_at: null,
          duration_seconds: null,
        },
      ],
      "/remediations/": [],
    });

    renderWithProviders();

    expect(await screen.findByText("Memory Leak Detected")).toBeInTheDocument();
    expect(screen.getByText("svc-api")).toBeInTheDocument();
  });

  it("shows empty messages when no investigations or remediations", async () => {
    setupFetchMock({
      "/analytics/summary": {
        total_investigations: 0,
        total_remediations: 0,
        auto_resolved_percent: 0,
        mean_time_to_resolve_seconds: 0,
        investigations_by_status: {},
        remediations_by_status: {},
      },
      "/agents/": [],
      "/investigations/": [],
      "/remediations/": [],
    });

    renderWithProviders();

    expect(await screen.findByText("No recent investigations")).toBeInTheDocument();
    expect(screen.getByText("No recent remediations")).toBeInTheDocument();
  });

  it("shows all agent type labels in health grid", async () => {
    setupFetchMock({
      "/analytics/summary": {
        total_investigations: 0,
        total_remediations: 0,
        auto_resolved_percent: 0,
        mean_time_to_resolve_seconds: 0,
        investigations_by_status: {},
        remediations_by_status: {},
      },
      "/agents/": [],
      "/investigations/": [],
      "/remediations/": [],
    });

    renderWithProviders();

    expect(await screen.findByText("Investigation")).toBeInTheDocument();
    expect(screen.getByText("Remediation")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByText("Cost")).toBeInTheDocument();
    expect(screen.getByText("Learning")).toBeInTheDocument();
    expect(screen.getByText("Supervisor")).toBeInTheDocument();
  });
});
