import { render, screen } from "@testing-library/react";
import MetricCard from "../MetricCard";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Total Investigations" value={42} />);
    expect(screen.getByText("Total Investigations")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders string values", () => {
    render(<MetricCard label="MTTR" value="5m 30s" />);
    expect(screen.getByText("5m 30s")).toBeInTheDocument();
  });

  it("shows green TrendingUp icon for positive change", () => {
    const { container } = render(<MetricCard label="Rate" value="80%" change={12.5} />);
    expect(screen.getByText("+12.5%")).toBeInTheDocument();
    const trendDiv = container.querySelector(".text-green-400");
    expect(trendDiv).toBeInTheDocument();
  });

  it("shows red TrendingDown icon for negative change", () => {
    const { container } = render(<MetricCard label="Errors" value={5} change={-8.3} />);
    expect(screen.getByText("-8.3%")).toBeInTheDocument();
    const trendDiv = container.querySelector(".text-red-400");
    expect(trendDiv).toBeInTheDocument();
  });

  it("shows neutral Minus icon for zero change", () => {
    const { container } = render(<MetricCard label="Flat" value={10} change={0} />);
    expect(screen.getByText("0.0%")).toBeInTheDocument();
    const trendDiv = container.querySelector(".text-gray-500");
    expect(trendDiv).toBeInTheDocument();
  });

  it("does not render trend section when no change prop", () => {
    const { container } = render(<MetricCard label="Simple" value={100} />);
    expect(container.querySelector(".text-green-400")).not.toBeInTheDocument();
    expect(container.querySelector(".text-red-400")).not.toBeInTheDocument();
    expect(container.querySelector(".text-gray-500")).not.toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    render(<MetricCard label="Test" value={1} icon={<span data-testid="icon">I</span>} />);
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });
});
