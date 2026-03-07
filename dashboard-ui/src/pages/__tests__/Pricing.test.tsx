import { render, screen, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Pricing from "../Pricing";

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({
      children,
      ...props
    }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  useInView: () => true,
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

function renderPricing() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Pricing />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("Pricing", () => {
  it("renders pricing header", () => {
    renderPricing();
    expect(screen.getByText("Simple, transparent pricing")).toBeInTheDocument();
  });

  it("renders all product pricing sections", () => {
    renderPricing();
    expect(screen.getByText("SRE Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Security Operations")).toBeInTheDocument();
    expect(screen.getByText("FinOps Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Compliance Automation")).toBeInTheDocument();
  });

  it("renders tier names for each product", () => {
    renderPricing();
    // Each product has Starter, Pro, Enterprise — so these should appear multiple times
    const starters = screen.getAllByText("Starter");
    const pros = screen.getAllByText("Pro");
    const enterprises = screen.getAllByText("Enterprise");
    expect(starters.length).toBe(4);
    expect(pros.length).toBe(4);
    expect(enterprises.length).toBe(4);
  });

  it("shows annual pricing by default", () => {
    renderPricing();
    // SRE Starter annual = $399
    expect(screen.getByText("$399")).toBeInTheDocument();
  });

  it("toggles to monthly pricing", () => {
    renderPricing();
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);

    // SRE Starter monthly = $499
    expect(screen.getByText("$499")).toBeInTheDocument();
  });

  it("renders FAQ section", () => {
    renderPricing();
    expect(screen.getByText("Frequently asked questions")).toBeInTheDocument();
    expect(screen.getByText("Can I try ShieldOps for free?")).toBeInTheDocument();
  });

  it("expands FAQ answer on click", () => {
    renderPricing();
    fireEvent.click(screen.getByText("Can I try ShieldOps for free?"));
    expect(screen.getByText(/14-day free trial/)).toBeInTheDocument();
  });

  it("shows Most Popular badge on Pro tiers", () => {
    renderPricing();
    const badges = screen.getAllByText("Most Popular");
    expect(badges.length).toBe(4); // One per product
  });

  it("shows Custom for enterprise pricing", () => {
    renderPricing();
    const customs = screen.getAllByText("Custom");
    expect(customs.length).toBe(4);
  });
});
