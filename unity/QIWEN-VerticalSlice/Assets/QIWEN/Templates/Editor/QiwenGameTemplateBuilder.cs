using System;
using System.IO;
using QIWEN.GameTemplates;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace QIWEN.Editor
{
    public static class QiwenGameTemplateBuilder
    {
        private const string Root = "Assets/QIWEN/Templates";

        [Serializable]
        private sealed class BuildReceipt
        {
            public string templateId = "";
            public string displayName = "";
            public string prefabPath = "";
            public string scenePath = "";
            public string definitionPath = "";
            public string componentType = "";
            public string inputMode = "";
            public string winCondition = "";
            public string culturalAffordance = "";
            public bool success;
            public string time = "";
        }

        [MenuItem("漆问/游戏模板/01 模拟·薄髹层积")]
        public static void BuildSimulation() => Build<LayeringSimulationTemplate>(
            "simulation-layering", "模拟·薄髹层积", "点击髹涂，准备表面，必要时打磨缺陷", "完成三层且表面缺陷为零",
            "薄髹需要逐层涂布、阴干与打磨；层数增加会积累时间与表面风险。");

        [MenuItem("漆问/游戏模板/02 时机·推光节律")]
        public static void BuildTiming() => Build<RhythmTimingTemplate>(
            "timing-polish", "时机·推光节律", "在节拍中心按下确认", "连续命中三个有效节拍",
            "顺着稳定节律推光，动作过早或过晚都会破坏漆面均匀度。");

        [MenuItem("漆问/游戏模板/03 收集·材料辨识")]
        public static void BuildCollection() => Build<CollectionTemplate>(
            "collection-materials", "收集·材料辨识", "移动并触碰材料样本", "收集三种不重复材料",
            "收集漆液、胎体与研磨材料，并辨认每种材料在工序中的用途。");

        [MenuItem("漆问/游戏模板/04 谜题·工序排序")]
        public static void BuildPuzzle() => Build<SequencePuzzleTemplate>(
            "puzzle-process", "谜题·工序排序", "依次选择工序卡片", "按清理、底漆、阴干、打磨完成排序",
            "漆艺工序有先后依赖；玩家通过排列工序理解为何不能跳过阴干与打磨。");

        [MenuItem("漆问/游戏模板/05 目标·纹样点漆")]
        public static void BuildTarget() => Build<SimpleTargetTemplate>(
            "target-lacquer-drops", "目标·纹样点漆", "瞄准纹样位置并用已蘸漆的刷具确认", "完成三个不重复纹样落点",
            "以蘸漆刷点中指定纹样位置，强调控制落点与用漆节制，不使用暴力叙事。");

        [MenuItem("漆问/游戏模板/06 动作·俯视角躲避")]
        public static void BuildDodge() => Build<QIWEN.Runtime.LacquerDodgeGame>(
            "topdown-dodge", "动作·俯视角躲避", "方向键或 WASD 移动，避开落下的漆滴", "保持耐久并坚持到倒计时结束",
            "在漆艺作坊中避开未固化漆液，理解规范操作和污染防护。");

        private static void Build<T>(string id, string displayName, string inputMode, string winCondition, string affordance)
            where T : MonoBehaviour, IGameTemplateDemo
        {
            Directory.CreateDirectory(Path.Combine(Application.dataPath, "QIWEN/Templates/Definitions"));
            Directory.CreateDirectory(Path.Combine(Application.dataPath, "QIWEN/Templates/Prefabs"));
            Directory.CreateDirectory(Path.Combine(Application.dataPath, "QIWEN/Templates/Scenes"));
            Directory.CreateDirectory(Path.Combine(Directory.GetParent(Application.dataPath)!.FullName, "QIWEN/TemplateReceipts"));

            var definitionPath = $"{Root}/Definitions/{id}.asset";
            var definition = AssetDatabase.LoadAssetAtPath<GameTemplateDefinition>(definitionPath);
            if (definition == null)
            {
                definition = ScriptableObject.CreateInstance<GameTemplateDefinition>();
                AssetDatabase.CreateAsset(definition, definitionPath);
            }
            definition.templateId = id;
            definition.displayName = displayName;
            definition.inputMode = inputMode;
            definition.winCondition = winCondition;
            definition.culturalAffordance = affordance;
            definition.componentType = typeof(T).FullName;
            EditorUtility.SetDirty(definition);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = new GameObject(displayName);
            root.AddComponent<T>();
            CreateBlackWhiteDemoGeometry(root.transform, id);
            CreateCameraAndLight();

            var prefabPath = $"{Root}/Prefabs/{id}.prefab";
            PrefabUtility.SaveAsPrefabAssetAndConnect(root, prefabPath, InteractionMode.AutomatedAction);
            var scenePath = $"{Root}/Scenes/{displayName}.unity";
            EditorSceneManager.SaveScene(scene, scenePath);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            var receipt = new BuildReceipt
            {
                templateId = id, displayName = displayName, prefabPath = prefabPath, scenePath = scenePath,
                definitionPath = definitionPath, componentType = typeof(T).FullName, inputMode = inputMode,
                winCondition = winCondition, culturalAffordance = affordance, success = true,
                time = DateTime.UtcNow.ToString("O")
            };
            File.WriteAllText(Path.Combine(Directory.GetParent(Application.dataPath)!.FullName, $"QIWEN/TemplateReceipts/{id}.json"), JsonUtility.ToJson(receipt, true));
            Debug.Log($"[漆问模板] 已创建：{displayName}；场景 {scenePath}；预制体 {prefabPath}");
        }

        private static void CreateBlackWhiteDemoGeometry(Transform parent, string id)
        {
            var floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            floor.name = "黑色演示台";
            floor.transform.SetParent(parent);
            floor.transform.localPosition = new Vector3(0, -0.55f, 0);
            floor.transform.localScale = new Vector3(6, 0.25f, 6);
            var floorMaterial = new Material(Shader.Find("Standard")) { color = Color.black };
            floor.GetComponent<Renderer>().sharedMaterial = floorMaterial;

            var count = id == "puzzle-process" ? 4 : 3;
            for (var index = 0; index < count; index += 1)
            {
                var marker = GameObject.CreatePrimitive(index % 2 == 0 ? PrimitiveType.Sphere : PrimitiveType.Cylinder);
                marker.name = $"白色交互标记_{index + 1}";
                marker.transform.SetParent(parent);
                marker.transform.localPosition = new Vector3((index - (count - 1) / 2f) * 1.4f, 0.2f, 0);
                marker.transform.localScale = Vector3.one * 0.65f;
                marker.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard")) { color = Color.white };
            }
        }

        private static void CreateCameraAndLight()
        {
            var cameraObject = new GameObject("演示相机", typeof(Camera), typeof(AudioListener));
            cameraObject.tag = "MainCamera";
            cameraObject.transform.position = new Vector3(0, 4.5f, -7.5f);
            cameraObject.transform.rotation = Quaternion.Euler(22, 0, 0);
            cameraObject.GetComponent<Camera>().backgroundColor = Color.black;

            var lightObject = new GameObject("白色主光", typeof(Light));
            lightObject.transform.rotation = Quaternion.Euler(50, -30, 0);
            var light = lightObject.GetComponent<Light>();
            light.type = LightType.Directional;
            light.color = Color.white;
            light.intensity = 1.2f;
        }
    }
}
