import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "漆问 · 人机共创游戏工作室",
  description: "人与智能体共同创作漆艺文化游戏的工作室",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="site-header">
          <Link href="/" className="brand" aria-label="漆问首页">
            <span className="brand-mark">漆</span>
            <span>漆问</span>
          </Link>
          <nav aria-label="主导航">
            <Link href="/knowledge">知识库</Link>
            <Link href="/studio?knowledge=MAT-001">创作室</Link>
            <Link href="/projects">项目</Link>
          </nav>
          <div className="header-meta">
            <span className="status-dot" /> 本地服务 · 数据已保存
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
