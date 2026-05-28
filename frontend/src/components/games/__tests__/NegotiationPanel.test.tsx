import { render, screen } from "@testing-library/react";
import NegotiationPanel from "../NegotiationPanel";

const scenario = {
  name: "资源分配",
  description: "两国争夺资源",
  resources: { 土地: 100, 矿产: 50 },
};

const turns = [
  { party: "A" as const, proposal: "我方要60%土地", action: "propose" as const, reason: "我方人口多" },
  { party: "B" as const, proposal: "我方要40%矿产", action: "propose" as const, reason: "我方工业需求" },
];

describe("NegotiationPanel", () => {
  it("renders scenario name", () => {
    render(<NegotiationPanel scenario={scenario} turns={[]} />);
    expect(screen.getByText("资源分配")).toBeInTheDocument();
  });

  it("renders scenario description", () => {
    render(<NegotiationPanel scenario={scenario} turns={[]} />);
    expect(screen.getByText("两国争夺资源")).toBeInTheDocument();
  });

  it("renders resources", () => {
    render(<NegotiationPanel scenario={scenario} turns={[]} />);
    expect(screen.getByText(/土地/)).toBeInTheDocument();
    expect(screen.getByText(/矿产/)).toBeInTheDocument();
  });

  it("renders current proposal", () => {
    render(<NegotiationPanel turns={[]} currentProposal="各分50%" />);
    expect(screen.getByText("各分50%")).toBeInTheDocument();
  });

  it("renders negotiation turns", () => {
    render(<NegotiationPanel turns={turns} />);
    expect(screen.getByText("我方要60%土地")).toBeInTheDocument();
    expect(screen.getByText("我方要40%矿产")).toBeInTheDocument();
  });

  it("renders deal reached", () => {
    render(<NegotiationPanel turns={[]} dealReached="各分50%" />);
    expect(screen.getByText("达成协议")).toBeInTheDocument();
    expect(screen.getByText("各分50%")).toBeInTheDocument();
  });

  it("renders scores", () => {
    const scores = { party_a_score: 8, party_b_score: 7, fairness: 9, evaluation: "公平合理" };
    render(<NegotiationPanel turns={[]} scores={scores} />);
    expect(screen.getByText("独立评估")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("公平合理")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<NegotiationPanel turns={[]} />);
    // Should render without errors
    expect(document.body).toBeInTheDocument();
  });
});
