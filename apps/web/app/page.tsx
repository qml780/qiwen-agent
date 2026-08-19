import Image from "next/image";
import Link from "next/link";
import { ArrowRight, BookOpen, Layers3, MousePointer2 } from "lucide-react";
import { knowledgeEntries } from "@/lib/mock-data";

export default function Home() {
  return (
    <main>
      <section className="hero-shell">
        <div className="hero-copy">
          <p className="eyebrow">人机共创游戏工作室</p>
          <h1>从漆艺知识，走向一个你参与决定的游戏。</h1>
          <p className="hero-intro">
            不是一句话自动生成。选择知识、提出想法、审阅每个版本，和共创助手一起把文化动作变成可玩的机制。
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/knowledge">
              探索知识库 <ArrowRight size={15} />
            </Link>
            <Link className="button button-secondary" href="/studio?knowledge=MAT-001">
              打开演示创作室
            </Link>
          </div>
        </div>
        <div className="hero-image">
          <Image
            src="/demo/lacquer-workshop.png"
            alt="漆艺作坊视觉素材"
            fill
            priority
            sizes="(max-width: 900px) 100vw, 48vw"
          />
          <div className="image-caption">
            <span>精选演示素材 / 仅限内部展示</span>
            <strong>漆艺作坊与创作空间</strong>
          </div>
        </div>
      </section>

      <section className="principles-strip" aria-label="产品原则">
        <div><BookOpen size={17} /><span>经过整理的知识</span></div>
        <div><MousePointer2 size={17} /><span>每个阶段都由玩家批准</span></div>
        <div><Layers3 size={17} /><span>所有版本均可回看</span></div>
      </section>

      <section className="editorial-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">以知识为创作材料</p>
            <h2>先理解工艺，再设计机制。</h2>
          </div>
          <Link href="/knowledge" className="text-link">查看知识库 <ArrowRight size={14} /></Link>
        </div>
        <div className="knowledge-preview-grid">
          {knowledgeEntries.map((entry, index) => (
            <Link href={`/knowledge/${entry.id}`} className="knowledge-preview" key={entry.id}>
              <div className="preview-index">0{index + 1}</div>
              <div className="preview-image">
                <Image src={entry.image_url} alt="" fill sizes="33vw" />
              </div>
              <p className="category-label">{entry.category}</p>
              <h3>{entry.title}</h3>
              <p>{entry.summary}</p>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
