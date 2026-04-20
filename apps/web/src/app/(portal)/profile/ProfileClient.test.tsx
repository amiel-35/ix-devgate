import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfileClient } from "./ProfileClient";
import type { MeResponse, SessionItem } from "@/lib/api/server";

vi.mock("@/lib/api/client", () => ({
  portalApi: {
    revokeSession: vi.fn().mockResolvedValue(undefined),
  },
  authApi: {
    logout: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const USER: MeResponse = {
  id: "u1",
  email: "alice@test.com",
  display_name: "Alice Test",
};

const SESSIONS: SessionItem[] = [
  {
    id: "s-current",
    expires_at: "2026-04-27T00:00:00Z",
    last_seen_at: "2026-04-20T10:00:00Z",
    ip: "127.0.0.1",
    user_agent: "Chrome/macOS",
    is_current: true,
  },
  {
    id: "s-other",
    expires_at: "2026-04-25T00:00:00Z",
    last_seen_at: "2026-04-19T08:00:00Z",
    ip: "10.0.0.1",
    user_agent: "Safari/iPhone",
    is_current: false,
  },
];

describe("ProfileClient", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders user name and email", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    expect(screen.getByText("Alice Test")).toBeInTheDocument();
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
  });

  it("renders all sessions", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    expect(screen.getByText("Chrome/macOS")).toBeInTheDocument();
    expect(screen.getByText("Safari/iPhone")).toBeInTheDocument();
  });

  it("current session revoke button is disabled", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    const buttons = screen.getAllByText("Révoquer") as HTMLButtonElement[];
    // Find the button in the current session row
    const currentRow = screen.getByText("Session actuelle").closest("[data-current='true']");
    const currentBtn = currentRow?.querySelector("button");
    expect(currentBtn).toBeDisabled();
  });

  it("revoking a session calls the API", async () => {
    const { portalApi } = await import("@/lib/api/client");
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);

    const revokeButtons = screen.getAllByText("Révoquer") as HTMLButtonElement[];
    const activeRevoke = revokeButtons.find((b) => !b.disabled)!;
    await userEvent.click(activeRevoke);

    await waitFor(() => {
      expect(portalApi.revokeSession).toHaveBeenCalledWith("s-other");
    });
  });

  it("shows avatar initials from display name", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    expect(screen.getByText("AT")).toBeInTheDocument(); // "Alice Test" → "AT"
  });
});
