# QIWEN《漆问》
## Human–Agent Cultural Game Co-Creation Studio
### MASTER DEVELOPMENT SPECIFICATION / CODEX EXECUTION INSTRUCTIONS

---

# 0. 你的身份与任务

你现在负责开发一个完整的研究型软件原型：

**QIWEN《漆问》——基于 Agent 的非遗知识游戏共创平台。**

这不是一个普通聊天机器人。

这不是一个“一句话自动生成游戏”的 AI Game Generator。

这也不是一个单纯的 Unity 插件。

它应该是一个：

**以 Web 技术构建的桌面级 AI 创作工作台，通过 Agent、生成式 AI 与 Unity 协作，让普通用户从文化知识出发，与 AI 共同设计并制作一个简单可玩的 Unity 游戏。**

整个系统必须坚持：

**Human-in-the-loop**

AI 可以：

- 分析
- 建议
- 生成
- 修改
- 编程
- 调用工具
- 操作 Unity
- 检查错误

但最终决定权始终属于玩家。

---

# 1. 在编写代码之前必须执行的工作

禁止收到本文件以后立刻开始大量编写代码。

首先建立：

`RESEARCH_NOTES.md`

研究当前可用的官方文档、GitHub 开源项目以及类似系统。

重点研究：

## 1.1 Unity AI / MCP

研究当前 Unity 官方：

- Unity MCP Server
- Unity AI
- Unity Editor automation
- MCP client connection
- Scene 操作
- GameObject 操作
- Component 操作
- Script creation
- Console / compilation error reading
- Play Mode
- Asset import
- Editor automation

目标不是重新发明 Unity 自动化协议。

优先使用当前稳定、官方或可靠维护的解决方案。

---

## 1.2 DeepSeek API

本项目语言模型统一使用：

`DeepSeek API`

当前优先考虑：

`deepseek-v4-pro`

复杂任务，例如：

- 游戏设计分析
- Knowledge–Mechanic Translation
- Unity 代码生成
- Debug
- Game Design Spec
- Agent planning

可使用 Pro。

普通任务，例如：

- 简单聊天
- UI辅助文本
- 简单总结

允许根据成本切换 Flash。

必须通过统一：

`LLMProvider`

调用。

禁止把具体模型名散落在整个项目代码中。

必须可以通过 `.env` 修改。

示例：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-pro
```

API Key 绝对禁止：

- 写死在源码
- 上传 GitHub
- 写进前端 bundle
- 暴露给浏览器

所有 DeepSeek 请求必须经过安全 Backend。

---

# 2. 产品核心定义

QIWEN 的核心不是：

“AI帮助用户生成游戏。”

而是：

**Agent 帮助非专业游戏创作者把文化知识转译为游戏机制，并通过持续的人机协作完成游戏。**

核心流程：

```text
KNOWLEDGE
↓
PLAYER IDEA
↓
DISCUSSION
↓
INTERPRETATION
↓
GAME MECHANIC
↓
PLAYER APPROVAL
↓
ASSET CREATION
↓
PLAYER APPROVAL
↓
UNITY BUILD
↓
PLAYER PARTICIPATION
↓
PLAYTEST
↓
REVISION
↓
FINISH
```

研究核心：

**Knowledge → Mechanic Translation**

---

# 3. 最重要的系统原则

以下原则属于 HARD REQUIREMENTS。

不得自行删除或修改。

## Principle 01 — Player First

Agent 不应该一开始替玩家决定游戏。

正确：

```text
玩家先表达自己的游戏想法
↓
Agent理解
↓
Agent提出意见
↓
玩家接受 / 拒绝 / 修改
↓
继续讨论
```

错误：

```text
Agent自动给3个游戏
↓
玩家只能选ABC
```

ABC 方案可以作为辅助，但绝不能成为唯一交互模式。

玩家必须始终拥有自由文本输入。

---

# 4. Human Approval Gate

这是整个系统最重要的交互机制之一。

任何关键阶段完成以后：

**必须暂停。**

必须等待玩家确认。

未经玩家明确确认：

**禁止进入下一阶段。**

主要 Approval Gates：

```text
Knowledge Selected
        ↓
Game Concept Approval
        ↓
Visual Approval
        ↓
3D Asset Approval
        ↓
Music Approval
        ↓
Game Logic Approval
        ↓
Ready to Build Approval
        ↓
Unity Build
        ↓
Playtest Approval
        ↓
Final Approval
```

必须在 Backend 状态机中真正限制。

不能只是前端做一个假的 Confirm 按钮。

---

# 5. Knowledge Base

知识库不是玩家使用时实时联网搜索生成。

必须提前建立。

这是：

**PREBUILT CURATED KNOWLEDGE BASE**

玩家使用产品时：

禁止为了回答基础漆艺知识而默认实时搜索互联网。

知识来源由研究者提前收集：

- 学术论文
- 专业书籍
- 博物馆资料
- 非遗机构资料
- 官方文化资料
- 专业行业资料
- 漆艺从业者
- 漆艺制作人
- 非遗传承人访谈
- 专家访谈
- 研究团队整理资料

第一阶段请先建立知识库 Schema 和后台录入能力。

不要擅自大量抓取互联网并把未经验证的信息直接作为正式知识。

---

# 6. Knowledge Schema

每条 Knowledge Entry 至少包含：

```text
id
title
short_title

