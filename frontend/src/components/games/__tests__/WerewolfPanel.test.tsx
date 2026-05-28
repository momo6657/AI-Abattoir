import { render, screen } from "@testing-library/react";
import WerewolfPanel from "../WerewolfPanel";

const players = [
  { agent_id: "p1", name: "Alice", role: "werewolf", alive: true },
  { agent_id: "p2", name: "Bob", role: "seer", alive: true },
  { agent_id: "p3", name: "Charlie", role: "villager", alive: false },
];

describe("WerewolfPanel", () => {
  it("renders phase indicator", () => {
    render(<WerewolfPanel players={players} phase="night" currentTurn={1} />);
    expect(screen.getByText(/夜晚/)).toBeInTheDocument();
    expect(screen.getByText(/第 1 回合/)).toBeInTheDocument();
  });

  it("renders day phase", () => {
    render(<WerewolfPanel players={players} phase="day" currentTurn={3} />);
    expect(screen.getByText(/白天/)).toBeInTheDocument();
  });

  it("renders all player names", () => {
    render(<WerewolfPanel players={players} phase="day" currentTurn={1} />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
  });

  it("renders death announcement", () => {
    render(
      <WerewolfPanel
        players={players}
        phase="day"
        currentTurn={1}
        lastDeath={["Charlie"]}
      />
    );
    expect(screen.getByText(/Charlie.*死亡/)).toBeInTheDocument();
  });

  it("renders safe night", () => {
    render(
      <WerewolfPanel players={players} phase="day" currentTurn={1} lastDeath={[]} />
    );
    expect(screen.getByText(/平安夜/)).toBeInTheDocument();
  });

  it("renders vote result", () => {
    render(
      <WerewolfPanel
        players={players}
        phase="day"
        currentTurn={1}
        voteResult={{
          votes: { p1: "p2", p2: "p1" },
          vote_counts: { p1: 1, p2: 1 },
          exiled: "p1",
        }}
      />
    );
    expect(screen.getByText("投票结果")).toBeInTheDocument();
  });

  it("renders game over with werewolf win", () => {
    render(
      <WerewolfPanel
        players={players}
        phase="day"
        currentTurn={1}
        gameOver={{ winner: "werewolf", roles: { p1: "werewolf" } }}
      />
    );
    expect(screen.getByText("狼人获胜")).toBeInTheDocument();
  });

  it("renders game over with village win", () => {
    render(
      <WerewolfPanel
        players={players}
        phase="day"
        currentTurn={1}
        gameOver={{ winner: "village", roles: {} }}
      />
    );
    expect(screen.getByText("村民获胜")).toBeInTheDocument();
  });
});
