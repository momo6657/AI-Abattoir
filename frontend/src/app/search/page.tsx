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
    <div className="animate-fade-in">
      <div className="mb-8">
        <h2 className="text-2xl font-bold">联网搜索</h2>
        <p className="text-sm text-gray-400 mt-1">实时搜索互联网获取最新信息</p>
      </div>

      <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入搜索关键词..."
            className="input-field text-base py-3"
            aria-label="搜索关键词"
          />
          <button
            type="submit"
            disabled={loading}
            className="btn-primary px-8 whitespace-nowrap disabled:opacity-50"
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
            <div className="card p-12 text-center">
              <div className="w-12 h-12 rounded-xl bg-surface-overlay flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <p className="text-gray-400">输入关键词开始搜索</p>
            </div>
          )}
          <div className="space-y-3">
            {results.map((r, i) => (
              <div key={i} className="card-hover p-4">
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-hover hover:text-accent font-medium text-sm"
                >
                  {r.title}
                </a>
                <p className="text-sm text-gray-400 mt-1.5 line-clamp-3">{r.snippet}</p>
                <button
                  onClick={() => handleFetch(r.url)}
                  className="btn-ghost text-xs mt-2 px-2 py-1"
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
            <div className="card p-5 animate-slide-up">
              <h4 className="font-medium mb-3">{fetchResult.title}</h4>
              <div className="text-sm text-gray-300 whitespace-pre-wrap max-h-[500px] overflow-y-auto leading-relaxed">
                {fetchResult.content}
              </div>
            </div>
          )}
          {!fetchResult && !fetchLoading && (
            <div className="card p-12 text-center">
              <div className="w-12 h-12 rounded-xl bg-surface-overlay flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <p className="text-gray-400 text-sm">点击搜索结果中的"抓取全文"查看内容</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