category
subcategory

summary
full_content

historical_context

materials[]

tools[]

process_steps[]

key_actions[]

physical_properties[]

cause_effect_relations[]

common_mistakes[]

expert_tips[]

sensory_features[]
    visual
    sound
    touch
    timing

learning_points[]

game_affordances[]

related_knowledge_ids[]

images[]

references[]

expert_verified

created_at
updated_at
```

---

# 7. Game Affordance Layer

知识库不能只是百科。

必须建立：

**Game Affordance Layer**

例如：

```text
Knowledge:
多次薄涂

Key Actions:
- 刷
- 刮
- 等待
- 检查
- 重复

Variables:
- 厚度
- 均匀程度
- 时间
- 次数

Failure:
- 太厚
- 不均匀
- 未干再次操作

Possible Mechanics:
- Precision
- Timing
- Rhythm
- Simulation
- Resource Management

Learning Objective:
理解“薄、匀、反复”的工艺逻辑
```

Agent 后续游戏设计必须优先使用这些结构化知识。

---

# 8. Knowledge Library UI

Knowledge Library 必须是完整前台页面。

建议分类：

```text
PROCESS
MATERIAL
TECHNIQUE
TOOLS
OBJECT
HISTORY
REGION
CULTURE
```

知识卡片必须可浏览。

点击进入 Knowledge Detail。

Knowledge Detail 展示：

- 标题
- 简介
- 图片
- 完整知识
- 工艺步骤
- 关键动作
- 常见错误
- 专家经验
- 相关知识
- 来源

页面底部：

`CREATE WITH THIS KNOWLEDGE`

点击以后创建 Project。

---

# 9. Project

每一次游戏创作都是独立 Project。

Project 至少保存：

```text
project_id
user_id

title

selected_knowledge_id

current_stage

game_concept

game_design_spec

conversation_history

assets

approvals

versions

unity_project

activity_log

created_at
updated_at
```

刷新网页后：

**任何项目数据都不能消失。**

---

# 10. Co-Creation Studio

这是产品最重要页面。

Desktop First。

建议基本布局：

```text
┌─────────────────────────────────────────────────────────┐
│ QIWEN     Knowledge  Concept  Visual  3D  Audio  Build │
├──────────────┬─────────────────────────┬────────────────┤
│              │                         │                │
│ ASSET        │                         │ CO-CREATOR     │
│ LIBRARY      │       WORKSPACE         │                │
│              │                         │ Agent Chat     │
│ Images       │                         │                │
│ 3D           │                         │                │
│ Audio        │                         │                │
│ UI           │                         │                │
│              │                         │                │
├──────────────┴─────────────────────────┴────────────────┤
│ PROJECT PROGRESS                                       │
│ ✓ Knowledge ✓ Concept ● Visual ○ 3D ○ Audio ○ Build   │
└─────────────────────────────────────────────────────────┘
```

聊天不是主界面。

Workspace 才是主界面。

Agent 是右侧：

**Co-Creator Panel**

---

# 11. Agent Conversation

用户选择知识以后：

必须先允许玩家自由输入自己的想法。

例如：

```text
“我想把这个知识做成一个节奏游戏，
每完成一次髹漆就增加一层音乐。”
```

Agent 再分析。

Agent 的角色：

不是老师。

不是命令者。

不是自动生成机器。

而是：

**Game Co-Designer**

Agent 应该：

1. 理解玩家想法
2. 找出和知识点对应的部分
3. 指出可能的问题
4. 提供改进建议
5. 询问玩家意见
6. 根据玩家反馈修改
7. 保留玩家原始创意
8. 不强迫接受 AI 建议

---

# 12. Agent 可以被拒绝

每条重要 Agent 建议必须允许：

```text
Accept
Reject
Modify
Discuss
```

玩家可以直接说：

```text
“这个建议不好。”
```

Agent必须：

理解原因 → 修改建议。

不得反复坚持原方案。

---

# 13. Game Concept

讨论达到一定成熟程度以后：

Agent可以提出：

`Generate Game Concept`

但仍需要玩家主动触发或同意。

生成：

```text
Game Name

Selected Knowledge

Genre

Player Fantasy

World

Learning Objective

Core Mechanic

Core Loop

Player Actions

Rules

Feedback

Failure Conditions

Win Condition

Level Structure

Estimated Duration
```

展示成可视化 Game Concept Canvas。

不能只显示 JSON。

---

# 14. Knowledge–Mechanic Alignment

生成 Concept 后执行一次：

**Knowledge Alignment Check**

例如：

```text
KNOWLEDGE
多次薄涂

GAME MECHANIC
玩家需要控制每层厚度并重复操作

ALIGNMENT

✓ Thin Layer
✓ Repetition
✓ Uniformity
✓ Waiting

Not represented:
○ Humidity

Alignment: HIGH
```

这只是建议。

不能阻止玩家继续。

玩家有最终决定权。

---

# 15. Game Concept Approval

提供：

```text
Continue Discussing

