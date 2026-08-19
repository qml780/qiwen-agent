import { KnowledgeLibraryClient } from "@/components/knowledge-library";

export default function KnowledgeLibrary() {
  return <main className="library-page">
    <header className="page-intro"><div><p className="eyebrow">漆艺知识库 V2 · 44 条</p><h1>从可靠知识出发，<br />把漆艺变成游戏语言。</h1></div><p>浏览材料、工艺、历史、地域与文化。每条知识均提供事实、因果、操作、误区和参考资料。</p></header>
    <KnowledgeLibraryClient />
  </main>;
}
