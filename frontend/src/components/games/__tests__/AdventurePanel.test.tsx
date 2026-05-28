import { render, screen, fireEvent } from "@testing-library/react";
import AdventurePanel from "../AdventurePanel";

const defaultState = {
  hp: 80,
  max_hp: 100,
  inventory: ["铁剑", "药水"],
  current_location: "森林深处",
  explored_locations: ["起始之地", "森林深处"],
};

describe("AdventurePanel", () => {
  it("renders HP bar", () => {
    render(<AdventurePanel state={defaultState} />);
    expect(screen.getByText("80/100")).toBeInTheDocument();
  });

  it("renders inventory items", () => {
    render(<AdventurePanel state={defaultState} />);
    expect(screen.getByText("铁剑")).toBeInTheDocument();
    expect(screen.getByText("药水")).toBeInTheDocument();
  });

  it("renders current location", () => {
    const { container } = render(<AdventurePanel state={defaultState} />);
    expect(container.textContent).toContain("森林深处");
  });

  it("renders scene description", () => {
    render(<AdventurePanel state={defaultState} scene="一片阴暗的森林" />);
    expect(screen.getByText("一片阴暗的森林")).toBeInTheDocument();
  });

  it("renders action options", () => {
    const options = { OPTION_A: "前进", OPTION_B: "探索" };
    const onChoice = jest.fn();
    render(<AdventurePanel state={defaultState} options={options} onChoice={onChoice} />);
    expect(screen.getByText("前进")).toBeInTheDocument();
    expect(screen.getByText("探索")).toBeInTheDocument();
  });

  it("calls onChoice when option clicked", () => {
    const options = { OPTION_A: "前进" };
    const onChoice = jest.fn();
    render(<AdventurePanel state={defaultState} options={options} onChoice={onChoice} />);
    fireEvent.click(screen.getByText("前进"));
    expect(onChoice).toHaveBeenCalledWith("OPTION_A");
  });

  it("renders HP change from last result", () => {
    const lastResult = { choice: "前进", result: "你受伤了", hp_change: -10 };
    render(<AdventurePanel state={defaultState} lastResult={lastResult} />);
    expect(screen.getByText("HP -10")).toBeInTheDocument();
  });

  it("renders item from last result", () => {
    const lastResult = { choice: "探索", result: "你找到了宝箱", item: "金戒指" };
    render(<AdventurePanel state={defaultState} lastResult={lastResult} />);
    expect(screen.getByText("获得：金戒指")).toBeInTheDocument();
  });

  it("renders explored locations", () => {
    render(<AdventurePanel state={defaultState} />);
    expect(screen.getByText("起始之地")).toBeInTheDocument();
  });

  it("renders game over", () => {
    render(<AdventurePanel state={defaultState} gameOver={{ result: "death" }} />);
    expect(screen.getByText("探险结束")).toBeInTheDocument();
  });

  it("does not render options when game over", () => {
    const options = { OPTION_A: "前进" };
    render(<AdventurePanel state={defaultState} options={options} gameOver={{ result: "death" }} />);
    expect(screen.queryByText("前进")).not.toBeInTheDocument();
  });
});
