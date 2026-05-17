import { render, screen } from "@testing-library/react";
import ThinkingIndicator from "../ThinkingIndicator";

describe("ThinkingIndicator", () => {
  it("renders bouncing dots", () => {
    const { container } = render(<ThinkingIndicator />);
    expect(container.querySelectorAll(".animate-bounce")).toHaveLength(3);
  });

  it("renders agent name when provided", () => {
    render(<ThinkingIndicator agentName="谋略家" />);
    expect(screen.getByText("谋略家 正在思考...")).toBeInTheDocument();
  });

  it("does not render text when no agent name", () => {
    render(<ThinkingIndicator />);
    expect(screen.queryByText(/正在思考/)).not.toBeInTheDocument();
  });
});
