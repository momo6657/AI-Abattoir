import type { Metadata } from "next";
import Link from "next/link";
import { ErrorBoundary } from "@/components";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Abattoir",
  description: "Multi-model AI interaction platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-background text-foreground">
        <nav className="border-b border-gray-800 px-6 py-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <h1 className="text-xl font-bold">AI Abattoir</h1>
            <div className="flex gap-6">
              <Link href="/" className="hover:text-blue-400">首页</Link>
              <Link href="/models" className="hover:text-blue-400">模型</Link>
              <Link href="/agents" className="hover:text-blue-400">智能体</Link>
              <Link href="/conversations" className="hover:text-blue-400">对话</Link>
              <Link href="/arena" className="hover:text-blue-400">竞技场</Link>
              <Link href="/games" className="hover:text-blue-400">游戏</Link>
              <Link href="/hierarchy" className="hover:text-blue-400">层级</Link>
              <Link href="/evolution" className="hover:text-blue-400">进化</Link>
              <Link href="/spectate" className="hover:text-blue-400">观战</Link>
              <Link href="/leaderboard" className="hover:text-blue-400">排行榜</Link>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </body>
    </html>
  );
}
