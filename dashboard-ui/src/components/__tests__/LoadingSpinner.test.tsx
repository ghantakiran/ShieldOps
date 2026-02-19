import { render } from "@testing-library/react";
import LoadingSpinner from "../LoadingSpinner";

describe("LoadingSpinner", () => {
  it("renders with default md size", () => {
    const { container } = render(<LoadingSpinner />);
    const spinner = container.querySelector(".animate-spin")!;
    expect(spinner.className).toContain("h-8");
    expect(spinner.className).toContain("w-8");
  });

  it("renders sm size", () => {
    const { container } = render(<LoadingSpinner size="sm" />);
    const spinner = container.querySelector(".animate-spin")!;
    expect(spinner.className).toContain("h-4");
    expect(spinner.className).toContain("w-4");
  });

  it("renders lg size", () => {
    const { container } = render(<LoadingSpinner size="lg" />);
    const spinner = container.querySelector(".animate-spin")!;
    expect(spinner.className).toContain("h-12");
    expect(spinner.className).toContain("w-12");
  });

  it("applies custom className", () => {
    const { container } = render(<LoadingSpinner className="mt-32" />);
    const wrapper = container.firstElementChild!;
    expect(wrapper.className).toContain("mt-32");
  });

  it("has animate-spin class", () => {
    const { container } = render(<LoadingSpinner />);
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("has flex centering on wrapper", () => {
    const { container } = render(<LoadingSpinner />);
    const wrapper = container.firstElementChild!;
    expect(wrapper.className).toContain("flex");
    expect(wrapper.className).toContain("items-center");
    expect(wrapper.className).toContain("justify-center");
  });
});
