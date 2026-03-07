import { render, screen, fireEvent, act } from "@testing-library/react";
import ToastContainer from "../ToastContainer";
import { useToastStore } from "../../store/toast";

describe("ToastContainer", () => {
  beforeEach(() => {
    // Reset store
    useToastStore.setState({ toasts: [] });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when no toasts", () => {
    const { container } = render(<ToastContainer />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a success toast", () => {
    act(() => {
      useToastStore.getState().addToast("success", "Saved successfully");
    });

    render(<ToastContainer />);
    expect(screen.getByText("Saved successfully")).toBeInTheDocument();
  });

  it("renders an error toast", () => {
    act(() => {
      useToastStore.getState().addToast("error", "Something failed");
    });

    render(<ToastContainer />);
    expect(screen.getByText("Something failed")).toBeInTheDocument();
  });

  it("removes toast when dismiss button is clicked", () => {
    act(() => {
      useToastStore.getState().addToast("info", "Dismiss me");
    });

    render(<ToastContainer />);
    expect(screen.getByText("Dismiss me")).toBeInTheDocument();

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);

    expect(screen.queryByText("Dismiss me")).not.toBeInTheDocument();
  });

  it("auto-dismisses after 5 seconds", () => {
    act(() => {
      useToastStore.getState().addToast("warning", "Auto dismiss");
    });

    const { rerender } = render(<ToastContainer />);
    expect(screen.getByText("Auto dismiss")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    rerender(<ToastContainer />);
    expect(screen.queryByText("Auto dismiss")).not.toBeInTheDocument();
  });

  it("renders multiple toasts", () => {
    act(() => {
      useToastStore.getState().addToast("success", "Toast 1");
      useToastStore.getState().addToast("error", "Toast 2");
    });

    render(<ToastContainer />);
    expect(screen.getByText("Toast 1")).toBeInTheDocument();
    expect(screen.getByText("Toast 2")).toBeInTheDocument();
  });
});
