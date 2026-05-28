import { render, screen } from "@testing-library/react";
import DebatePanel from "../DebatePanel";

const rounds = [
  { phase: "opening", side: "pro" as const, content: "AI will create jobs" },
  { phase: "opening", side: "con" as const, content: "AI will destroy jobs" },
];

describe("DebatePanel", () => {
  it("renders topic", () => {
    render(<DebatePanel topic="AI and Jobs" rounds={[]} currentPhase="opening" />);
    expect(screen.getByText("AI and Jobs")).toBeInTheDocument();
  });

  it("renders phase indicators", () => {
    render(<DebatePanel topic="Test" rounds={[]} currentPhase="opening" />);
    expect(screen.getByText("立论")).toBeInTheDocument();
    expect(screen.getByText("质询")).toBeInTheDocument();
    expect(screen.getByText("总结")).toBeInTheDocument();
    expect(screen.getByText("评分")).toBeInTheDocument();
  });

  it("renders pro and con sides", () => {
    render(<DebatePanel topic="Test" rounds={rounds} currentPhase="opening" />);
    expect(screen.getByText("正方")).toBeInTheDocument();
    expect(screen.getByText("反方")).toBeInTheDocument();
  });

  it("renders argument content", () => {
    render(<DebatePanel topic="Test" rounds={rounds} currentPhase="opening" />);
    expect(screen.getByText("AI will create jobs")).toBeInTheDocument();
    expect(screen.getByText("AI will destroy jobs")).toBeInTheDocument();
  });

  it("renders scores when available", () => {
    const scores = {
      pro_arguments: 8, pro_logic: 7, pro_expression: 9,
      con_arguments: 6, con_logic: 7, con_expression: 8,
      pro_total: 24, con_total: 21,
      winner: "正方", reason: "Better arguments",
    };
    render(<DebatePanel topic="Test" rounds={[]} currentPhase="result" scores={scores} />);
    expect(screen.getByText("正方获胜")).toBeInTheDocument();
    expect(screen.getByText("Better arguments")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<DebatePanel topic="Test" rounds={[]} currentPhase="opening" />);
    expect(screen.getByText("正方")).toBeInTheDocument();
  });
});
