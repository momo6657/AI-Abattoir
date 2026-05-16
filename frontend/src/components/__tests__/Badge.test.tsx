import { render, screen } from "@testing-library/react";
import Badge from "../Badge";

describe("Badge", () => {
  it("renders text", () => {
    render(<Badge text="online" />);
    expect(screen.getByText("online")).toBeInTheDocument();
  });

  it("applies success variant", () => {
    render(<Badge text="active" variant="success" />);
    const badge = screen.getByText("active");
    expect(badge.className).toContain("bg-green-900");
  });

  it("applies danger variant", () => {
    render(<Badge text="offline" variant="danger" />);
    const badge = screen.getByText("offline");
    expect(badge.className).toContain("bg-red-900");
  });

  it("applies md size", () => {
    render(<Badge text="test" size="md" />);
    const badge = screen.getByText("test");
    expect(badge.className).toContain("px-3");
  });

  it("defaults to sm size and default variant", () => {
    render(<Badge text="default" />);
    const badge = screen.getByText("default");
    expect(badge.className).toContain("px-2");
    expect(badge.className).toContain("bg-gray-800");
  });
});