Edit

Save Version

Approve Concept
```

只有点击：

`Approve Concept`

Backend 才可以进入：

`visual`

状态。

---

# 16. Asset Generation Architecture

所有生成式能力必须使用：

**Provider Architecture**

禁止将具体第三方 API 写死到 UI 或业务逻辑。

必须建立：

```text
ImageProvider

ThreeDProvider

MusicProvider

LLMProvider
```

每种 Provider 至少有：

```text
MockProvider
RealProvider
```

---

# 17. 第一阶段禁止依赖真实生成 API

第一版必须做到：

**ZERO REAL GENERATIVE API REQUIRED**

也就是说没有任何外部 API Key 时：

完整流程依然能运行。

Mock Image Provider：

返回测试图片。

Mock 3D Provider：

返回测试 GLB。

Mock Music Provider：

返回测试 WAV / MP3。

Mock LLM：

如果 DeepSeek Key 尚未配置，允许使用预设对话或开发模式。

---

# 18. Visual Studio

进入 Visual Stage 后显示：

```text
VISUAL STUDIO
```

允许玩家输入：

- 风格描述
- 世界观
- 场景描述
- 角色描述
- UI描述
- 色彩描述

Agent 可以帮助优化 Prompt。

生成后：

必须展示结果。

例如：

```text
Image A
Image B
Image C
Image D
```

每张图片允许：

```text
Preview
Save
Regenerate
Edit Prompt
Generate Variation
Add to Project
Delete from Project
```

注意：

删除 Project 引用 ≠ 永久删除个人素材。

---

# 19. Visual Approval

视觉方向确定后：

`Approve Visual Direction`

才进入下一阶段。

---

# 20. 3D Studio

3D生成必须独立页面。

未来正式 Provider：

优先预留混元 3D。

支持：

```text
Text → 3D

Image → 3D

Multi-view → 3D
```

生成完成后：

必须通过 Web 3D Viewer 查看。

支持：

- Rotate
- Zoom
- Inspect
- Model metadata
- Texture preview

显示：

```text
File
Format
Polygon Count
Texture
Version
```

允许：

```text
Save
Regenerate
Generate Variation
Replace
Add to Project
```

未经玩家确认：

禁止自动进入 Unity。

---

# 21. Music Studio

Music Studio 必须提供：

- Prompt
- Mood
- Tempo
- Duration
- Loop
- Instrument / style

生成后：

必须可以在线试听。

播放器：

```text
Play
Pause
Seek
Volume
Loop
```

允许多个版本：

```text
BGM v1
BGM v2
BGM v3
```

玩家选择：

`Use in Project`

再点击：

`Approve Music`

才进入下一阶段。

---

# 22. Asset Library

Asset Library 是整个产品的核心功能之一。

必须始终可访问。

至少分：

```text
ALL
IMAGE
3D
AUDIO
UI
CODE
SCENE
```

---

# 23. 两级 Asset System

必须区分：

## Project Assets

当前项目正在使用。

## My Library

用户过去生成和保存的所有资产。

例如：

```text
MY LIBRARY

LacquerBowl_v1
LacquerBowl_v2
LacquerBrush
WorkshopMusic
Texture_03
```

旧项目生成的素材：

可以在新项目复用。

---

# 24. Asset Versioning

资产不得覆盖。

必须保存版本。

例如：

```text
Bowl
 ├─ v1
 ├─ v2
 ├─ v3
 └─ v4
```

玩家可以：

- 查看历史版本
- 恢复旧版本
- Add to Project
- Remove from Project

---

# 25. Project Progress

整个创作过程必须有常驻：

**PROJECT PROGRESS**

例如：

```text
PROJECT
一层之间

68%

01 Knowledge
✓ Confirmed

02 Concept
✓ Confirmed

03 Visual
✓ Confirmed

04 3D
✓ Confirmed

05 Music
● Waiting for approval

06 Logic
○ Not started

07 Unity
○ Not started

08 Playtest
○ Not started
```

---

# 26. 状态机

不要依赖前端字符串判断。

Backend 建立正式状态机。

推荐：

```text
knowledge_selection

concept_drafting
concept_review
concept_approved

visual_drafting
visual_review
visual_approved

3d_drafting
3d_review
3d_approved

music_drafting
music_review
music_approved

logic_drafting
logic_review
logic_approved

ready_to_build

unity_connecting
unity_building
unity_review

playtesting

revision

completed
```

---

# 27. Dependency Invalidations

如果玩家回到前面的阶段修改内容：

后续相关阶段必须失效。

例如：

已经完成 Unity。

玩家回去更换 3D Model。

系统提示：

```text
This change affects:

Unity Scene
Game Build
Playtest Results

These stages must be rebuilt.

Cancel

Update & Rebuild
```

然后：

```text
Unity
Needs Update

Playtest
Needs Update
```

---

# 28. Game Logic Approval

Unity 编程之前：

不要直接让 Agent 写代码。

先生成：

**Game Logic Specification**

例如：

```text
PLAYER

Mouse controls brush.

PAINTING

Brush movement affects coating.

Thickness > threshold
→ visual failure feedback.

Coverage > 90%
→ next layer.

