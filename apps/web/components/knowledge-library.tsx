"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Filter, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { knowledgeCategories, knowledgeEntries } from "@/lib/knowledge-v2";

export function KnowledgeLibraryClient() {
  const [category, setCategory] = useState("全部");
  const [query, setQuery] = useState("");
  const visible = useMemo(() => knowledgeEntries.filter((entry) => {
    const inCategory = category === "全部" || entry.category === category;
    const haystack = [entry.title, entry.summary, ...entry.core_facts, ...entry.key_actions].join(" ");
    return inCategory && haystack.includes(query.trim());
  }), [category, query]);

  return <>
    <div className="knowledge-tools">
      <label className="knowledge-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索材料、工艺、历史或地域" /></label>
      <span>{visible.length} 条知识</span>
    </div>
    <div className="filter-row" aria-label="知识分类">
      <Filter size={15} />
      {knowledgeCategories.map((item) => <button type="button" aria-pressed={category === item} onClick={() => setCategory(item)} className={category === item ? "filter-active" : ""} key={item}>{item}</button>)}
    </div>
    <section className="library-grid">
      {visible.map((entry, index) => <Link href={`/knowledge/${entry.id}`} className="library-entry" key={entry.id}>
        <div className="library-image">
          <Image src={entry.image_url} alt={entry.title} fill sizes="(max-width: 900px) 100vw, 33vw" />
          <span>{String(index + 1).padStart(2, "0")}</span><small>AI 生成示意图</small>
        </div>
        <div className="library-entry-title"><div><p>{entry.category}</p><h2>{entry.title}</h2></div><ArrowUpRight size={18} /></div>
        <p className="library-summary">{entry.summary}</p>
        <div className="tag-row">{entry.key_actions.slice(0, 3).map((item) => <span key={item}>{item}</span>)}</div>
      </Link>)}
      {!visible.length && <p className="knowledge-empty">没有匹配结果，请更换分类或关键词。</p>}
    </section>
  </>;
}
