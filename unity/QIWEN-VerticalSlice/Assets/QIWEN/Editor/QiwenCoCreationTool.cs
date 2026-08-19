using System;
using System.IO;
using System.Text.RegularExpressions;
using QIWEN.GameTemplates;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace QIWEN.Editor
{
    public static class QiwenCoCreationTool
    {
        private const string PendingPath = "QIWEN/CoCreation/pending.json";

        [Serializable]
        private sealed class ChangeRequest
        {
            public string id = "";
            public string projectId = "";
            public string action = "";
            public string assetId = "";
            public string assetPath = "";
            public string objectName = "";
            public float[] position = Array.Empty<float>();
            public float[] rotation = Array.Empty<float>();
            public float[] scale = Array.Empty<float>();
            public string templateId = "";
            public string interaction = "";
            public string generatedScript = "";
            public string generatedScriptPath = "";
            public string checkpointPath = "";
            public string originalScenePath = "";
        }

        [Serializable]
        private sealed class ChangeReceipt
        {
            public string id = "";
            public bool success;
            public string action = "";
            public string message = "";
            public string objectName = "";
            public string checkpointPath = "";
            public string originalScenePath = "";
            public string generatedScriptPath = "";
            public string time = "";
        }

        [MenuItem("漆问/共创/应用已批准变更")]
        public static void ApplyApprovedChange()
        {
            var request = ReadRequest();
            if (request == null) return;
            try
            {
                var scene = EditorSceneManager.GetActiveScene();
                if (!scene.IsValid() || string.IsNullOrWhiteSpace(scene.path))
                    scene = EditorSceneManager.OpenScene("Assets/QIWEN/Scenes/漆问最小切片.unity", OpenSceneMode.Single);
                EditorSceneManager.SaveScene(scene);
                var checkpointPath = $"Assets/QIWEN/Checkpoints/{request.id}.unity";
                Directory.CreateDirectory(Path.Combine(Application.dataPath, "QIWEN/Checkpoints"));
                AssetDatabase.DeleteAsset(checkpointPath);
                if (!AssetDatabase.CopyAsset(scene.path, checkpointPath)) throw new InvalidOperationException("无法建立场景检查点");

                var generatedPath = "";
                switch (request.action)
                {
                    case "add_asset": AddAsset(request); break;
                    case "adjust_asset": AdjustAsset(request); break;
                    case "request_interaction": generatedPath = AddInteraction(request); break;
                    default: throw new InvalidOperationException("不支持的共创动作");
                }
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                AssetDatabase.SaveAssets();
                WriteReceipt(request, true, "已应用玩家批准的 Unity 变更", checkpointPath, scene.path, generatedPath);
            }
            catch (Exception error)
            {
                WriteReceipt(request, false, error.Message, "", "", "");
                Debug.LogError($"[漆问共创] {error}");
            }
        }

        [MenuItem("漆问/共创/撤销到检查点")]
        public static void UndoToCheckpoint()
        {
            var request = ReadRequest();
            if (request == null) return;
            try
            {
                if (string.IsNullOrWhiteSpace(request.checkpointPath) || string.IsNullOrWhiteSpace(request.originalScenePath))
                    throw new InvalidOperationException("撤销请求缺少检查点路径");
                var checkpointAbsolute = ToAbsoluteAssetPath(request.checkpointPath);
                var originalAbsolute = ToAbsoluteAssetPath(request.originalScenePath);
                if (!File.Exists(checkpointAbsolute)) throw new FileNotFoundException("找不到场景检查点", checkpointAbsolute);
                File.Copy(checkpointAbsolute, originalAbsolute, true);
                AssetDatabase.ImportAsset(request.originalScenePath, ImportAssetOptions.ForceUpdate);
                EditorSceneManager.OpenScene(request.originalScenePath, OpenSceneMode.Single);
                if (!string.IsNullOrWhiteSpace(request.generatedScriptPath) && request.generatedScriptPath.StartsWith("Assets/QIWEN/Generated/CoCreation/", StringComparison.Ordinal))
                    AssetDatabase.DeleteAsset(request.generatedScriptPath);
                WriteReceipt(request, true, "已撤销到变更前检查点", request.checkpointPath, request.originalScenePath, "");
            }
            catch (Exception error)
            {
                WriteReceipt(request, false, error.Message, request.checkpointPath, request.originalScenePath, "");
                Debug.LogError($"[漆问共创] {error}");
            }
        }

        private static void AddAsset(ChangeRequest request)
        {
            var source = GameObject.Find("漆碗");
            GameObject instance;
            if (source != null) instance = UnityEngine.Object.Instantiate(source);
            else
            {
                instance = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                instance.GetComponent<Renderer>().sharedMaterial = new Material(Shader.Find("Standard")) { color = Color.black };
            }
            instance.name = request.objectName;
            ApplyTransform(instance.transform, request);
        }

        private static void AdjustAsset(ChangeRequest request)
        {
            var target = GameObject.Find(request.objectName);
            if (target == null) throw new InvalidOperationException($"场景中找不到对象：{request.objectName}");
            ApplyTransform(target.transform, request);
        }

        private static string AddInteraction(ChangeRequest request)
        {
            var target = GameObject.Find(request.objectName);
            if (target == null) throw new InvalidOperationException($"场景中找不到对象：{request.objectName}");
            var type = request.templateId switch
            {
                "simulation-layering" => typeof(LayeringSimulationTemplate),
                "timing-polish" => typeof(RhythmTimingTemplate),
                "collection-materials" => typeof(CollectionTemplate),
                "puzzle-process" => typeof(SequencePuzzleTemplate),
                "target-lacquer-drops" => typeof(SimpleTargetTemplate),
                "topdown-dodge" => typeof(QIWEN.Runtime.LacquerDodgeGame),
                _ => throw new InvalidOperationException("交互模板不在允许列表中")
            };
            if (target.GetComponent(type) == null) target.AddComponent(type);
            if (string.IsNullOrWhiteSpace(request.generatedScript)) return "";
            var match = Regex.Match(request.generatedScript, @"public\s+sealed\s+class\s+([A-Za-z_][A-Za-z0-9_]*)");
            if (!match.Success) throw new InvalidOperationException("生成脚本缺少受控 public sealed class");
            var relativePath = $"Assets/QIWEN/Generated/CoCreation/{match.Groups[1].Value}.cs";
            Directory.CreateDirectory(Path.Combine(Application.dataPath, "QIWEN/Generated/CoCreation"));
            File.WriteAllText(ToAbsoluteAssetPath(relativePath), request.generatedScript);
            AssetDatabase.ImportAsset(relativePath, ImportAssetOptions.ForceSynchronousImport);
            return relativePath;
        }

        private static void ApplyTransform(Transform transform, ChangeRequest request)
        {
            if (request.position?.Length == 3) transform.position = new Vector3(request.position[0], request.position[1], request.position[2]);
            if (request.rotation?.Length == 3) transform.eulerAngles = new Vector3(request.rotation[0], request.rotation[1], request.rotation[2]);
            if (request.scale?.Length == 3) transform.localScale = new Vector3(request.scale[0], request.scale[1], request.scale[2]);
        }

        private static ChangeRequest ReadRequest()
        {
            var absolute = Path.Combine(Directory.GetParent(Application.dataPath)!.FullName, PendingPath);
            if (!File.Exists(absolute)) { Debug.LogError("[漆问共创] 找不到 pending.json"); return null; }
            return JsonUtility.FromJson<ChangeRequest>(File.ReadAllText(absolute));
        }

        private static void WriteReceipt(ChangeRequest request, bool success, string message, string checkpoint, string scene, string generated)
        {
            var root = Path.Combine(Directory.GetParent(Application.dataPath)!.FullName, "QIWEN/CoCreation/Receipts");
            Directory.CreateDirectory(root);
            var receipt = new ChangeReceipt { id = request.id, success = success, action = request.action, message = message, objectName = request.objectName, checkpointPath = checkpoint, originalScenePath = scene, generatedScriptPath = generated, time = DateTime.UtcNow.ToString("O") };
            File.WriteAllText(Path.Combine(root, $"{request.id}.json"), JsonUtility.ToJson(receipt, true));
            Debug.Log($"[漆问共创] {message}：{request.objectName}");
        }

        private static string ToAbsoluteAssetPath(string assetPath) => Path.Combine(Directory.GetParent(Application.dataPath)!.FullName, assetPath.Replace('/', Path.DirectorySeparatorChar));
    }
}
