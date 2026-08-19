# 《漆问》知识库 V2 重构说明（给 Codex）

## 目标
当前知识库过薄，不能只保留“标题 + 一句话简介”。请使用同目录 `QIWEN_漆艺知识库V2.json` 重建正式知识库。

当前种子库共 **44 条高密度知识单元**，覆盖材料、采漆生态、制漆准备、胎体基层、基础工艺、装饰技法、地域传统、历史、文化真实性、安全和保存保护。

## 每条知识卡必须支持
- 核心解释
- 核心事实
- 为什么：因果关系
- 关键动作
- 常见误解
- 学习目标
- 相关来源
- AI教育插图
- “用于游戏创作”

## Agent 使用约束
`game_affordances` 不得在玩家独立构思前直接显示成“推荐玩法”。它只用于：
1. 检查玩家玩法是否真实体现知识；
2. 追问遗漏的因果/动作；
3. 指出文化误导；
4. 玩家主动请求灵感时提供候选方向。

必须继续遵守：
**玩家先提出，Agent再追问；玩家决定，Agent辅助。**

## 数据库迁移
如果当前 schema 不足，增加：
- `core_facts JSON`
- `cause_effect_relations JSON`
- `key_actions JSON`
- `common_misconceptions JSON`
- `game_affordances JSON`
- `learning_objectives JSON`
- `references JSON`
- `image_prompt_zh TEXT`
- `verification TEXT`
- `expert_verified BOOLEAN DEFAULT FALSE`

不要破坏旧 Project 对 KnowledgeEntry 的引用；做 migration。

## 前台知识详情页
不要只显示摘要。推荐结构：
1. 标题与分类
2. 2–4句核心说明
3. “你需要知道的事实”
4. “为什么会这样”
5. “工艺中要做什么”
6. “常见误解”
7. 来源
8. AI示意图
9. 相关知识
10. `用这个知识创作游戏`

## AI 图片
使用每条记录的 `image_prompt_zh` 调图像 Provider。
硬性规则：
- 显示“AI生成示意图”
- 不得伪装成馆藏照片/考古照片/历史档案
- 如果后续需要真实文物图，研究者人工替换为有授权的博物馆来源

## RAG
RAG 不要只返回一个短 chunk。优先把一个完整知识单元的：
summary + core_facts + cause_effect_relations + key_actions + common_misconceptions
一起传给 Reflective Agent。

## 搜索分类
- 材料基础
- 采漆与生态
- 制漆与准备
- 胎体与基层
- 基础工艺
- 装饰技法
- 地域传统
- 历史
- 文化与使用
- 文化与真实性
- 安全
- 保存与保护

## 论文实验知识集
另建 `experimental_knowledge_set`，不要直接让实验参与者面对整个百科库。
实验条目从专家复核后的知识中选 6–8 个，满足：
- 非专业用户通常不了解
- 10分钟内可学习
- 有明确因果/条件
- 能产生多种玩法
- 能判断正确/错误机制
- 可以出迁移题

## 导入验收
完成后生成 `KNOWLEDGE_BASE_V2_REPORT.md`：
- 导入条目数
- 分类统计
- migration结果
- RAG抽样结果
- 5条完整前台知识详情截图
- AI图生成状态
- 待专家核验条目
- 当前仍缺失的扩展主题

禁止只汇报“知识库已更新”。
