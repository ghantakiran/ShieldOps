import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import Login from "../Login";

// Mock navigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

// Mock auth store
const mockSetAuth = vi.fn();
vi.mock("../../store/auth", () => ({
  useAuthStore: () => ({ setAuth: mockSetAuth }),
}));

// Mock API client
const mockPost = vi.fn();
const mockGet = vi.fn();
vi.mock("../../api/client", () => ({
  post: (...args: unknown[]) => mockPost(...args),
  get: (...args: unknown[]) => mockGet(...args),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  },
}));

function renderLogin() {
  return render(
    <BrowserRouter>
      <Login />
    </BrowserRouter>,
  );
}

describe("Login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders email and password inputs", () => {
    renderLogin();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("renders submit button", () => {
    renderLogin();
    expect(screen.getByRole("button", { name: "Sign In" })).toBeInTheDocument();
  });

  it("renders ShieldOps branding", () => {
    renderLogin();
    expect(screen.getByText("ShieldOps")).toBeInTheDocument();
    expect(screen.getByText("Autonomous SRE Platform")).toBeInTheDocument();
  });

  it("calls setAuth and navigates on successful login", async () => {
    const user = userEvent.setup();
    mockPost.mockResolvedValueOnce({ access_token: "tok-123", token_type: "bearer" });
    mockGet.mockResolvedValueOnce({
      id: "u1",
      email: "admin@test.com",
      name: "Admin",
      role: "admin",
      is_active: true,
    });

    renderLogin();

    await user.type(screen.getByLabelText("Email"), "admin@test.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(mockSetAuth).toHaveBeenCalledWith("tok-123", expect.objectContaining({ email: "admin@test.com" }));
    });
    expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
  });

  it("shows error message on failed login", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("../../api/client");
    mockPost.mockRejectedValueOnce(new ApiError(401, "Invalid credentials"));

    renderLogin();

    await user.type(screen.getByLabelText("Email"), "bad@test.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
    expect(mockSetAuth).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("shows generic error for unexpected errors", async () => {
    const user = userEvent.setup();
    mockPost.mockRejectedValueOnce(new Error("Network error"));

    renderLogin();

    await user.type(screen.getByLabelText("Email"), "test@test.com");
    await user.type(screen.getByLabelText("Password"), "pass");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    await waitFor(() => {
      expect(screen.getByText("An unexpected error occurred. Please try again.")).toBeInTheDocument();
    });
  });

  it("shows loading state while submitting", async () => {
    const user = userEvent.setup();
    let resolvePost: (value: unknown) => void;
    mockPost.mockReturnValueOnce(new Promise((r) => { resolvePost = r; }));

    renderLogin();

    await user.type(screen.getByLabelText("Email"), "test@test.com");
    await user.type(screen.getByLabelText("Password"), "pass");
    await user.click(screen.getByRole("button", { name: "Sign In" }));

    expect(screen.getByText("Signing in...")).toBeInTheDocument();

    // Resolve to clean up
    resolvePost!({ access_token: "tok", token_type: "bearer" });
    mockGet.mockResolvedValueOnce({ id: "u1", email: "t@t.com", name: "T", role: "viewer", is_active: true });
  });
});