ROUNDS

5 layers.

WIN

Complete 5 valid layers.

FAIL

3 invalid coatings.
```

展示给玩家。

玩家可以：

```text
Discuss
Edit
Approve Logic
```

只有：

`Approve Logic`

以后才能进入 Build。

---

# 29. Ready to Build

Unity Build 前必须出现 Summary：

```text
READY TO BUILD

Knowledge
✓ Approved

Game Concept
✓ Approved

Visual
✓ Approved

3D Assets
✓ 4 selected

Music
✓ Approved

Game Logic
✓ Approved

Unity
Ready
```

按钮：

```text
Back to Edit

BUILD IN UNITY
```

必须由玩家点击。

Agent不得自动 Build。

---

# 30. Unity Architecture

不要假装网页本身可以任意控制本地 Unity。

建立：

**QIWEN Local Bridge**

结构：

```text
QIWEN Studio
        ↓
Backend / Local Communication
        ↓
QIWEN Local Bridge
        ↓
Unity MCP
        ↓
Unity Editor
```

---

# 31. Unity 必须可见

重要：

Unity Editor 必须以玩家可见方式运行。

禁止把主要流程设计成：

Headless Unity。

玩家点击：

`BUILD IN UNITY`

以后：

应该能够真实打开本地 Unity Editor。

玩家应该看到 Agent 正在：

- 创建 Scene
- 创建 GameObject
- 导入 Asset
- 添加 Component
- 创建 Script
- 配置 Audio
- 设置 Collider
- 设置 Camera
- 运行 Play Mode

---

# 32. Unity Agent 不应该完全替代玩家

目标不是：

AI 100% 自动生成完整游戏。

目标是：

**AI搭建基础结构 + 玩家参与组装和决策。**

Agent负责：

- Project structure
- Scene
- GameManager
- Player
- Camera
- Basic UI
- Logic scripts
- Collider
- Trigger
- Audio setup
- Common interactions

玩家可以：

- 选择素材
- 拖入素材
- 更换素材
- 调整位置
- 调整大小
- 决定交互对象
- 修改玩法
- 请求 Agent 改代码

---

# 33. Unity Interaction Example

玩家把：

`LacquerBowl.glb`

加入 Scene。

Agent可以询问：

```text
Do you want this object to be interactive?

Add Painting Interaction

Static Decoration

Custom
```

如果玩家选择：

`Painting Interaction`

Agent再：

- 添加 Collider
- 添加 Interaction Component
- 绑定 Painting Script
- 配置参数

---

# 34. Unity Game Templates

第一版禁止支持“任何游戏”。

先建立有限 Template System。

MVP建议：

```text
01 Interaction / Simulation

02 Click / Timing

03 Collection / Exploration

04 Simple Puzzle

05 Simple Shooting / Target Interaction
```

Game Design Agent 根据玩法：

推荐 Template。

玩家确认。

然后 Agent 基于 Template 修改。

不要从空项目无限自由生成。

---

# 35. Template Structure

每个 Template 应至少包含：

```text
Template ID

Supported Mechanics

Scene Base

Player Controller

Camera

GameManager

UI

Input

Win Condition Interface

Fail Condition Interface

Interaction Interface

Audio Manager

Save Config
```

---

# 36. DeepSeek 与 Unity 的关系

DeepSeek：

负责：

- Reasoning
- Planning
- Dialogue
- Game Design
- Code generation
- Code modification
- Error analysis

Unity MCP：

负责：

- 实际操作 Unity Editor

正确：

```text
DeepSeek
↓
Agent Orchestrator
↓
Tool Call
↓
Unity MCP
↓
Unity Editor
```

错误：

```text
DeepSeek API
↓
Unity
```

必须存在 Tool / Execution Layer。

---

# 37. Unity Code Generation

所有 C# 代码由 DeepSeek 生成或辅助修改。

但是代码生成必须有：

```text
Plan
↓
Generate
↓
Write
↓
Compile
↓
Read Console
↓
Fix
↓
Compile Again
↓
Play Test
```

不能：

Generate → Assume Success。

---

# 38. Unity Build Monitor

Web / Desktop UI 必须提供：

**BUILD MONITOR**

例如：

```text
BUILDING GAME

72%

✓ Unity Connected

✓ Project Opened

✓ Scene Created

✓ Assets Imported

✓ Player Created

✓ Camera Created

● Generating PaintingController.cs

○ Configure Audio

○ Compile

○ Playtest
```

---

# 39. Agent Action Log

玩家必须能够查看：

```text
14:21:03
Connected to Unity

14:21:08
Created MainScene

14:21:12
Imported LacquerBowl.glb

14:21:16
Created PaintingController.cs

14:21:20
Compilation Error

14:21:27
Fixing CS0246

14:21:35
Compilation Successful
```

不要显示模型内部思维链。

只显示：

**可观察的动作、状态和结果。**

---

# 40. Error Visibility

如果失败：

绝对禁止假装成功。

显示：

```text
BUILD ISSUE

PaintingController.cs failed to compile.

Agent is attempting repair.

View Error
```

如果多次修复失败：

```text
Automatic repair failed.

Open in Unity

