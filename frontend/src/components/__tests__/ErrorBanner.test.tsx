import { render, screen, fireEvent } from "@testing-library/react";
import ErrorBanner from "../ErrorBanner";

describe("ErrorBanner", () => {
  it("renders message", () => {
    render(<ErrorBanner message="Something went wrong" onDismiss={() => {}} />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("calls onDismiss when X is clicked", () => {
    const onDismiss = jest.fn();
    render(<ErrorBanner message="Error" onDismiss={onDismiss} />);
    fireEvent.click(screen.getByText("×"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
