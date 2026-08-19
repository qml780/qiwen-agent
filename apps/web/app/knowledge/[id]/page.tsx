import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ExternalLink } from "lucide-react";
import { notFound } from "next/navigation";
import { findKnowledge, knowledgeEntries } from "@/lib/knowledge-v2";

export default async function KnowledgeDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const entry = findKnowledge(id);
  if (!entry) notFound();
  const related = knowledgeEntries.filter((item) => item.category === entry.category && item.id !== entry.id).slice(0, 3);
  return <main className="detail-page">
    <Link href="/knowledge" className="back-link"><ArrowLeft size={14} /> 返回知识库</Link>
    <section className="detail-hero"><div><p className="eyebrow">{entry.category} / {entry.id}</p><h1>{entry.title}</h1><p className="detail-lede">{entry.summary}</p></div><div className="detail-image"><Image src={entry.image_url} alt={entry.title} fill priority sizes="55vw" /><span>AI 生成示意图</span></div></section>
    <section className="detail-body"><aside><p className="metadata-label">核验状态</p><p>{entry.verification}</p><p className="metadata-label">学习目标</p><ul>{entry.learning_objectives.map((item) => <li key={item}>{item}</li>)}</ul></aside>
      <article><h2>核心事实</h2><ul>{entry.core_facts.map((item) => <li key={item}>{item}</li>)}</ul>
        <div className="detail-columns"><div><h3>因果关系</h3><ul>{entry.cause_effect_relations.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h3>关键操作</h3><ul>{entry.key_actions.map((item) => <li key={item}>{item}</li>)}</ul></div></div>
        <div className="detail-columns warning-columns"><div><h3>常见误区</h3><ul>{entry.common_misconceptions.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h3>参考资料</h3>{entry.references.map((ref) => <a className="knowledge-reference" href={ref.url} target="_blank" rel="noreferrer" key={ref.url}>{ref.title}<ExternalLink size={13} /></a>)}</div></div>
        <h2>相关知识</h2><div className="tag-row">{related.map((item) => <Link href={`/knowledge/${item.id}`} key={item.id}>{item.title}</Link>)}</div>
        <Link href={`/studio?knowledge=${entry.id}`} className="create-with-knowledge"><span><small>创建新项目</small>用这条知识开始创作</span><ArrowRight size={20} /></Link>
      </article></section>
  </main>;
}
