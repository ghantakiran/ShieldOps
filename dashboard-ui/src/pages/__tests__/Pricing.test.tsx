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
    expect(screen.getByText("API Platform")).toBeInTheDocument();
    expect(screen.getByText("Agent Marketplace")).toBeInTheDocument();
  });

  it("renders tier names for each product", () => {
    renderPricing();
    // 6 products now — 4 have Starter, API has Developer, Marketplace has Free
    const enterprises = screen.getAllByText("Enterprise");
    expect(enterprises.length).toBe(6);
  });

  it("shows annual pricing by default", () => {
    renderPricing();
    // SRE Starter annual = $399 (may appear in multiple products)
    const prices = screen.getAllByText("$399");
    expect(prices.length).toBeGreaterThanOrEqual(1);
  });

  it("toggles to monthly pricing", () => {
    renderPricing();
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);

    // SRE Starter monthly = $499 (may appear in multiple products)
    const prices = screen.getAllByText("$499");
    expect(prices.length).toBeGreaterThanOrEqual(1);
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

  it("shows Most Popular badge on highlighted tiers", () => {
    renderPricing();
    const badges = screen.getAllByText("Most Popular");
    expect(badges.length).toBe(6); // One per product
  });

  it("shows Custom for enterprise pricing", () => {
    renderPricing();
    const customs = screen.getAllByText("Custom");
    expect(customs.length).toBe(6);
  });
});