Ask Agent

Retry
```

玩家必须可以人工接管。

---

# 41. Playtest

Build完成后：

必须进入 Playtest。

允许：

```text
Play in Unity

Restart

Report Issue

Ask Agent to Modify
```

玩家可以说：

```text
“刷漆速度太快。”

“这个失败条件太严格。”

“音乐声音太大。”

“我想把这个模型换掉。”
```

Agent根据反馈：

修改参数 / 代码 / Scene。

---

# 42. Final Approval

只有玩家点击：

`FINISH PROJECT`

项目才能进入：

`completed`

Agent不能自己判断完成。

---

# 43. Activity Log

必须保存整个共创过程。

记录：

```text
PLAYER_IDEA

AGENT_SUGGESTION

PLAYER_REJECT

PLAYER_ACCEPT

PLAYER_MODIFICATION

CONCEPT_VERSION

ASSET_GENERATION

ASSET_SELECTION

ASSET_REJECTION

APPROVAL

UNITY_ACTION

PLAYTEST_FEEDBACK

FINAL_VERSION
```

---

# 44. Research Data

Activity Log 将来用于 Human–AI Co-Creation 研究。

因此需要能够匿名导出：

```text
Project Timeline

Conversation Events

Suggestion Acceptance Rate

Rejected Suggestions

Number of Iterations

Asset Generations

Asset Selection

Approval Events

Revision Events

Knowledge Alignment Versions

Game Design Versions
```

提供：

`Export Research Data`

MVP可输出 JSON / CSV。

---

# 45. UI DESIGN SYSTEM

整个产品必须采用：

**高级极简专业创作工具风格。**

参考的是视觉原则，不是复制：

- Figma
- Linear
- Arc
- Notion
- modern professional creative software
- professional 3D / design tools

---

# 46. 禁止的视觉风格

禁止：

- generic AI purple gradient
- 大面积蓝紫渐变
- 发光边框
- 满屏 AI 星星
- 卡通机器人头像
- 过度圆角
- 每一个内容都套 Card
- 过度阴影
- 赛博朋克
- Dashboard 模板感
- ChatGPT clone
- SaaS template look

---

# 47. UI原则

必须：

```text
Professional
Minimal
Editorial
Restrained
Precise
Calm
Creative-tool oriented
```

颜色：

主要使用：

```text
White
Off-white
Black
Dark Gray
Light Gray
```

文化内容、漆艺素材本身负责提供主要色彩。

可以使用非常克制的“大漆红 / 漆黑”作为品牌强调色，但不要大面积铺满。

---

# 48. Layout

Desktop First。

主要设计目标：

```text
1440 × 900
1920 × 1080
```

优先桌面。

移动端第一版只需要基本响应式。

不要为了手机牺牲桌面创作体验。

---

# 49. Typography

要求：

- 清晰
- 克制
- 高信息密度
- 明确层级
- 不使用夸张标题
- 不使用过多字体

UI文字必须适合中英文混排。

---

# 50. Motion

动画必须克制。

允许：

- panel transition
- progress transition
- asset loading
- subtle hover
- stage completion
- generation state

禁止：

- 大量漂浮元素
- 炫技粒子
- 过度 spring
- 过度 parallax

---

# 51. 产品信息架构

至少实现：

```text
Home

Knowledge Library

Knowledge Detail

Projects

Project Studio

Concept

Visual Studio

3D Studio

Music Studio

Logic

Build

Playtest

Asset Library

Settings
```

这些可以是独立 Route，也可以部分作为 Studio 内部 Workspace。

---

# 52. 推荐技术架构

优先考虑：

Frontend:

```text
Next.js
React
TypeScript
```

UI：

选择成熟、轻量、可维护方案。

不要为了视觉效果引入大量依赖。

---

Backend：

可以：

```text
FastAPI
```

或者在研究后提出更合理方案。

但必须解释选择理由。

---

Database：

推荐：

```text
PostgreSQL
```

知识检索需要向量能力时：

```text
pgvector
```

---

Storage：

开发环境：

```text
local storage directory
```

正式版本预留：

```text
S3-compatible object storage
```

---

# 53. 3D Viewer

Web端使用成熟 WebGL 3D Viewer。

优先考虑：

Three.js / React Three Fiber 等成熟方案。

不要自己编写底层 renderer。

---

# 54. API Provider Interface

至少建立：

```text
LLMProvider

ImageGenerationProvider

ThreeDGenerationProvider

MusicGenerationProvider
```

业务逻辑禁止直接调用供应商。

例如：

错误：

```text
VisualStudio
→ Hunyuan / XXX API
```

正确：

```text
VisualStudio
→ ImageGenerationService
→ ImageProvider
```

---

# 55. API 缺失处理

如果 Key 不存在：

系统不得崩溃。

例如：

```text
HUNYUAN_API_KEY missing

Using MockThreeDProvider
```

UI显示：

`Demo Generation Mode`

而不是 Error。

---

# 56. Security

API Keys：

只存在 Backend / Local environment。

`.env`

必须加入：

`.gitignore`

提供：

`.env.example`

例如：

```env
DEEPSEEK_API_KEY=

