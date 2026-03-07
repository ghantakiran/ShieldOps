import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProductLanding from "../ProductLanding";

// Mock framer-motion to avoid animation complexities in tests
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

function renderWithProduct(productId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/products/${productId}`]}>
        <Routes>
          <Route path="/products/:productId" element={<ProductLanding />} />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ProductLanding", () => {
  it("renders SRE product landing page", () => {
    renderWithProduct("sre");
    expect(screen.getByText("SRE Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Autonomous incident response")).toBeInTheDocument();
    expect(screen.getByText("Everything you need")).toBeInTheDocument();
  });

  it("renders SOC product landing page", () => {
    renderWithProduct("soc");
    expect(screen.getByText("Security Operations")).toBeInTheDocument();
    expect(screen.getByText("AI-powered threat defense")).toBeInTheDocument();
  });

  it("renders FinOps product landing page", () => {
    renderWithProduct("finops");
    expect(screen.getByText("FinOps Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Cloud cost optimization")).toBeInTheDocument();
  });

  it("renders Compliance product landing page", () => {
    renderWithProduct("compliance");
    expect(screen.getByText("Compliance Automation")).toBeInTheDocument();
    expect(screen.getByText("Continuous compliance assurance")).toBeInTheDocument();
  });

  it("redirects to home for invalid product ID", () => {
    renderWithProduct("invalid");
    expect(screen.getByText("Home")).toBeInTheDocument();
  });

  it("shows metrics section for SRE product", () => {
    renderWithProduct("sre");
    expect(screen.getByText("73%")).toBeInTheDocument();
    expect(screen.getByText("MTTR Reduction")).toBeInTheDocument();
  });

  it("shows features grid for SRE product", () => {
    renderWithProduct("sre");
    expect(screen.getByText("Fleet Overview")).toBeInTheDocument();
    expect(screen.getByText("AI Investigation")).toBeInTheDocument();
    expect(screen.getByText("Auto-Remediation")).toBeInTheDocument();
  });

  it("shows integrations for SRE product", () => {
    renderWithProduct("sre");
    expect(screen.getByText("AWS")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("shows CTA with product name", () => {
    renderWithProduct("sre");
    const ctaButtons = screen.getAllByText(/Try SRE Intelligence Demo/);
    expect(ctaButtons.length).toBeGreaterThan(0);
  });
});
