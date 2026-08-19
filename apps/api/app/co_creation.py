from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .domain import UnityChangePreviewRequest
from .models import AssetRow, UnityChangeRow


ACTION_LABELS = {
    "add_asset": "把已选资产加入场景",
    "adjust_asset": "调整场景资产",
    "request_interaction": "为资产配置交互",
    "undo": "撤销到检查点",
}
TEMPLATE_LABELS = {
    "simulation-layering": "模拟·薄髹层积",
    "timing-polish": "时机·推光节律",
    "collection-materials": "收集·材料辨识",
    "puzzle-process": "谜题·工序排序",
    "target-lacquer-drops": "目标·纹样点漆",
    "topdown-dodge": "动作·俯视角躲避",
}


def _safe_csharp_text(value: str) -> str:
    return value.replace("\\", " ").replace('"', "'").replace("\r", " ").replace("\n", " ")[:300]


def serialize_change(row: UnityChangeRow) -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "asset_id": row.asset_id,
        "action": row.action,
        "action_label": ACTION_LABELS.get(row.action, row.action),
        "status": row.status,
        "request": row.request_payload,
        "preview": row.preview_payload,
        "receipt": row.receipt_payload,
        "checkpoint_path": row.checkpoint_path,
        "created_at": row.created_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        "undone_at": row.undone_at.isoformat() if row.undone_at else None,
    }


async def create_change_preview(session: AsyncSession, project_id: str, request: UnityChangePreviewRequest) -> UnityChangeRow:
    change_id = str(uuid4())
    asset = await session.get(AssetRow, request.asset_id) if request.asset_id else None
    valid_game_asset = asset is not None and (asset.type == "3D" or (asset.type == "IMAGE" and asset.metadata_json.get("artifact") == "3d"))
    if request.action == "add_asset" and not valid_game_asset:
        raise ValueError("加入场景必须选择一个已批准的二维或三维资产")
    if asset and asset.project_id not in {None, project_id}:
        raise ValueError("所选资产不属于当前项目")
    if request.action == "request_interaction" and not request.template_id:
        raise ValueError("请求交互必须选择一个已测试模板")

    source = ""
    component = ""
    if request.action == "request_interaction":
        class_name = f"CoCreationInteraction_{change_id.replace('-', '_')}"
        interaction = _safe_csharp_text(request.interaction or "按已批准模板响应玩家输入")
        source = (
            "using UnityEngine;\n\n"
            "namespace QIWEN.Generated\n{\n"
            f"    public sealed class {class_name} : MonoBehaviour\n    {{\n"
            f"        [SerializeField] private string interaction = \"{interaction}\";\n"
            "        public string Interaction => interaction;\n"
            "    }\n}\n"
        )
        component = request.template_id or ""

    transform = request.transform.model_dump(mode="json")
    request_payload = {
        "assetId": request.asset_id,
        "assetName": asset.name if asset else None,
        "assetHash": asset.sha256 if asset else None,
        "assetType": asset.type if asset else None,
        "objectName": request.object_name,
        "position": transform["position"],
        "rotation": transform["rotation"],
        "scale": transform["scale"],
        "templateId": request.template_id,
        "interaction": request.interaction,
    }
    differences = []
    if request.action == "add_asset":
        differences = [f"新增场景对象：{request.object_name}", f"资产：{asset.name}", f"固定资产哈希：{asset.sha256 or '未提供'}", f"位置：{transform['position']}；旋转：{transform['rotation']}；缩放：{transform['scale']}"]
    elif request.action == "adjust_asset":
        differences = [f"修改对象：{request.object_name}", f"位置改为：{transform['position']}", f"旋转改为：{transform['rotation']}", f"缩放改为：{transform['scale']}"]
    else:
        differences = [f"对象：{request.object_name}", f"添加已测试组件：{TEMPLATE_LABELS.get(component, component)}", "在受控生成区新增一个只读交互说明脚本", f"交互请求：{request.interaction or '按模板默认交互'}"]
    preview = {
        "title": ACTION_LABELS[request.action],
        "summary": "这是智能助手提议，尚未写入 Unity。批准后会先建立场景检查点。",
        "differences": differences,
        "generated_script": source,
        "generated_area": "Assets/QIWEN/Generated/CoCreation" if source else None,
        "undo_available_after_apply": True,
    }
    row = UnityChangeRow(
        id=change_id, project_id=project_id, asset_id=request.asset_id, action=request.action,
        status="preview", request_payload=request_payload, preview_payload=preview, receipt_payload={},
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def list_project_changes(session: AsyncSession, project_id: str) -> list[dict]:
    rows = (await session.scalars(select(UnityChangeRow).where(UnityChangeRow.project_id == project_id).order_by(UnityChangeRow.created_at.desc()))).all()
    return [serialize_change(row) for row in rows]


def bridge_payload(row: UnityChangeRow, unity_project_path: str) -> dict:
    request = row.request_payload
    return {
        "id": row.id,
        "projectId": row.project_id,
        "unityProjectPath": unity_project_path,
        "action": row.action,
        "assetId": row.asset_id,
        "assetPath": ("Assets/QIWEN/Input/game-art.png" if request.get("assetType") == "IMAGE" else "Assets/QIWEN/Input/lacquer-bowl.glb") if row.asset_id else None,
        "objectName": request["objectName"],
        "position": request["position"],
        "rotation": request["rotation"],
        "scale": request["scale"],
        "templateId": request.get("templateId"),
        "interaction": request.get("interaction"),
        "generatedScript": row.preview_payload.get("generated_script") or None,
    }


def undo_payload(row: UnityChangeRow, undo_id: str, unity_project_path: str) -> dict:
    receipt = row.receipt_payload
    return {
        "id": undo_id,
        "projectId": row.project_id,
        "unityProjectPath": unity_project_path,
        "action": "undo",
        "objectName": row.request_payload["objectName"],
        "checkpointPath": receipt.get("checkpointPath"),
        "originalScenePath": receipt.get("originalScenePath"),
        "generatedScriptPath": receipt.get("generatedScriptPath"),
    }
