import { render, screen, fireEvent } from "@testing-library/react";
import Modal from "../Modal";

describe("Modal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <Modal open={false} onClose={() => {}} title="Test">Content</Modal>
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders title and content when open", () => {
    render(
      <Modal open onClose={() => {}} title="My Modal">Hello World</Modal>
    );
    expect(screen.getByText("My Modal")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("calls onClose when backdrop is clicked", () => {
    const onClose = jest.fn();
    const { container } = render(
      <Modal open onClose={onClose} title="Test">Content</Modal>
    );
    fireEvent.click(container.firstChild!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when X is clicked", () => {
    const onClose = jest.fn();
    render(
      <Modal open onClose={onClose} title="Test">Content</Modal>
    );
    fireEvent.click(screen.getByText("×"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on Escape key", () => {
    const onClose = jest.fn();
    render(
      <Modal open onClose={onClose} title="Test">Content</Modal>
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
