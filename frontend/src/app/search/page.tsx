"use client";

import { useState } from "react";
import { searchApi } from "@/lib/api";
import { ErrorBanner, LoadingSpinner } from "@/components";

interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

interface FetchResult {
  title: string;
  content: string;
  url: string;
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchResult, setFetchResult] = useState<FetchResult | null>(null);
  const [fetchLoading, setFetchLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setFetchResult(null);
    try {
      const r = await searchApi.search(query, 10);
      setResults(r.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "搜索失败");
    } finally {
      setLoading(false);
    }
  };

  const handleFetch = async (url: string) => {
    setFetchLoading(true);
    setFetchResult(null);
    try {
      const r = await searchApi.fetchUrl(url);
      setFetchResult(r.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "抓取失败");
    } finally {
      setFetchLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">联网搜索</h2>

      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入搜索关键词..."
            className="flex-1 bg-gray-800 rounded-lg px-4 py-3 text-lg"
            aria-label="搜索关键词"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 px-6 py-3 rounded-lg font-medium"
          >
            {loading ? "搜索中..." : "搜索"}
          </button>
        </div>
      </form>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {loading && <LoadingSpinner text="正在搜索互联网..." />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Search Results */}
        <div>
          <h3 className="text-lg font-semibold mb-4">搜索结果</h3>
          {results.length === 0 && !loading && (
            <p className="text-gray-500">输入关键词开始搜索</p>
          )}
          <div className="space-y-4">
            {results.map((r, i) => (
              <div key={i} className="bg-gray-900 p-4 rounded-xl">
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 font-medium"
                >
                  {r.title}
                </a>
                <p className="text-sm text-gray-400 mt-1 line-clamp-3">{r.snippet}</p>
                <button
                  onClick={() => handleFetch(r.url)}
                  className="text-xs text-gray-500 hover:text-gray-300 mt-2"
                >
                  抓取全文
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Fetch Result */}
        <div>
          <h3 className="text-lg font-semibold mb-4">网页内容</h3>
          {fetchLoading && <LoadingSpinner text="正在抓取网页..." />}
          {fetchResult && (
            <div className="bg-gray-900 p-4 rounded-xl">
              <h4 className="font-medium mb-2">{fetchResult.title}</h4>
              <p className="text-sm text-gray-300 whitespace-pre-wrap max-h-96 overflow-y-auto">
                {fetchResult.content}
              </p>
            </div>
          )}
          {!fetchResult && !fetchLoading && (
            <p className="text-gray-500">点击搜索结果中的"抓取全文"查看内容</p>
          )}
        </div>
      </div>
    </div>
  );
}
