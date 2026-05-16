import { render, screen } from "@testing-library/react";
import ProgressBar from "../ProgressBar";

describe("ProgressBar", () => {
  it("renders without label by default", () => {
    const { container } = render(<ProgressBar value={50} />);
    expect(container.querySelector('[style*="width: 50%"]')).toBeInTheDocument();
    expect(screen.queryByText("50%")).not.toBeInTheDocument();
  });

  it("renders label when showLabel is true", () => {
    render(<ProgressBar value={75} showLabel />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("clamps value to 0-100", () => {
    const { container } = render(<ProgressBar value={150} />);
    expect(container.querySelector('[style*="width: 100%"]')).toBeInTheDocument();
  });

  it("clamps negative value to 0", () => {
    const { container } = render(<ProgressBar value={-10} />);
    expect(container.querySelector('[style*="width: 0%"]')).toBeInTheDocument();
  });
});
