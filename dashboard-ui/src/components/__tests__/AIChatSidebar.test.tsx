import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AIChatSidebar from "../AIChatSidebar";

function renderChat() {
  return render(
    <MemoryRouter>
      <AIChatSidebar />
    </MemoryRouter>,
  );
}

describe("AIChatSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the FAB button", () => {
    renderChat();
    expect(screen.getByLabelText("Open AI assistant")).toBeInTheDocument();
  });

  it("opens chat panel when FAB is clicked", () => {
    renderChat();
    fireEvent.click(screen.getByLabelText("Open AI assistant"));
    expect(screen.getByText("ShieldOps AI")).toBeInTheDocument();
    expect(screen.getByText("How can I help?")).toBeInTheDocument();
  });

  it("shows suggested prompts in empty state", () => {
    renderChat();
    fireEvent.click(screen.getByLabelText("Open AI assistant"));
    expect(
      screen.getByText("What's my current security posture?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Summarize recent incidents"),
    ).toBeInTheDocument();
  });

  it("has a textarea for input", () => {
    renderChat();
    fireEvent.click(screen.getByLabelText("Open AI assistant"));
    expect(screen.getByPlaceholderText("Ask anything...")).toBeInTheDocument();
  });
});
