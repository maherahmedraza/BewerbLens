import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import ErrorPage from "./error";

describe("dashboard error boundary", () => {
  it("surfaces a retry action", () => {
    const reset = vi.fn();

    render(<ErrorPage error={new Error("boom")} reset={reset} />);

    fireEvent.click(screen.getByRole("button", { name: "Retry view" }));

    expect(screen.getByText("Something interrupted the dashboard.")).toBeInTheDocument();
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
