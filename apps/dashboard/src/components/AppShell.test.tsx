import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import AppShell from "./AppShell";

const usePathnameMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathnameMock(),
}));

vi.mock("@/components/Header", () => ({
  default: () => <div data-testid="header">Header</div>,
}));

vi.mock("@/components/Sidebar", () => ({
  default: () => <div data-testid="sidebar">Sidebar</div>,
}));

describe("AppShell", () => {
  it("renders public routes without the private shell", () => {
    usePathnameMock.mockReturnValue("/");

    render(
      <AppShell>
        <div>Landing</div>
      </AppShell>
    );

    expect(screen.getByText("Landing")).toBeInTheDocument();
    expect(screen.queryByTestId("header")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sidebar")).not.toBeInTheDocument();
  });

  it("renders authenticated routes with sidebar and header", () => {
    usePathnameMock.mockReturnValue("/dashboard");

    render(
      <AppShell>
        <div>Dashboard</div>
      </AppShell>
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("header")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });
});