IMAGE_PROVIDER=mock
IMAGE_API_KEY=

THREED_PROVIDER=mock
HUNYUAN_SECRET_ID=
HUNYUAN_SECRET_KEY=

MUSIC_PROVIDER=mock
MUSIC_API_KEY=
```

---

# 57. Data Model

至少建立：

```text
User

Project

KnowledgeEntry

KnowledgeReference

Conversation

Message

GameConcept

GameDesignVersion

Asset

AssetVersion

ProjectAsset

Approval

ProjectStage

ActivityEvent

UnitySession

UnityAction

PlaytestSession

ResearchExport
```

---

# 58. Approval Data

Approval不能只是 boolean。

保存：

```text
approval_id

project_id

stage

artifact_version

status

approved_by

approved_at

comment
```

这样以后可以知道：

玩家确认的是哪个版本。

---

# 59. Versioning

必须版本化：

```text
Game Concept

Game Design

Visual Direction

3D Assets

Music

Game Logic

Unity Build
```

不要覆盖历史版本。

---

# 60. Autosave

用户输入、聊天、设计修改：

自动保存。

避免刷新丢失。

显示非常克制的：

```text
Saved
Saving…
```

---

# 61. Development Strategy

严禁一次性开发整个系统。

必须采用 Milestone Development。

---

# MILESTONE 0
## Research & Architecture

只研究，不大规模开发。

输出：

```text
RESEARCH_NOTES.md

ARCHITECTURE.md

TECH_DECISIONS.md

RISKS.md
```

确认：

- Unity MCP 当前最佳方案
- DeepSeek API 当前接口
- 3D Provider方案
- Web → Local Bridge方案
- Unity版本
- 依赖
- 数据库
- Web 3D viewer

完成后再继续。

---

# MILESTONE 1
## UI + Full Mock Workflow

这是第一重要里程碑。

完全不使用真实 AI。

实现：

```text
Knowledge
↓
Select
↓
Player Idea
↓
Mock Agent
↓
Concept
↓
Approve
↓
Visual
↓
Approve
↓
3D
↓
Approve
↓
Music
↓
Approve
↓
Logic
↓
Approve
↓
Ready to Build
```

必须可以完整走通。

同时：

- 高级极简 UI
- Asset Library
- Progress
- Approval Gate
- Stage navigation

全部完成。

---

# MILESTONE 2
## Database + Persistence

实现：

- Projects
- Knowledge
- Chat
- Assets
- Versions
- Approvals
- Progress
- Activity Log

测试：

刷新浏览器。

关闭程序。

重新打开。

项目必须恢复。

---

# MILESTONE 3
## DeepSeek Agent

接入 DeepSeek。

实现真实：

```text
Player Idea
↕
Agent
```

支持多轮对话。

Conversation history必须由本系统持久化。

不要假设 API 会自动记忆历史。

实现：

- Knowledge Context
- System Prompt
- Game Design Agent
- Structured Game Concept
- Knowledge Alignment
- Logic Specification

---

# MILESTONE 4
## Asset Providers

逐个实现。

顺序：

```text
Image
↓
3D
↓
Music
```

每一个 Provider 独立完成测试。

没有 API Key：

Mock仍然工作。

---

# MILESTONE 5
## Unity Minimum Vertical Slice

不要马上做复杂游戏。

第一目标只有：

```text
点击 BUILD IN UNITY
↓
连接本地 Unity
↓
打开 / 创建 Project
↓
创建 Scene
↓
导入一个 GLB
↓
导入一个 Audio
↓
创建 GameObject
↓
生成一个 C# Script
↓
挂载 Script
↓
Compile
↓
进入 Play Mode
```

只有这条完全成功：

才允许继续。

---

# MILESTONE 6
## Unity Build Monitor

实现：

- connection status
- action status
- progress
- console
- error
- retry
- human takeover

Web界面实时看到 Unity 当前工作。

---

# MILESTONE 7
## Game Templates

逐个实现：

```text
Simulation

Timing

Collection

Puzzle

Simple Target/Shooting
```

不要一次完成全部。

每完成一个：

必须建立测试 Demo。

---

# MILESTONE 8
## Human–Agent Unity Co-Creation

实现：

玩家：

- 选择 Asset
- 加入 Scene
- 调整 Asset
- 请求交互

Agent：

- 添加组件
- 写脚本
- 修改代码
- 配置逻辑

---

# MILESTONE 9
## Playtest & Revision

实现：

```text
Play
↓
Feedback
↓
Agent Modify
↓
Compile
↓
Play Again
```

形成完整迭代。

---

# MILESTONE 10
## Research Logging

实现：

- Event logging
- Timeline
- Suggestion acceptance
- Revision count
- Approval history
- Export

---

# MILESTONE 11
## Polish

最后才做：

- animation
- empty states
- onboarding
- loading
- error UX
- accessibility
- visual polish
- performance
- responsive

禁止第一阶段花大量时间做动画。

---

# 62. 每个 Milestone 的完成规则

每完成一个 Milestone：

必须：

```text
1. Run
2. Test
3. Fix errors
4. Verify UI
5. Verify persistence
6. Write report
```

建立：

`MILESTONE_REPORT.md`

说明：

```text
Completed

