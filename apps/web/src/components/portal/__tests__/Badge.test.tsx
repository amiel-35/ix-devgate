import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KindBadge, StatusBadge, AuthBadge } from "../Badge";

describe("KindBadge", () => {
  it("renders 'staging' label", () => {
    render(<KindBadge kind="staging" />);
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("renders 'preview' label", () => {
    render(<KindBadge kind="preview" />);
    expect(screen.getByText("preview")).toBeInTheDocument();
  });

  it("renders 'dev' label", () => {
    render(<KindBadge kind="dev" />);
    expect(screen.getByText("dev")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders 'En ligne' for online status", () => {
    render(<StatusBadge status="online" />);
    expect(screen.getByText("En ligne")).toBeInTheDocument();
  });

  it("renders 'Hors ligne' for offline status", () => {
    render(<StatusBadge status="offline" />);
    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
  });

  it("renders 'Inconnu' for unknown status", () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText("Inconnu")).toBeInTheDocument();
  });
});

describe("AuthBadge", () => {
  it("renders when shown", () => {
    render(<AuthBadge />);
    expect(screen.getByText(/Auth requise/)).toBeInTheDocument();
  });
});
