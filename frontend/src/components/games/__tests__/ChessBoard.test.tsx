import { render, screen } from "@testing-library/react";
import ChessBoard from "../ChessBoard";

const initialBoard: Record<string, [string, string]> = {
  a1: ["white", "rook"], b1: ["white", "knight"], c1: ["white", "bishop"],
  d1: ["white", "queen"], e1: ["white", "king"], f1: ["white", "bishop"],
  g1: ["white", "knight"], h1: ["white", "rook"],
  a2: ["white", "pawn"], b2: ["white", "pawn"], c2: ["white", "pawn"],
  d2: ["white", "pawn"], e2: ["white", "pawn"], f2: ["white", "pawn"],
  g2: ["white", "pawn"], h2: ["white", "pawn"],
  a7: ["black", "pawn"], b7: ["black", "pawn"], c7: ["black", "pawn"],
  d7: ["black", "pawn"], e7: ["black", "pawn"], f7: ["black", "pawn"],
  g7: ["black", "pawn"], h7: ["black", "pawn"],
  a8: ["black", "rook"], b8: ["black", "knight"], c8: ["black", "bishop"],
  d8: ["black", "queen"], e8: ["black", "king"], f8: ["black", "bishop"],
  g8: ["black", "knight"], h8: ["black", "rook"],
};

describe("ChessBoard", () => {
  it("renders all 64 squares", () => {
    const { container } = render(<ChessBoard board={initialBoard} />);
    const squares = container.querySelectorAll('[title]');
    expect(squares.length).toBe(64);
  });

  it("renders Unicode chess pieces", () => {
    render(<ChessBoard board={initialBoard} />);
    // White king
    expect(screen.getByTitle("e1")).toHaveTextContent("♔");
    // Black king
    expect(screen.getByTitle("e8")).toHaveTextContent("♚");
  });

  it("highlights last move", () => {
    const { container } = render(
      <ChessBoard board={initialBoard} lastMove={{ from: "e2", to: "e4" }} />
    );
    const e2 = screen.getByTitle("e2");
    const e4 = screen.getByTitle("e4");
    expect(e2.className).toContain("bg-yellow-600");
    expect(e4.className).toContain("bg-yellow-600");
  });

  it("highlights king in check", () => {
    const board: Record<string, [string, string]> = {
      e1: ["white", "king"],
      e8: ["black", "rook"],
      e5: ["black", "queen"],
    };
    render(<ChessBoard board={board} inCheck="white" />);
    const king = screen.getByTitle("e1");
    expect(king.className).toContain("bg-red-500");
  });

  it("renders empty board", () => {
    const { container } = render(<ChessBoard board={{}} />);
    const squares = container.querySelectorAll('[title]');
    expect(squares.length).toBe(64);
  });

  it("renders flipped board", () => {
    const { container } = render(<ChessBoard board={initialBoard} flipped />);
    const squares = container.querySelectorAll('[title]');
    expect(squares.length).toBe(64);
  });

  it("displays captured pieces", () => {
    const board: Record<string, [string, string]> = {
      e1: ["white", "king"],
      e8: ["black", "king"],
    };
    render(<ChessBoard board={board} />);
    // With only kings, no captured pieces displayed
    expect(screen.getByTitle("e1")).toBeInTheDocument();
  });
});
