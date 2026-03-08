import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import Breadcrumbs from "../Breadcrumbs";

function renderAtPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Breadcrumbs />
    </MemoryRouter>,
  );
}

describe("Breadcrumbs", () => {
  it("does not render on /app root", () => {
    renderAtPath("/app");
    expect(screen.queryByLabelText("Breadcrumb")).not.toBeInTheDocument();
  });

  it("renders breadcrumbs for /app/investigations", () => {
    renderAtPath("/app/investigations");
    expect(screen.getByLabelText("Breadcrumb")).toBeInTheDocument();
    expect(screen.getByText("Investigations")).toBeInTheDocument();
  });

  it("renders multi-level breadcrumbs", () => {
    renderAtPath("/app/playbooks/editor");
    expect(screen.getByText("Playbooks")).toBeInTheDocument();
    expect(screen.getByText("Editor")).toBeInTheDocument();
  });

  it("truncates UUID-like segments", () => {
    renderAtPath("/app/investigations/a1b2c3d4-e5f6-7890-abcd-ef1234567890");
    expect(screen.getByText("a1b2c3d4...")).toBeInTheDocument();
  });

  it("converts kebab-case to title case", () => {
    renderAtPath("/app/system-health");
    expect(screen.getByText("System Health")).toBeInTheDocument();
  });
});
