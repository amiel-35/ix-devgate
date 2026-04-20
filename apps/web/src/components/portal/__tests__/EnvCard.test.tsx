import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EnvCard } from "../EnvCard";

const BASE_ENV = {
  id: "env-1",
  organization_name: "Client X",
  project_name: "Refonte site",
  environment_name: "Staging principal",
  kind: "staging",
  url: "https://client-x.devgate.example.com",
  gateway_url: "/gateway/env-1/",
  requires_app_auth: false,
  status: "online",
};

describe("EnvCard", () => {
  it("renders org name, project name, env name", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("Client X")).toBeInTheDocument();
    expect(screen.getByText("Refonte site")).toBeInTheDocument();
    expect(screen.getByText("Staging principal")).toBeInTheDocument();
  });

  it("renders kind badge", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("renders Accéder link when online", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("Accéder ↗")).toBeInTheDocument();
  });

  it("renders Indisponible disabled span when offline", () => {
    render(<EnvCard env={{ ...BASE_ENV, status: "offline" }} />);
    const btn = screen.getByText("Indisponible");
    expect(btn).toBeInTheDocument();
    expect(btn.tagName).toBe("SPAN");
  });

  it("renders auth badge when requires_app_auth is true", () => {
    render(<EnvCard env={{ ...BASE_ENV, requires_app_auth: true }} />);
    expect(screen.getByText(/Auth requise/)).toBeInTheDocument();
  });

  it("shows public hostname in footer", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("client-x.devgate.example.com")).toBeInTheDocument();
  });

  it("Accéder links to /resource/{id}", () => {
    render(<EnvCard env={BASE_ENV} />);
    const link = screen.getByText("Accéder ↗").closest("a");
    expect(link).toHaveAttribute("href", "/resource/env-1");
  });
});
