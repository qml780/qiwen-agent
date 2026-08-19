import raw from "@/data/knowledge-v2.json";
import type { KnowledgeEntry } from "@/lib/domain";

const images: Record<string, string> = {
  "采漆与生态": "/curated/彩色卡通-漆林采集关卡.png",
  "基础工艺": "/curated/彩色卡通-漆艺工坊关卡.png",
  "装饰技法": "/curated/彩色卡通-漆艺工坊关卡.png",
  "材料基础": "/curated/彩色卡通-层漆碗道具.png",
};

export const knowledgeEntries: KnowledgeEntry[] = raw.entries.map((entry) => ({
  ...entry,
  english_title: "",
  full_text: entry.core_facts.join("\n\n"),
  image_url: images[entry.category] ?? "/curated/彩色卡通-漆艺学徒角色.png",
  steps: entry.key_actions,
  common_errors: entry.common_misconceptions,
  expert_notes: [],
  related_ids: [],
  source: entry.references.map((item) => item.title).join("；"),
  affordances: entry.game_affordances,
}));

export const knowledgeCategories = ["全部", ...Array.from(new Set(knowledgeEntries.map((entry) => entry.category)))];

export function findKnowledge(id: string) {
  return knowledgeEntries.find((entry) => entry.id === id);
}
