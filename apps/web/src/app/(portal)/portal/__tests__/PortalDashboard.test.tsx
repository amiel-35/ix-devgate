import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PortalDashboard } from "../PortalDashboard";
import type { EnvironmentItem, MeResponse } from "@/lib/api/server";

const USER: MeResponse = { id: "u1", email: "alice@test.com", display_name: "Alice" };

const ENVS: EnvironmentItem[] = [
  {
    id: "e1",
    organization_name: "Client X",
    project_name: "Site corporate",
    environment_name: "Staging principal",
    kind: "staging",
    url: "https://cx-staging.example.com",
    requires_app_auth: false,
    status: "online",
  },
  {
    id: "e2",
    organization_name: "Client X",
    project_name: "App mobile",
    environment_name: "Preview feature",
    kind: "preview",
    url: "https://cx-preview.example.com",
    requires_app_auth: true,
    status: "online",
  },
];

describe("PortalDashboard", () => {
  it("renders welcome banner with user name", () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    expect(screen.getByText(/Bonjour Alice/)).toBeInTheDocument();
  });

  it("renders metric: number of environments", () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders all env cards initially", () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    expect(screen.getByText("Staging principal")).toBeInTheDocument();
    expect(screen.getByText("Preview feature")).toBeInTheDocument();
  });

  it("filters by kind when clicking staging chip", async () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    await userEvent.click(screen.getByRole("button", { name: "Staging" }));
    expect(screen.getByText("Staging principal")).toBeInTheDocument();
    expect(screen.queryByText("Preview feature")).not.toBeInTheDocument();
  });

  it("filters by search input", async () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    await userEvent.type(screen.getByPlaceholderText("Rechercher…"), "App");
    expect(screen.queryByText("Staging principal")).not.toBeInTheDocument();
    expect(screen.getByText("Preview feature")).toBeInTheDocument();
  });

  it("shows empty state when no environments", () => {
    render(<PortalDashboard user={USER} environments={[]} />);
    expect(screen.getByText("Aucune ressource visible")).toBeInTheDocument();
  });
});
