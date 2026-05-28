import { render, screen, fireEvent } from "@testing-library/react";
import GameControlBar from "../GameControlBar";

describe("GameControlBar", () => {
  const defaultProps = {
    status: "waiting" as const,
    currentTurn: 0,
    maxTurns: 20,
    connected: true,
    onStart: jest.fn(),
    onPause: jest.fn(),
    onResume: jest.fn(),
    onSpeedChange: jest.fn(),
  };

  beforeEach(() => jest.clearAllMocks());

  it("renders waiting state with start button", () => {
    render(<GameControlBar {...defaultProps} />);
    expect(screen.getByText("等待开始")).toBeInTheDocument();
    expect(screen.getByText("开始游戏")).toBeInTheDocument();
  });

  it("renders in_progress state with pause button", () => {
    render(<GameControlBar {...defaultProps} status="in_progress" />);
    expect(screen.getByText("进行中")).toBeInTheDocument();
    expect(screen.getByText("暂停")).toBeInTheDocument();
  });

  it("renders paused state with resume button", () => {
    render(<GameControlBar {...defaultProps} status="paused" />);
    expect(screen.getByText("已暂停")).toBeInTheDocument();
    expect(screen.getByText("继续")).toBeInTheDocument();
  });

  it("renders finished state", () => {
    render(<GameControlBar {...defaultProps} status="finished" />);
    expect(screen.getByText("已结束")).toBeInTheDocument();
  });

  it("calls onStart when start button clicked", () => {
    render(<GameControlBar {...defaultProps} />);
    fireEvent.click(screen.getByText("开始游戏"));
    expect(defaultProps.onStart).toHaveBeenCalled();
  });

  it("calls onPause when pause button clicked", () => {
    render(<GameControlBar {...defaultProps} status="in_progress" />);
    fireEvent.click(screen.getByText("暂停"));
    expect(defaultProps.onPause).toHaveBeenCalled();
  });

  it("calls onResume when resume button clicked", () => {
    render(<GameControlBar {...defaultProps} status="paused" />);
    fireEvent.click(screen.getByText("继续"));
    expect(defaultProps.onResume).toHaveBeenCalled();
  });

  it("displays connected status", () => {
    render(<GameControlBar {...defaultProps} />);
    expect(screen.getByText("已连接")).toBeInTheDocument();
  });

  it("displays disconnected status", () => {
    render(<GameControlBar {...defaultProps} connected={false} />);
    expect(screen.getByText("未连接")).toBeInTheDocument();
  });

  it("displays turn progress", () => {
    render(<GameControlBar {...defaultProps} currentTurn={5} maxTurns={20} />);
    expect(screen.getByText("回合 5/20")).toBeInTheDocument();
  });

  it("shows speed controls during in_progress", () => {
    render(<GameControlBar {...defaultProps} status="in_progress" />);
    expect(screen.getByText("速度")).toBeInTheDocument();
    expect(screen.getByText("1s")).toBeInTheDocument();
    expect(screen.getByText("3s")).toBeInTheDocument();
    expect(screen.getByText("5s")).toBeInTheDocument();
  });

  it("hides speed controls when not in_progress", () => {
    render(<GameControlBar {...defaultProps} status="waiting" />);
    expect(screen.queryByText("速度")).not.toBeInTheDocument();
  });
});
