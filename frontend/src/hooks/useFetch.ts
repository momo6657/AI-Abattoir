import { useState, useEffect, useCallback } from "react";
import { AxiosResponse } from "axios";

interface UseFetchState<T> {
  data: T | null;
  loading: boolean;
  error: string;
}

export function useFetch<T>(
  fetcher: () => Promise<AxiosResponse<T>>,
  deps: unknown[] = []
) {
  const [state, setState] = useState<UseFetchState<T>>({
    data: null,
    loading: true,
    error: "",
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: "" }));
    try {
      const res = await fetcher();
      setState({ data: res.data, loading: false, error: "" });
    } catch (e: unknown) {
      setState({
        data: null,
        loading: false,
        error: e instanceof Error ? e.message : "请求失败",
      });
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}
