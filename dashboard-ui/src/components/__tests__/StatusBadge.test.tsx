import { render, screen } from "@testing-library/react";
import StatusBadge from "../StatusBadge";

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="healthy" />);
    expect(screen.getByText("healthy")).toBeInTheDocument();
  });

  it("maps 'healthy' to success variant (green)", () => {
    const { container } = render(<StatusBadge status="healthy" />);
    const badge = container.querySelector("span")!;
    expect(badge.className).toContain("text-green-400");
  });

  it("maps 'critical' to error variant (red)", () => {
    const { container } = render(<StatusBadge status="critical" />);
    const badge = container.querySelector("span")!;
    expect(badge.className).toContain("text-red-400");
  });

  it("maps 'in_progress' to warning variant (yellow)", () => {
    const { container } = render(<StatusBadge status="in_progress" />);
    const badge = container.querySelector("span")!;
    expect(badge.className).toContain("text-yellow-400");
  });

  it("formats underscore statuses to spaces", () => {
    render(<StatusBadge status="in_progress" />);
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });

  it("formats pending_approval with spaces", () => {
    render(<StatusBadge status="pending_approval" />);
    expect(screen.getByText("pending approval")).toBeInTheDocument();
  });

  it("uses explicit variant prop over auto-mapping", () => {
    const { container } = render(<StatusBadge status="healthy" variant="error" />);
    const badge = container.querySelector("span")!;
    expect(badge.className).toContain("text-red-400");
  });

  it("falls back to neutral for unknown statuses", () => {
    const { container } = render(<StatusBadge status="unknown_xyz" />);
    const badge = container.querySelector("span")!;
    expect(badge.className).toContain("text-gray-400");
  });

  it("has ring-1 ring-inset styling", () => {
    const { container } = render(<StatusBadge status="idle" />);
    const badge = container.querySelector("span")!;
    expect(badge.className).toContain("ring-1");
    expect(badge.className).toContain("ring-inset");
  });
});
