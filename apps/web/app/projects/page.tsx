"use client";

import Link from "next/link";
import { ArrowRight, LoaderCircle, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/domain";

export default function ProjectsPage() {
  const pageSize = 40;
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    void api.projects(pageSize, 0)
      .then((items) => { setProjects(items); setHasMore(items.length === pageSize); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "无法读取项目"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="library-page projects-page">
      <header className="page-intro">
        <div><p className="eyebrow">持久化项目</p><h1>继续你的漆艺游戏创作。</h1></div>
        <div><p>已有项目可以继续或删除。新游戏会创建独立项目，不再覆盖上一次进度。</p><Link className="button button-primary" href="/knowledge"><Plus size={15} />新建游戏</Link></div>
      </header>
      {loading && <div className="project-loading"><LoaderCircle className="spin" />正在读取项目……</div>}
      {error && <div className="inline-error">{error}</div>}
      {!loading && !error && !projects.length && <div className="project-empty">还没有项目。请从知识库选择一条知识开始创作。</div>}
      <section className="project-list">
        {projects.map((project) => <article className="project-row" key={project.id}>
          <Link href={`/studio?knowledge=${project.selected_knowledge_id}&project=${project.id}`}>
            <span><small>{project.current_stage === "ready_to_build" ? "可以构建" : "创作进行中"}</small><strong>{project.title}</strong><small>编号 {project.id.slice(0, 8)}</small></span>
            <span><b>{project.progress}%</b><small>第 {project.revision} 次保存</small><ArrowRight size={16} /></span>
          </Link>
          <button type="button" className="project-delete" disabled={deleting === project.id} onClick={() => {
            if (!window.confirm(`确定删除《${project.title}》吗？项目记录会从列表移除，此操作不能撤销。`)) return;
            setDeleting(project.id); setError("");
            void api.deleteProject(project.id).then(() => setProjects((current) => current.filter((item) => item.id !== project.id))).catch((reason) => setError(reason instanceof Error ? reason.message : "项目删除失败")).finally(() => setDeleting(null));
          }}>{deleting === project.id ? <LoaderCircle className="spin" size={15} /> : <Trash2 size={15} />}删除</button>
        </article>)}
      </section>
      {!loading && !error && hasMore && <button type="button" className="button button-secondary project-load-more" disabled={loadingMore} onClick={() => {
        setLoadingMore(true); setError("");
        void api.projects(pageSize, projects.length)
          .then((items) => { setProjects((current) => [...current, ...items]); setHasMore(items.length === pageSize); })
          .catch((reason) => setError(reason instanceof Error ? reason.message : "读取更多项目失败"))
          .finally(() => setLoadingMore(false));
      }}>{loadingMore ? <><LoaderCircle className="spin" size={15} />正在读取……</> : "加载更多项目"}</button>}
    </main>
  );
}
