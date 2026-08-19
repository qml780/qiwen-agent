import json
from pathlib import Path

from .domain import KnowledgeEntry


LEGACY_KNOWLEDGE = [
    KnowledgeEntry(
        id="thin-layers",
        category="TECHNIQUE",
        title="薄髹与层积",
        english_title="Thin Coating & Layering",
        summary="漆器的深度不是一次覆盖，而是薄层反复髹涂、等待与打磨共同形成。",
        full_text="每一层大漆都应薄而均匀。漆层需要在合适温湿度下干燥，再经过打磨后进入下一层。层与层之间的时间、厚度和手势共同决定最终表面。",
        image_url="/demo/lacquer-bowl.png",
        steps=["处理胎体", "薄而均匀地髹涂", "荫干等待", "细磨表面", "重复层积"],
        key_actions=["控制厚度", "保持均匀", "判断干燥状态", "重复操作"],
        common_errors=["单层过厚导致皱缩", "未干透即打磨", "边缘积漆"],
        expert_notes=["光泽来自层次与工序，而不是一次性涂亮。", "等待不是空白，而是工艺的一部分。"],
        related_ids=["harvesting", "polishing"],
        source="QIWEN curated demo · user-provided materials · internal demo only",
        affordances=["重复节奏", "厚度控制", "等待窗口", "均匀度反馈"],
    ),
    KnowledgeEntry(
        id="harvesting",
        category="PROCESS",
        title="割漆与采集",
        english_title="Lacquer Harvesting",
        summary="从漆树取得生漆是一项受季节、时间与伤口尺度制约的工作。",
        full_text="采漆需要在合适的季节与时段进行。割口过深会伤树，过浅则难以取得足量漆液，工匠需要在产量与树木生长之间保持克制。",
        image_url="/demo/lacquer-forest.png",
        steps=["观察树龄与天气", "选择割口", "控制深浅", "等待漆液", "收集与封存"],
        key_actions=["观察", "轻割", "等待", "收集"],
        common_errors=["割口过深", "不合时令", "容器污染"],
        expert_notes=["采集是一种长期关系，不是一次性索取。"],
        related_ids=["thin-layers"],
        source="QIWEN curated demo · user-provided materials · internal demo only",
        affordances=["风险收益", "季节窗口", "资源克制", "精确操作"],
    ),
    KnowledgeEntry(
        id="polishing",
        category="TECHNIQUE",
        title="研磨与显光",
        english_title="Polishing & Revealing",
        summary="研磨既去除不平，也逐步揭示被层积包裹的纹理与光泽。",
        full_text="研磨使用由粗到细的材料与手势。压力、方向和次数影响表面，过度研磨会穿透漆层，不足则无法显出平整光泽。",
        image_url="/demo/lacquer-workshop.png",
        steps=["检查干燥", "粗磨找平", "清洁表面", "细磨显光", "检查层次"],
        key_actions=["调节压力", "改变方向", "观察反光", "及时停止"],
        common_errors=["局部磨穿", "磨料残留", "压力不均"],
        expert_notes=["好的研磨是一种逐渐显现，而不是快速抛亮。"],
        related_ids=["thin-layers"],
        source="QIWEN curated demo · user-provided materials · internal demo only",
        affordances=["压力控制", "隐藏信息揭示", "风险阈值", "由粗到细"],
    ),
]


def _load_v2() -> list[KnowledgeEntry]:
    payload = json.loads(Path(__file__).with_name("knowledge_v2.json").read_text(encoding="utf-8-sig"))
    image_by_category = {
        "采漆与生态": "/curated/彩色卡通-漆林采集关卡.png",
        "基础工艺": "/curated/彩色卡通-漆艺工坊关卡.png",
        "装饰技法": "/curated/彩色卡通-漆艺工坊关卡.png",
        "材料基础": "/curated/彩色卡通-层漆碗道具.png",
    }
    default_image = "/curated/彩色卡通-漆艺学徒角色.png"
    result: list[KnowledgeEntry] = []
    for item in payload["entries"]:
        result.append(KnowledgeEntry(
            **item,
            full_text="\n\n".join(item.get("core_facts", [])),
            image_url=image_by_category.get(item["category"], default_image),
            steps=item.get("key_actions", []),
            common_errors=item.get("common_misconceptions", []),
            source="；".join(ref["title"] for ref in item.get("references", [])),
            affordances=item.get("game_affordances", []),
        ))
    return result


KNOWLEDGE = _load_v2() + LEGACY_KNOWLEDGE


def get_knowledge(knowledge_id: str) -> KnowledgeEntry | None:
    return next((entry for entry in KNOWLEDGE if entry.id == knowledge_id), None)