Not Completed

Known Issues

Tests

Screenshots / Evidence

Next Step
```

未通过：

禁止假装完成。

---

# 63. Testing

至少包含：

## Unit Test

核心业务。

## Integration Test

Provider / Database。

## State Machine Test

确保未经 Approval 无法进入下一阶段。

## Unity Integration Test

确保操作真实执行。

## E2E

完整：

```text
Knowledge
→ Concept
→ Assets
→ Unity
→ Playtest
```

---

# 64. Human Approval Tests

必须专门测试：

```text
Can user skip Concept Approval?
→ NO

Can Agent automatically approve Visual?
→ NO

Can Unity Build start without Logic Approval?
→ NO

Can Agent publish automatically?
→ NO
```

---

# 65. Failure Recovery

必须考虑：

```text
DeepSeek timeout

Image generation failure

3D generation failure

Music generation failure

Unity not installed

Unity project missing

Unity MCP disconnected

Compile error

Asset missing

Corrupt GLB

Network interruption
```

任何一个失败：

都不能导致整个 Project 消失。

---

# 66. Unity Missing

如果玩家没有 Unity：

显示明确状态：

```text
Unity not detected.

Install / Configure Unity

Retry Connection
```

不要无限 Loading。

---

# 67. Local Bridge

Local Bridge 必须：

- 仅允许授权的本地操作
- 明确端口
- 验证连接
- 不开放危险远程控制
- 提供 health status
- 能重新连接 Unity

提供：

```text
Local Bridge
Connected

Unity
Connected

MCP
Connected
```

---

# 68. Agent System Architecture

前台只有：

**QIWEN Co-Creator**

后台允许多个逻辑角色：

```text
Knowledge Agent

Learning Design Agent

Game Design Agent

Asset Prompt Agent

Unity Builder Agent

Debug Agent

Alignment Agent
```

但不要在前台让玩家不停切换七个机器人。

对玩家来说：

始终是一个连续的 Co-Creator。

---

# 69. Agent Context

每次 Agent 回复需要根据当前 Stage 获取不同 Context。

例如 Concept：

```text
Selected Knowledge
Player Original Idea
Conversation
Current Game Concept
Previous Rejected Ideas
```

Visual：

```text
Approved Game Concept
Selected Knowledge
Visual Direction
Existing Assets
```

Unity：

```text
Approved Game Design
Approved Assets
Approved Logic
Unity State
Console
```

不要把所有信息无限塞进每一次 Prompt。

---

# 70. Player Original Idea

特别重要。

必须保存：

`original_player_idea`

不要在多轮 Agent 对话以后丢失。

研究时需要比较：

```text
Original Idea
vs
Final Game
```

---

# 71. Agent Suggestions

重要建议应该可以结构化记录：

```text
suggestion_id

agent_type

content

related_stage

player_response

accepted
rejected
modified

timestamp
```

---

# 72. Knowledge Alignment Research

每个 Concept Version 可以计算 / 生成：

```text
knowledge_elements

represented_elements

missing_elements

mechanic_mapping

alignment_explanation
```

不要把一个虚假的百分比当科学测量。

第一版优先使用：

```text
Strong
Moderate
Weak
```

并解释理由。

---

# 73. MVP Scope

第一版 MVP 的目标不是：

“生成任何3D游戏。”

而是：

**完整证明一个普通玩家可以从一个漆艺知识点开始，与 Agent 共创并完成一个简单可玩的 Unity 游戏。**

只要这个 Vertical Slice 成功：

MVP成立。

---

# 74. MVP Demo Knowledge

开发阶段至少准备 5–10 个示例漆艺知识。

例如不同类型：

```text
工艺流程

材料属性

操作技巧

常见错误

装饰技法
```

这些是 Demo 数据。

最终正式知识必须由研究者核验。

---

# 75. MVP Demo Assets

准备：

```text
3–5 images

3–5 GLB models

3 music tracks

basic UI

basic Unity templates
```

确保没有真实生成 API：

Demo仍然能跑。

---

# 76. 不要做的事情

第一阶段禁止：

```text
不要做社区

不要做复杂用户社交

不要做排行榜

不要做商业支付

不要做移动App

不要做多人联机

不要做开放世界

不要做复杂角色系统

不要做无限游戏类型

不要做完整Unity替代品

不要过度工程化
```

Community / Remix：

保留架构接口。

但不是第一版重点。

---

# 77. 产品最终形态

当前优先：

**Desktop-first Web Application**

开发成熟后允许：

Tauri / Electron

包装为：

**QIWEN Studio**

但第一阶段不要为了桌面打包拖慢核心流程。

优先：

```text
Web UI
+
Local Bridge
+
Unity
```

跑通。

---

# 78. 代码质量

要求：

- TypeScript strict
- clear modules
- no giant files
- no duplicated provider logic
- no hardcoded secrets
- no hidden magic constants
- reusable components
- clear naming
- documented interfaces

---

# 79. Documentation

项目根目录最终至少需要：

```text
README.md

AGENTS.md

MASTER_SPEC.md

ARCHITECTURE.md

PRODUCT_FLOW.md

