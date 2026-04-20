import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OtpContent from "../OtpContent";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams("email=user@example.com"),
}));

const verifyMock = vi.fn();
vi.mock("@/lib/api/client", () => ({
  authApi: { verify: (...args: unknown[]) => verifyMock(...args) },
}));

beforeEach(() => {
  pushMock.mockReset();
  verifyMock.mockReset();
});

describe("OtpContent (E03)", () => {
  it("renders 6 OTP inputs", () => {
    render(<OtpContent />);
    expect(screen.getAllByRole("textbox")).toHaveLength(6);
  });

  it("submits when 6 digits entered", async () => {
    verifyMock.mockResolvedValue({ ok: true, redirect_to: "/portal" });
    render(<OtpContent />);
    const inputs = screen.getAllByRole("textbox");
    for (let i = 0; i < 6; i++) {
      await userEvent.type(inputs[i], String(i));
    }
    await userEvent.click(screen.getByRole("button", { name: /valider/i }));
    await waitFor(() => expect(verifyMock).toHaveBeenCalledWith("012345"));
    expect(pushMock).toHaveBeenCalledWith("/portal");
  });

  it("shows error on invalid code", async () => {
    verifyMock.mockRejectedValue(new Error("Code invalide"));
    render(<OtpContent />);
    const inputs = screen.getAllByRole("textbox");
    for (let i = 0; i < 6; i++) {
      await userEvent.type(inputs[i], "1");
    }
    await userEvent.click(screen.getByRole("button", { name: /valider/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/code invalide/i);
    });
  });
});
