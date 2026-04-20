import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "../page";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const startMock = vi.fn();
vi.mock("@/lib/api/client", () => ({
  authApi: { start: (...args: unknown[]) => startMock(...args) },
}));

beforeEach(() => {
  pushMock.mockReset();
  startMock.mockReset();
});

describe("LoginPage (E01)", () => {
  it("renders email input and both buttons", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText(/adresse email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /recevoir mon lien/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /code otp/i })).toBeInTheDocument();
  });

  it("calls authApi.start with magic_link on submit", async () => {
    startMock.mockResolvedValue({ ok: true, method: "magic_link" });
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse email/i), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: /recevoir mon lien/i }));
    await waitFor(() => expect(startMock).toHaveBeenCalledWith("user@example.com"));
    expect(pushMock).toHaveBeenCalledWith("/magic-sent?email=user%40example.com");
  });

  it("shows error on API failure", async () => {
    startMock.mockRejectedValue(new Error("Network down"));
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse email/i), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: /recevoir mon lien/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/network down/i);
    });
  });

  it("switches to OTP route on secondary button", async () => {
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse email/i), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: /code otp/i }));
    expect(pushMock).toHaveBeenCalledWith("/otp?email=user%40example.com");
  });
});