UI_SPEC.md

KNOWLEDGE_SCHEMA.md

DATABASE_SCHEMA.md

STATE_MACHINE.md

AGENT_RULES.md

PROVIDER_INTERFACE.md

ASSET_SYSTEM.md

UNITY_ARCHITECTURE.md

LOCAL_BRIDGE.md

TEST_PLAN.md

RESEARCH_NOTES.md

TASKS.md
```

---

# 80. AGENTS.md

必须告诉后续 coding agent：

1. 产品是什么
2. Human Approval原则
3. 不允许自动跳阶段
4. Provider architecture
5. UI设计规范
6. Unity规则
7. DeepSeek规则
8. 测试要求
9. 不允许修改核心产品逻辑
10. 每次修改前先阅读相关文档

---

# 81. README

README 应包含：

```text
What is QIWEN?

Architecture

Requirements

Install

Environment Variables

Run Frontend

Run Backend

Run Local Bridge

Configure DeepSeek

Configure Unity MCP

Mock Mode

Real Provider Mode

Troubleshooting
```

---

# 82. UI QUALITY BAR

任何页面在完成前：

必须检查：

```text
Does it look like a professional creative tool?

Is the workspace dominant?

Is chat secondary?

Is whitespace sufficient?

Are there too many cards?

Are there unnecessary gradients?

Does the hierarchy feel calm?

Can the user immediately see:
Where am I?
What am I editing?
What is approved?
What happens next?
```

如果像普通 AI SaaS template：

重新设计。

---

# 83. 最终核心用户体验

用户应该能够：

```text
打开 QIWEN
↓
浏览漆艺知识
↓
理解一个知识点
↓
选择它
↓
先说自己的游戏想法
↓
与 Agent 讨论
↓
拒绝 / 接受 / 修改建议
↓
确认玩法
↓
生成视觉
↓
选择并确认
↓
生成3D
↓
旋转查看并确认
↓
生成音乐
↓
试听并确认
↓
确认游戏逻辑
↓
点击 Build in Unity
↓
本地 Unity 打开
↓
看到 Agent 搭建游戏
↓
使用自己保存的素材
↓
参与组装
↓
试玩
↓
提出修改
↓
Agent 修改
↓
再次试玩
↓
玩家确认完成
```

这是整个产品最重要的 E2E Test。

---

# 84. Definition of Done

项目不是在：

“页面都做出来”

的时候完成。

而是在真实完成以下闭环时完成：

```text
Knowledge
✓

Human-Agent Discussion
✓

Approval
✓

Assets
✓

Asset Library
✓

Game Logic
✓

Unity Connection
✓

Unity Scene Construction
✓

DeepSeek Code Generation
✓

Compilation
✓

Play Mode
✓

Human Revision
✓

Final Game
✓
```

---

# 85. 最重要的最后要求

不要为了展示 AI 能力而削弱人的参与。

这个项目的核心不是：

**How much can AI automate?**

而是：

**How can AI support people in transforming cultural knowledge into playable experiences?**

因此始终遵循：

```text
AI proposes.
Human decides.

AI generates.
Human selects.

AI builds.
Human participates.

AI checks.
Human approves.
```

QIWEN 应该让玩家感觉：

**“这是我和 Agent 一起做出来的游戏。”**

而不是：

**“这是 AI 替我生成的游戏。”**

---

# 86. 现在开始执行

不要立即开发全部功能。

首先只执行：

## PHASE 0

1. 阅读本 MASTER SPEC。
2. 检查当前项目目录。
3. 不删除已有用户项目文件。
4. 研究当前官方 Unity MCP 文档。
5. 研究当前 DeepSeek API。
6. 研究可靠的 Unity Agent / AI Game Generation GitHub 项目。
7. 研究 Local Bridge 最合理实现。
8. 确定 Unity 版本。
9. 确定 Web 技术架构。
10. 确定数据库。
11. 确定 Mock Provider Architecture。
12. 确定项目目录结构。
13. 写 `RESEARCH_NOTES.md`。
14. 写 `ARCHITECTURE.md`。
15. 写 `TECH_DECISIONS.md`。
16. 写 `TASKS.md`。
17. 输出风险与待确认问题。

PHASE 0 完成以后：

**不要自动进入大规模开发。**

先向我汇报：

```text
A. 你理解的产品是什么

B. 推荐技术架构

C. 找到哪些可以复用的项目 / 官方能力

D. Unity MCP方案

E. DeepSeek方案

F. Local Bridge方案

G. 数据库方案

H. Mock Provider方案

I. 项目目录结构

J. 开发里程碑

K. 技术风险

L. 哪些地方需要我做决定
```

等待我确认。

得到我的确认以后：

才开始 MILESTONE 1。

---

# FINAL RULE

如果某项技术能力不确定：

**先验证。**

不要假设。

如果某个 GitHub 项目已经解决：

**优先研究和复用成熟思想。**

如果某个 API 尚未提供：

**使用 Mock Provider。**

如果 Unity 操作失败：

**显示失败并允许人工接管。**

如果玩家没有确认：

**停止流程。**

如果 Agent 与玩家意见冲突：

**玩家拥有最终决定权。**