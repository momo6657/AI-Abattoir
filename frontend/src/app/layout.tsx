import type { Metadata } from "next";
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
              <a href="/" className="hover:text-blue-400">首页</a>
              <a href="/models" className="hover:text-blue-400">模型</a>
              <a href="/agents" className="hover:text-blue-400">智能体</a>
              <a href="/conversations" className="hover:text-blue-400">对话</a>
              <a href="/arena" className="hover:text-blue-400">竞技场</a>
              <a href="/games" className="hover:text-blue-400">游戏</a>
              <a href="/leaderboard" className="hover:text-blue-400">排行榜</a>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
