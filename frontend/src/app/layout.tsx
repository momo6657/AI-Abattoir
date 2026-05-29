import type { Metadata } from "next";
import { Navigation } from "@/components/Navigation";
import { ErrorBoundary } from "@/components";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Abattoir",
  description: "Multi-model AI interaction platform",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
        <Navigation />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </body>
    </html>
  );
}
