import { render, screen } from "@testing-library/react";
import ChatMessage from "../ChatMessage";

describe("ChatMessage", () => {
  it("renders text content", () => {
    render(
      <ChatMessage
        agentName="Alice"
        content="Hello world"
        createdAt="2026-01-01T00:00:00Z"
      />
    );
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders agent name in info span", () => {
    const { container } = render(
      <ChatMessage
        agentName="Alice"
        content="Hello"
        createdAt="2026-01-01T00:00:00Z"
      />
    );
    const infoSpan = container.querySelector(".text-gray-400");
    expect(infoSpan?.textContent).toContain("Alice");
  });

  it("renders system message", () => {
    render(
      <ChatMessage
        content="System message"
        createdAt="2026-01-01T00:00:00Z"
        isSystem
      />
    );
    expect(screen.getByText("System message")).toBeInTheDocument();
  });

  it("renders elimination message", () => {
    render(
      <ChatMessage
        content="Player eliminated"
        createdAt="2026-01-01T00:00:00Z"
        isElimination
      />
    );
    expect(screen.getByText("Player eliminated")).toBeInTheDocument();
  });

  it("renders turn number in info span", () => {
    const { container } = render(
      <ChatMessage
        agentName="Alice"
        content="Hello"
        createdAt="2026-01-01T00:00:00Z"
        turnNumber={5}
      />
    );
    const infoSpan = container.querySelector(".text-gray-400");
    expect(infoSpan?.textContent).toContain("5");
  });

  it("renders unknown when no agent name", () => {
    const { container } = render(
      <ChatMessage
        content="Anonymous"
        createdAt="2026-01-01T00:00:00Z"
      />
    );
    const infoSpan = container.querySelector(".text-gray-400");
    expect(infoSpan?.textContent).toContain("未知");
  });
});
