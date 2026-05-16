import { renderHook, waitFor } from "@testing-library/react";
import { useFetch } from "../useFetch";

describe("useFetch", () => {
  it("returns data on success", async () => {
    const mockFetcher = jest.fn().mockResolvedValue({ data: { name: "test" } });
    const { result } = renderHook(() => useFetch(mockFetcher, []));

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual({ name: "test" });
    expect(result.current.error).toBe("");
  });

  it("returns error on failure", async () => {
    const mockFetcher = jest.fn().mockRejectedValue(new Error("Network error"));
    const { result } = renderHook(() => useFetch(mockFetcher, []));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("Network error");
  });

  it("reload re-fetches data", async () => {
    let count = 0;
    const mockFetcher = jest.fn().mockImplementation(() => {
      count++;
      return Promise.resolve({ data: { count } });
    });

    const { result } = renderHook(() => useFetch(mockFetcher, []));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual({ count: 1 });

    result.current.reload();

    await waitFor(() => {
      expect(result.current.data).toEqual({ count: 2 });
    });
  });
});
