import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "../Sidebar";
import { useSidebarStore } from "../../store/sidebar";

function renderSidebar(initialPath = "/app") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    // Reset sidebar store
    useSidebarStore.setState({
      collapsed: false,
      expandedGroups: new Set(["sre", "security", "finops", "compliance", "platform"]),
    });
    localStorage.clear();
  });

  it("renders the ShieldOps logo", () => {
    renderSidebar();
    expect(screen.getByText("ShieldOps")).toBeInTheDocument();
  });

  it("renders all nav group labels", () => {
    renderSidebar();
    expect(screen.getByText("SRE Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Security Operations")).toBeInTheDocument();
    expect(screen.getByText("FinOps Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Compliance & Audit")).toBeInTheDocument();
    expect(screen.getByText("Platform")).toBeInTheDocument();
  });

  it("renders nav items within groups", () => {
    renderSidebar();
    expect(screen.getByText("Fleet Overview")).toBeInTheDocument();
    expect(screen.getByText("Investigations")).toBeInTheDocument();
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.getByText("Cost")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("collapses a group when header is clicked", () => {
    renderSidebar();

    // Fleet Overview should be visible
    expect(screen.getByText("Fleet Overview")).toBeInTheDocument();

    // Click the SRE Intelligence group header to collapse it
    fireEvent.click(screen.getByText("SRE Intelligence"));

    // After collapse, items should be removed from the DOM
    expect(screen.queryByText("Fleet Overview")).not.toBeInTheDocument();
  });

  it("toggles sidebar collapsed state", () => {
    renderSidebar();

    // Find the collapse toggle button
    const collapseButton = screen.getByTitle("Collapse sidebar");
    fireEvent.click(collapseButton);

    // Logo text should be hidden in collapsed mode
    expect(screen.queryByText("ShieldOps")).not.toBeInTheDocument();
  });

  it("highlights active group based on current path", () => {
    renderSidebar("/app/security");
    // The Security Operations group header should have an active style
    const groupHeader = screen.getByText("Security Operations");
    expect(groupHeader.closest("button")).toHaveClass("text-red-400");
  });
});
