# 项目状态机

顺序固定：

`knowledge_selection → concept_drafting → concept_review → visual_drafting → visual_review → 3d_drafting → 3d_review → music_drafting → music_review → logic_drafting → logic_review → ready_to_build`。

规则：草案生成只进入审阅，不自动批准；只有玩家批准当前版本才能进入下一阶段。重新打开上游阶段会创建或等待新版本，并使依赖它的下游批准失效。Unity 构建只接受 `ready_to_build` 且所有必要批准新鲜的项目。

Unity 变更状态为 `preview → applying → applied`，玩家也可从预览进入 `rejected`，从已应用进入 `undone`，异常进入 `failed`。试玩状态为 `playing → feedback → revision_preview → replaying → completed`；修订预览创建逻辑新版本并移除旧批准。

