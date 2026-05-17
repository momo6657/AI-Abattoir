"use client";

import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="bg-red-900/30 border border-red-800 rounded-xl p-6 m-4">
          <h3 className="text-red-400 font-semibold mb-2">出现错误</h3>
          <p className="text-gray-400 text-sm mb-4">
            {this.state.error?.message || "未知错误"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="bg-red-800 hover:bg-red-700 px-4 py-2 rounded-lg text-sm"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
