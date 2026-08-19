using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace QIWEN.Editor
{
    [InitializeOnLoad]
    public static class QiwenVerticalSliceBuilder
    {
        private const string MenuPath = "漆问/执行最小垂直切片";
        private const string ScenePath = "Assets/QIWEN/Scenes/漆问最小切片.unity";
        private const string ScriptPath = "Assets/QIWEN/Runtime/LacquerBowlExperience.cs";
        private const string StatePath = "QIWEN/State/vertical-slice-state.json";
        private const string ResultPath = "QIWEN/Results/vertical-slice.json";
        private const string EventPath = "QIWEN/Results/vertical-slice-events.jsonl";
        private static bool waitingForPlay;

        [Serializable]
        private sealed class SliceState
        {
            public string stage = "";
            public string startedAt = "";
        }

        [Serializable]
        private sealed class SliceResult
        {
            public bool success;
            public string stage = "";
            public string message = "";
            public string time = "";
        }

        [Serializable]
        private sealed class SliceEvent
        {
            public string stage = "";
            public int progress;
            public string message = "";
            public string level = "";
            public string time = "";
        }

        [Serializable]
        private sealed class BridgeRequest
        {
            public string projectId = "";
            public string runtimeScript = "";
            public string mode = "3d";
            public UnityBuildPlan buildPlan = new UnityBuildPlan();
        }

        [Serializable]
        private sealed class UnityBuildPlan
        {
            public int schema_version = 1;
            public string template_id = "simulation-layering";
            public string game_title = "漆问游戏";
            public string objective = "完成漆艺挑战";
            public string player_instructions = "按照画面提示操作";
            public int target_count = 3;
            public int time_limit_seconds = 60;
            public int failure_limit = 3;
            public float speed = 1f;
            public string[] sequence_steps = Array.Empty<string>();
            public string[] asset_roles = Array.Empty<string>();
            public string[] audio_cues = Array.Empty<string>();
        }

        [Serializable] private sealed class GltfRoot { public BufferView[] bufferViews = Array.Empty<BufferView>(); public Accessor[] accessors = Array.Empty<Accessor>(); public GltfMesh[] meshes = Array.Empty<GltfMesh>(); }
        [Serializable] private sealed class BufferView { public int byteOffset; public int byteLength; public int byteStride; }
        [Serializable] private sealed class Accessor { public int bufferView; public int byteOffset; public int componentType; public int count; public string type = ""; }
        [Serializable] private sealed class GltfMesh { public Primitive[] primitives = Array.Empty<Primitive>(); }
        [Serializable] private sealed class Primitive { public Attributes attributes = new Attributes(); public int indices = -1; }
        [Serializable] private sealed class Attributes { public int POSITION = -1; public int NORMAL = -1; }

        static QiwenVerticalSliceBuilder()
        {
            EditorApplication.delayCall += ResumeIfNeeded;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
            CompilationPipeline.assemblyCompilationFinished += OnAssemblyCompiled;
        }

        [MenuItem(MenuPath)]
        public static void Build()
        {
            try
            {
                ResetResults();
                var requestFile = Path.GetFullPath("QIWEN/Requests/pending.json");
                if (!File.Exists(requestFile)) throw new InvalidOperationException("找不到玩家发起的构建请求");
                var request = JsonUtility.FromJson<BridgeRequest>(File.ReadAllText(requestFile));
                if (request == null || string.IsNullOrWhiteSpace(request.runtimeScript)) throw new InvalidOperationException("构建请求缺少经安全校验的运行时脚本");
                if (request.buildPlan == null || string.IsNullOrWhiteSpace(request.buildPlan.template_id)) throw new InvalidOperationException("构建请求缺少玩家已批准的游戏构建计划");
                var twoD = string.Equals(request.mode, "2d", StringComparison.OrdinalIgnoreCase);
                WriteState("创建场景");
                Emit("创建场景", 30, twoD ? $"按已批准计划创建《{request.buildPlan.game_title}》；模板 {request.buildPlan.template_id}" : "创建三维漆艺场景", "信息");
                CreateBaseScene(request);
                Emit("导入画面", 40, twoD ? "二维游戏画面已导入并配置为精灵" : "三维资产已导入并转换为网格", "成功");
                Emit("导入音频", 50, "WAV 已导入并配置 AudioSource", "成功");
                Emit("创建对象", 60, twoD ? $"已按 {request.buildPlan.template_id} 计划创建输入、目标、失败条件、素材角色与声音事件" : "漆碗、地面、灯光与相机已创建", "成功");

                WriteState("等待编译");
                Emit("生成脚本", 70, "使用已批准逻辑生成运行时 C# 脚本", "成功");
                Directory.CreateDirectory(Path.GetDirectoryName(ScriptPath) ?? "Assets/QIWEN/Runtime");
                File.WriteAllText(ScriptPath, request.runtimeScript, new UTF8Encoding(false));
                AssetDatabase.ImportAsset(ScriptPath, ImportAssetOptions.ForceUpdate);
                Emit("编译", 75, "等待 Unity 完成脚本编译", "信息");
            }
            catch (Exception exception)
            {
                Fail("创建场景", exception);
            }
        }

        [MenuItem("漆问/继续最小垂直切片")]
        public static void Resume()
        {
            ResumeIfNeeded();
        }

        private static void ResumeIfNeeded()
        {
            var state = ReadState();
            if (state == null || state.stage != "等待编译") return;
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                EditorApplication.delayCall += ResumeIfNeeded;
                return;
            }
            if (EditorUtility.scriptCompilationFailed)
            {
                Fail("编译", new InvalidOperationException("Unity 报告脚本编译失败，请查看控制台"));
                return;
            }
            AttachAndPlay();
        }

        private static void AttachAndPlay()
        {
            try
            {
                var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
                var request = JsonUtility.FromJson<BridgeRequest>(File.ReadAllText(Path.GetFullPath("QIWEN/Requests/pending.json")));
                var twoD = string.Equals(request?.mode, "2d", StringComparison.OrdinalIgnoreCase);
                var bowl = GameObject.Find(twoD ? "漆问游戏控制器" : "漆碗");
                if (bowl == null) throw new InvalidOperationException(twoD ? "场景中找不到游戏控制器" : "场景中找不到漆碗对象");
                var behaviourType = Type.GetType("QIWEN.Runtime.LacquerBowlExperience, Assembly-CSharp");
                if (behaviourType == null) throw new InvalidOperationException("生成的运行时脚本尚未载入");
                if (!twoD && bowl.GetComponent(behaviourType) == null) bowl.AddComponent(behaviourType);
                if (twoD && bowl.GetComponent<QIWEN.Runtime.AgentGameRuntime>() == null) throw new InvalidOperationException("Agent 游戏计划解释器未挂载");
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene, ScenePath);
                Emit("挂载脚本", 85, twoD ? $"已挂载计划驱动运行时：{request.buildPlan.template_id}" : "运行时脚本已挂载到漆碗", "成功");
                Emit("编译", 90, "Unity 脚本编译通过", "成功");
                WriteState("进入试玩");
                waitingForPlay = true;
                Emit("试玩", 95, "正在进入 Play Mode", "信息");
                EditorApplication.isPlaying = true;
            }
            catch (Exception exception)
            {
                Fail("挂载脚本", exception);
            }
        }

        private static void OnPlayModeChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredPlayMode) return;
            var sliceState = ReadState();
            if (!waitingForPlay && sliceState?.stage != "进入试玩") return;
            waitingForPlay = false;
            var controller = GameObject.Find("漆问游戏控制器");
            var game = controller == null ? null : controller.GetComponent<QIWEN.Runtime.AgentGameRuntime>();
            var isTwoD = game != null;
            Emit("试玩", 100, isTwoD ? $"Unity 已进入播放模式；实际模板 {game.ActiveTemplateId}，不是固定演示游戏" : "Unity 已进入播放模式；漆碗可旋转且音乐开始播放", "成功");
            WriteResult(true, "完成", isTwoD ? $"Agent 构建计划已执行并进入真实播放模式：{game.ActiveTemplateId}" : "最小垂直切片已完成并进入试玩");
            WriteState("完成");
        }

        private static void OnAssemblyCompiled(string assemblyPath, CompilerMessage[] messages)
        {
            foreach (var message in messages)
            {
                if (message.type == CompilerMessageType.Error)
                {
                    Emit("编译", 75, message.message, "错误");
                }
            }
        }

        private static void CreateBaseScene(BridgeRequest request)
        {
            var twoD = string.Equals(request.mode, "2d", StringComparison.OrdinalIgnoreCase);
            Directory.CreateDirectory("Assets/QIWEN/Scenes");
            AssetDatabase.ImportAsset("Assets/QIWEN/Input/main-theme.wav", ImportAssetOptions.ForceSynchronousImport);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            if (twoD)
            {
                const string spriteFolder = "Assets/QIWEN/Input/Sprites";
                var imagePaths = Directory.GetFiles(spriteFolder, "*.png").OrderBy(path => path).Select(path => path.Replace('\\', '/')).ToArray();
                if (imagePaths.Length == 0) throw new InvalidOperationException("没有找到已确认的二维独立素材");
                var sprites = new List<Sprite>();
                for (var index = 0; index < imagePaths.Length; index++)
                {
                    var imagePath = imagePaths[index];
                    AssetDatabase.ImportAsset(imagePath, ImportAssetOptions.ForceSynchronousImport);
                    var importer = AssetImporter.GetAtPath(imagePath) as TextureImporter;
                    if (importer == null) throw new InvalidOperationException($"二维素材导入失败：{imagePath}");
                    importer.textureType = TextureImporterType.Sprite;
                    importer.spriteImportMode = SpriteImportMode.Single;
                    importer.alphaIsTransparency = true;
                    importer.SaveAndReimport();
                    var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(imagePath);
                    if (sprite == null) throw new InvalidOperationException($"二维素材无法转换为精灵：{imagePath}");
                    sprites.Add(sprite);
                }
                var controllerObject = new GameObject("漆问游戏控制器");
                var game = controllerObject.AddComponent<QIWEN.Runtime.AgentGameRuntime>();
                game.templateId = request.buildPlan.template_id;
                game.gameTitle = request.buildPlan.game_title;
                game.objective = request.buildPlan.objective;
                game.playerInstructions = request.buildPlan.player_instructions;
                game.targetCount = request.buildPlan.target_count;
                game.timeLimitSeconds = request.buildPlan.time_limit_seconds;
                game.failureLimit = request.buildPlan.failure_limit;
                game.gameSpeed = request.buildPlan.speed;
                game.sequenceSteps = request.buildPlan.sequence_steps ?? Array.Empty<string>();
                game.audioCueLabels = request.buildPlan.audio_cues ?? Array.Empty<string>();
                game.approvedSprites = sprites.ToArray();
                game.approvedAudio = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/QIWEN/Input/main-theme.wav");

                var workshop = new GameObject("深色机械漆坊背景");
                if (sprites.Count > 0)
                {
                    var backgroundRenderer = workshop.AddComponent<SpriteRenderer>();
                    backgroundRenderer.sprite = sprites[sprites.Count - 1];
                    backgroundRenderer.color = new Color(0.28f, 0.32f, 0.38f, 0.48f);
                    backgroundRenderer.sortingOrder = -10;
                    var bounds = backgroundRenderer.sprite.bounds.size;
                    workshop.transform.localScale = new Vector3(16f / Mathf.Max(0.1f, bounds.x), 10f / Mathf.Max(0.1f, bounds.y), 1f);
                }
                var camera2DObject = new GameObject("主相机");
                camera2DObject.tag = "MainCamera";
                var camera2D = camera2DObject.AddComponent<Camera>();
                camera2DObject.AddComponent<AudioListener>();
                camera2D.orthographic = true; camera2D.orthographicSize = 5.0f;
                camera2D.clearFlags = CameraClearFlags.SolidColor;
                camera2D.backgroundColor = new Color(0.035f, 0.045f, 0.075f, 1f);
                camera2DObject.transform.position = new Vector3(0f, 0f, -10f);
                EditorSceneManager.SaveScene(scene, ScenePath);
                AssetDatabase.SaveAssets();
                return;
            }

            var bowl = new GameObject("漆碗");

            AssetDatabase.ImportAsset("Assets/QIWEN/Input/lacquer-bowl.glb", ImportAssetOptions.ForceSynchronousImport);
            var mesh = ReadFirstMesh("Assets/QIWEN/Input/lacquer-bowl.glb");
            mesh.name = "漆碗_GLＢ网格";
            var filter = bowl.AddComponent<MeshFilter>();
            filter.sharedMesh = mesh;
            var renderer = bowl.AddComponent<MeshRenderer>();
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var material = new Material(shader) { name = "黑漆材质", color = new Color(0.025f, 0.025f, 0.025f, 1f) };
            renderer.sharedMaterial = material;
            bowl.AddComponent<MeshCollider>().sharedMesh = mesh;
            bowl.transform.position = new Vector3(0f, 0.8f, 0f);

            var audio = bowl.AddComponent<AudioSource>();
            audio.clip = AssetDatabase.LoadAssetAtPath<AudioClip>("Assets/QIWEN/Input/main-theme.wav");
            audio.loop = true;
            audio.playOnAwake = true;
            audio.volume = 0.45f;

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "白色工作台";
            ground.transform.localScale = new Vector3(1.6f, 1f, 1.6f);
            var groundMaterial = new Material(shader) { name = "白色工作台材质", color = new Color(0.86f, 0.86f, 0.84f, 1f) };
            ground.GetComponent<MeshRenderer>().sharedMaterial = groundMaterial;

            var cameraObject = new GameObject("主相机");
            cameraObject.tag = "MainCamera";
            var camera = cameraObject.AddComponent<Camera>();
            cameraObject.AddComponent<AudioListener>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.white;
            cameraObject.transform.SetPositionAndRotation(new Vector3(0f, 2.5f, -4.5f), Quaternion.Euler(16f, 0f, 0f));

            var lightObject = new GameObject("主灯光");
            var light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.3f;
            light.color = Color.white;
            lightObject.transform.rotation = Quaternion.Euler(48f, -32f, 0f);

            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
        }

        private static Mesh ReadFirstMesh(string assetPath)
        {
            var fullPath = Path.GetFullPath(assetPath);
            var bytes = File.ReadAllBytes(fullPath);
            if (bytes.Length < 20 || BitConverter.ToUInt32(bytes, 0) != 0x46546C67 || BitConverter.ToUInt32(bytes, 4) != 2)
                throw new InvalidDataException("GLB 文件头无效");
            var cursor = 12;
            string json = "";
            byte[] binary = Array.Empty<byte>();
            while (cursor + 8 <= bytes.Length)
            {
                var length = checked((int)BitConverter.ToUInt32(bytes, cursor));
                var type = BitConverter.ToUInt32(bytes, cursor + 4);
                cursor += 8;
                if (cursor + length > bytes.Length) throw new InvalidDataException("GLB 数据块越界");
                if (type == 0x4E4F534A) json = Encoding.UTF8.GetString(bytes, cursor, length).TrimEnd('\0', ' ', '\r', '\n');
                if (type == 0x004E4942)
                {
                    binary = new byte[length];
                    Buffer.BlockCopy(bytes, cursor, binary, 0, length);
                }
                cursor += length;
            }
            var root = JsonUtility.FromJson<GltfRoot>(json) ?? throw new InvalidDataException("GLB JSON 无法解析");
            if (root.meshes.Length == 0 || root.meshes[0].primitives.Length == 0) throw new InvalidDataException("GLB 不含网格");
            var primitive = root.meshes[0].primitives[0];
            var vertices = ReadVector3(root, binary, primitive.attributes.POSITION);
            var normals = primitive.attributes.NORMAL >= 0 ? ReadVector3(root, binary, primitive.attributes.NORMAL) : Array.Empty<Vector3>();
            var triangles = ReadIndices(root, binary, primitive.indices);
            var mesh = new Mesh { indexFormat = vertices.Length > 65535 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
            mesh.vertices = vertices;
            mesh.triangles = triangles;
            if (normals.Length == vertices.Length) mesh.normals = normals; else mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();
            return mesh;
        }

        private static Vector3[] ReadVector3(GltfRoot root, byte[] binary, int accessorIndex)
        {
            if (accessorIndex < 0 || accessorIndex >= root.accessors.Length) throw new InvalidDataException("GLB 顶点访问器缺失");
            var accessor = root.accessors[accessorIndex];
            if (accessor.componentType != 5126 || accessor.type != "VEC3") throw new InvalidDataException("GLB 顶点格式不受支持");
            var view = root.bufferViews[accessor.bufferView];
            var start = view.byteOffset + accessor.byteOffset;
            var stride = view.byteStride > 0 ? view.byteStride : 12;
            var values = new Vector3[accessor.count];
            for (var i = 0; i < values.Length; i++)
            {
                var offset = start + i * stride;
                values[i] = new Vector3(BitConverter.ToSingle(binary, offset), BitConverter.ToSingle(binary, offset + 4), BitConverter.ToSingle(binary, offset + 8));
            }
            return values;
        }

        private static int[] ReadIndices(GltfRoot root, byte[] binary, int accessorIndex)
        {
            if (accessorIndex < 0 || accessorIndex >= root.accessors.Length) throw new InvalidDataException("GLB 索引访问器缺失");
            var accessor = root.accessors[accessorIndex];
            var view = root.bufferViews[accessor.bufferView];
            var start = view.byteOffset + accessor.byteOffset;
            var elementSize = accessor.componentType == 5125 ? 4 : accessor.componentType == 5123 ? 2 : 1;
            var values = new int[accessor.count];
            for (var i = 0; i < values.Length; i++)
            {
                var offset = start + i * elementSize;
                values[i] = accessor.componentType == 5125 ? checked((int)BitConverter.ToUInt32(binary, offset)) : accessor.componentType == 5123 ? BitConverter.ToUInt16(binary, offset) : binary[offset];
            }
            return values;
        }

        private static SliceState ReadState()
        {
            var path = Path.GetFullPath(StatePath);
            if (!File.Exists(path)) return null;
            try { return JsonUtility.FromJson<SliceState>(File.ReadAllText(path)); }
            catch { return null; }
        }

        private static void WriteState(string stage)
        {
            var path = Path.GetFullPath(StatePath);
            Directory.CreateDirectory(Path.GetDirectoryName(path) ?? "QIWEN/State");
            File.WriteAllText(path, JsonUtility.ToJson(new SliceState { stage = stage, startedAt = DateTime.UtcNow.ToString("O") }, true), new UTF8Encoding(false));
        }

        private static void Emit(string stage, int progress, string message, string level)
        {
            var path = Path.GetFullPath(EventPath);
            Directory.CreateDirectory(Path.GetDirectoryName(path) ?? "QIWEN/Results");
            var line = JsonUtility.ToJson(new SliceEvent { stage = stage, progress = progress, message = message, level = level, time = DateTime.UtcNow.ToString("O") });
            File.AppendAllText(path, line + Environment.NewLine, new UTF8Encoding(false));
            Debug.Log($"[漆问] {progress}% {stage}：{message}");
        }

        private static void WriteResult(bool success, string stage, string message)
        {
            var path = Path.GetFullPath(ResultPath);
            Directory.CreateDirectory(Path.GetDirectoryName(path) ?? "QIWEN/Results");
            File.WriteAllText(path, JsonUtility.ToJson(new SliceResult { success = success, stage = stage, message = message, time = DateTime.UtcNow.ToString("O") }, true), new UTF8Encoding(false));
        }

        private static void Fail(string stage, Exception exception)
        {
            Emit(stage, 0, exception.Message, "错误");
            WriteResult(false, stage, exception.ToString());
            WriteState("失败");
            Debug.LogException(exception);
        }

        private static void ResetResults()
        {
            foreach (var relative in new[] { ResultPath, EventPath })
            {
                var path = Path.GetFullPath(relative);
                if (File.Exists(path)) File.Delete(path);
            }
        }
    }
}
