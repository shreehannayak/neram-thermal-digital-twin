using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Neram.Unity;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;

namespace Neram.EditorTools
{
    /// <summary>
    /// One-click project bootstrap (menu NERAM > 1. Run full setup, or batch mode:
    ///   Unity -batchmode -quit -projectPath unity_editor -executeMethod Neram.EditorTools.NeramSetup.RunFullSetupBatch).
    ///
    /// Steps: locate the workspace by marker folders and sync config + validated replays; make sure URP is active;
    /// configure generated textures; create the URP material palette; create/repair the PanelSettings asset; build the
    /// scene Assets/Scenes/NERAM_OR_Replay.unity from the generated theatre/patient bundle; assign the UIDocument's
    /// PanelSettings through serialization and VERIFY it after saving; add an EventSystem for the Input System; validate.
    ///
    /// Root cause of the earlier "3D only, no dashboard" scene: the generated UIDocument was saved with
    /// m_PanelSettings = {fileID: 0}. A UIDocument without PanelSettings renders nothing. Setup now assigns the asset via
    /// SerializedObject after the new scene exists, re-opens the saved scene and fails loudly if the reference is missing.
    ///
    /// COORDINATE CONTRACT (generated geometry and CAD): metres, Y up, origin = centre of the table-top surface, +Z toward
    /// the patient's head, patient supine (face +Y). In Unity's left-handed frame this puts the PATIENT'S LEFT at +X.
    /// </summary>
    public static class NeramSetup
    {
        public const string ScenePath = "Assets/Scenes/NERAM_OR_Replay.unity";
        public const string MaterialsDir = "Assets/Materials/NERAM";
        public const string RenderingDir = "Assets/Settings/Rendering";
        public const string PanelSettingsPath = "Assets/Resources/NERAM/NeramPanelSettings.asset";
        public const string LegacyPanelSettingsPath = "Assets/UI/NeramPanelSettings.asset";
        public const string UxmlPath = "Assets/Resources/NERAM/UI/NeramMain.uxml";
        public const string ThemePath = "Assets/Resources/NERAM/UI/NeramRuntimeTheme.tss";

        // ------------------------------------------------------------------ entry points

        [MenuItem("NERAM/1. Run full setup", priority = 1)]
        public static void RunFullSetupMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            var (log, errors) = RunFullSetup();
            Debug.Log(log);
            foreach (var e in errors) Debug.LogError("[NERAM setup] " + e);
            var ok = NeramValidation.Run(out var report);
            if (ok && errors.Count == 0) Debug.Log(report); else Debug.LogError(report);
            var fails = report.Split('\n').Where(l => l.StartsWith("FAIL", StringComparison.Ordinal)).Take(6).ToList();
            string msg;
            if (errors.Count == 0 && ok) msg = "NERAM setup v" + NeramVersion.Value + " complete. Validation PASSED.\n\nPress Play: the dashboard and the replay start automatically.";
            else
            {
                msg = "NERAM setup v" + NeramVersion.Value + " finished with problems.\n\n";
                foreach (var e in errors.Take(4)) msg += "SETUP ERROR  " + e + "\n";
                foreach (var f in fails) msg += f.Trim() + "\n";
                msg += "\nFull report in the Console (NERAM > 4. Validate project re-runs the checks).";
            }
            EditorUtility.DisplayDialog("NERAM setup", msg, "OK");
        }

        /// <summary>Batch-mode entry point. Exit code 0 = setup and validation passed, 1 = validation failed, 2 = setup error.</summary>
        public static void RunFullSetupBatch()
        {
            try
            {
                var (log, errors) = RunFullSetup();
                Debug.Log(log);
                foreach (var e in errors) Debug.LogError("[NERAM setup] " + e);
                var ok = NeramValidation.Run(out var report);
                Debug.Log(report);
                EditorApplication.Exit(errors.Count > 0 ? 2 : ok ? 0 : 1);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                EditorApplication.Exit(2);
            }
        }

        [MenuItem("NERAM/3. Rebuild scene", priority = 3)]
        public static void RebuildSceneMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            var errors = new List<string>();
            var lit = LitShader();
            var res = new NeramSceneBuilder.Result();
            NeramSceneBuilder.ConfigureTextures(res);
            var mats = NeramSceneBuilder.EnsureMaterials(MaterialsDir, lit, res);
            AddHalo(mats);
            BuildScene(mats, EnsurePanelSettings(errors), EnsureVolumeProfile(), errors);
            errors.AddRange(res.Errors);
            foreach (var e in errors) Debug.LogError("[NERAM setup] " + e);
            if (errors.Count == 0) Debug.Log("[NERAM] scene rebuilt: " + ScenePath);
        }

        public static (string log, List<string> errors) RunFullSetup()
        {
            var log = new System.Text.StringBuilder();
            var errors = new List<string>();
            EnsureFolders();
            log.AppendLine(NeramWorkspace.Describe());
            var sync = NeramSync.Sync();
            log.AppendLine(sync.ToString());
            if (sync.Fatal != null) errors.Add("sync failed: workspace not found (see Console). StreamingAssets keeps its previous contents.");
            foreach (var r in sync.Rejected) errors.Add("replay rejected by the validator and NOT copied: " + r);
            log.AppendLine(EnsureRenderPipeline());
            var res = new NeramSceneBuilder.Result();
            NeramSceneBuilder.ConfigureTextures(res);
            var mats = NeramSceneBuilder.EnsureMaterials(MaterialsDir, LitShader(), res);
            AddHalo(mats);
            log.AppendLine("materials: " + mats.Count + " in " + MaterialsDir);
            var ps = EnsurePanelSettings(errors);
            log.AppendLine("panel settings: " + (ps != null ? AssetDatabase.GetAssetPath(ps) : "MISSING"));
            var profile = EnsureVolumeProfile();
            var built = BuildScene(mats, ps, profile, errors);
            errors.AddRange(res.Errors);
            foreach (var i in res.Info) log.AppendLine(i);
            if (built != null) foreach (var i in built.Info) log.AppendLine(i);
            log.AppendLine("scene: " + ScenePath + " (first in Build Settings)");
            AssetDatabase.SaveAssets();
            return (log.ToString(), errors);
        }

        private static void EnsureFolders()
        {
            foreach (var d in new[] { "Assets/Scenes", MaterialsDir, RenderingDir, "Assets/Resources/NERAM", "Assets/StreamingAssets/config", "Assets/StreamingAssets/replays", "Assets/StreamingAssets/cad", "Assets/NERAM_CAD", "Assets/NERAM_Generated/Meshes" })
                Directory.CreateDirectory(Path.Combine(Path.GetDirectoryName(Application.dataPath) ?? "", d));
            AssetDatabase.Refresh();
        }

        // ------------------------------------------------------------------ render pipeline

        public static string EnsureRenderPipeline()
        {
            var current = GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
            if (current != null)
            {
                SetAllQualityLevels(current);
                return "URP: already active (" + AssetDatabase.GetAssetPath(current) + ")";
            }
            var rdPath = RenderingDir + "/NERAM_UniversalRenderer.asset";
            var assetPath = RenderingDir + "/NERAM_URP.asset";
            var asset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(assetPath);
            if (asset == null)
            {
                var rd = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(rdPath);
                if (rd == null)
                {
                    rd = ScriptableObject.CreateInstance<UniversalRendererData>();
                    if (rd.postProcessData == null)
                        rd.postProcessData = AssetDatabase.LoadAssetAtPath<PostProcessData>("Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset");
                    AssetDatabase.CreateAsset(rd, rdPath);
                }
                asset = UniversalRenderPipelineAsset.Create(rd);
                asset.supportsHDR = true;
                asset.msaaSampleCount = 4;
                AssetDatabase.CreateAsset(asset, assetPath);
            }
            GraphicsSettings.defaultRenderPipeline = asset;
            SetAllQualityLevels(asset);
            AssetDatabase.SaveAssets();
            return "URP: created and activated " + assetPath;
        }

        private static void SetAllQualityLevels(RenderPipelineAsset asset)
        {
            int keep = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = asset;
            }
            QualitySettings.SetQualityLevel(keep, false);
        }

        // ------------------------------------------------------------------ materials

        public static Shader LitShader()
        {
            var s = Shader.Find("Universal Render Pipeline/Lit");
            if (s == null) { Debug.LogError("[NERAM] URP Lit shader not found; falling back to Standard (scene will render incorrectly)."); s = Shader.Find("Standard"); }
            return s;
        }

        private static Shader UnlitShader()
        {
            var s = Shader.Find("Universal Render Pipeline/Unlit");
            return s != null ? s : Shader.Find("Unlit/Color");
        }

        /// <summary>Fault outline material (unlit, front faces culled = inverted hull); colour set per renderer.</summary>
        private static void AddHalo(Dictionary<string, Material> mats)
        {
            var haloPath = MaterialsDir + "/MAT_Halo.mat";
            var halo = AssetDatabase.LoadAssetAtPath<Material>(haloPath);
            if (halo == null)
            {
                halo = new Material(UnlitShader()) { name = "MAT_Halo" };
                AssetDatabase.CreateAsset(halo, haloPath);
            }
            if (halo.HasProperty("_BaseColor")) halo.SetColor("_BaseColor", new Color(0.92f, 0.70f, 0.03f));
            if (halo.HasProperty("_Cull")) halo.SetFloat("_Cull", (float)CullMode.Front);
            EditorUtility.SetDirty(halo);
            mats["MAT_Halo"] = halo;
            AssetDatabase.SaveAssets();
        }

        // ------------------------------------------------------------------ UI + post-processing assets

        /// <summary>PanelSettings lives in Resources so the runtime can also load it as a fallback.</summary>
        public static PanelSettings EnsurePanelSettings(List<string> errors)
        {
            var ps = AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelSettingsPath);
            if (ps == null && AssetDatabase.LoadAssetAtPath<PanelSettings>(LegacyPanelSettingsPath) != null)
            {
                var err = AssetDatabase.MoveAsset(LegacyPanelSettingsPath, PanelSettingsPath); // keeps the GUID
                if (!string.IsNullOrEmpty(err)) errors.Add("could not move PanelSettings to " + PanelSettingsPath + ": " + err);
                ps = AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelSettingsPath);
            }
            if (ps == null)
            {
                ps = ScriptableObject.CreateInstance<PanelSettings>();
                AssetDatabase.CreateAsset(ps, PanelSettingsPath);
            }
            ps.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            ps.referenceResolution = new Vector2Int(1600, 900); // logical layout size
            // Shrink: scale = max(width / 1600, height / 900). 16:9 screens give exactly 1600 x 900; narrower screens keep
            // the height at 900 (as before); WIDER screens (21:9, a wide Editor Game view) scale by width, so text grows
            // with the window instead of shrinking with its height (R2 readability fix).
            ps.screenMatchMode = PanelScreenMatchMode.Shrink;
            ps.match = 1f;
            ps.sortingOrder = 0;
            ps.themeStyleSheet = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(ThemePath);
            if (ps.themeStyleSheet == null) errors.Add("runtime theme " + ThemePath + " not found: UI controls would lack default styles");
            EditorUtility.SetDirty(ps);
            AssetDatabase.SaveAssets();
            return AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelSettingsPath);
        }

        /// <summary>Global volume: neutral tonemapping, restrained bloom (heater/LED emission), light vignette. Visual only.</summary>
        public static VolumeProfile EnsureVolumeProfile()
        {
            var path = RenderingDir + "/NERAM_PostProcess.asset";
            var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
            if (profile == null)
            {
                profile = ScriptableObject.CreateInstance<VolumeProfile>();
                AssetDatabase.CreateAsset(profile, path);
            }
            if (!profile.TryGet<Bloom>(out var bloom))
            {
                bloom = profile.Add<Bloom>(true);
                bloom.name = "Bloom";
                AssetDatabase.AddObjectToAsset(bloom, profile);
            }
            bloom.threshold.Override(1.05f);
            bloom.intensity.Override(0.55f);
            bloom.scatter.Override(0.55f);
            if (!profile.TryGet<Tonemapping>(out var tone))
            {
                tone = profile.Add<Tonemapping>(true);
                tone.name = "Tonemapping";
                AssetDatabase.AddObjectToAsset(tone, profile);
            }
            tone.mode.Override(TonemappingMode.Neutral);
            if (!profile.TryGet<Vignette>(out var vig))
            {
                vig = profile.Add<Vignette>(true);
                vig.name = "Vignette";
                AssetDatabase.AddObjectToAsset(vig, profile);
            }
            vig.intensity.Override(0.18f);
            vig.smoothness.Override(0.45f);
            EditorUtility.SetDirty(profile);
            AssetDatabase.SaveAssets();
            return profile;
        }

        // ------------------------------------------------------------------ scene

        public static NeramSceneBuilder.Result BuildScene(Dictionary<string, Material> mats, PanelSettings ps, VolumeProfile profile, List<string> errors)
        {
            // ROOT CAUSE of the v2 failure on Unity 6000.3.26f1 (Editor.log, 2026-10-09): NewScene(Single) unloads assets that
            // nothing in the open scene references. The PanelSettings object loaded just before it was unloaded, so `ps`
            // compared equal to null afterwards ("PanelSettings asset missing"), AssignDocument returned early and the scene
            // was saved with m_PanelSettings and sourceAsset both {fileID: 0}. Remember asset PATHS before the new scene and
            // reload every asset reference from disk after it.
            string psPath = ps != null ? AssetDatabase.GetAssetPath(ps) : PanelSettingsPath;
            if (string.IsNullOrEmpty(psPath)) psPath = PanelSettingsPath;
            string profilePath = profile != null ? AssetDatabase.GetAssetPath(profile) : null;
            var matPaths = new List<KeyValuePair<string, string>>();
            foreach (var kv in mats) matPaths.Add(new KeyValuePair<string, string>(kv.Key, kv.Value != null ? AssetDatabase.GetAssetPath(kv.Value) : null));

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            ps = AssetDatabase.LoadAssetAtPath<PanelSettings>(psPath);
            if (ps == null) errors.Add("PanelSettings could not be loaded from " + psPath + " after creating the new scene (asset missing or failed to import)");
            if (!string.IsNullOrEmpty(profilePath)) profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(profilePath);
            foreach (var kv in matPaths)
            {
                if (string.IsNullOrEmpty(kv.Value)) continue;
                var m = AssetDatabase.LoadAssetAtPath<Material>(kv.Value);
                if (m != null) mats[kv.Key] = m;
                else errors.Add("material " + kv.Key + " could not be reloaded from " + kv.Value);
            }

            // Lighting environment (visual only)
            RenderSettings.skybox = null;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.62f, 0.66f, 0.72f);
            RenderSettings.ambientEquatorColor = new Color(0.46f, 0.49f, 0.53f);
            RenderSettings.ambientGroundColor = new Color(0.22f, 0.24f, 0.27f);

            var vol = new GameObject("PostProcess_Volume").AddComponent<Volume>();
            vol.isGlobal = true;
            vol.sharedProfile = profile;

            var probe = new GameObject("Reflection_Probe").AddComponent<ReflectionProbe>();
            probe.transform.position = new Vector3(0f, 0.7f, -0.3f);
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.OnAwake;
            probe.timeSlicingMode = ReflectionProbeTimeSlicingMode.IndividualFaces;
            probe.size = new Vector3(6.8f, 3.0f, 7.3f);
            probe.boxProjection = true;

            // Camera rig
            var rigGo = new GameObject("NERAM_CameraRig");
            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            camGo.transform.SetParent(rigGo.transform, false);
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color32(196, 205, 214, 255);
            cam.nearClipPlane = 0.02f;
            cam.farClipPlane = 40f;
            cam.fieldOfView = 40f;
            cam.allowHDR = true;
            var camData = camGo.AddComponent<UniversalAdditionalCameraData>();
            camData.renderPostProcessing = true;
            camData.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            camData.antialiasingQuality = AntialiasingQuality.High;
            camGo.AddComponent<AudioListener>();
            var rig = rigGo.AddComponent<CameraRig>();
            rig.cam = cam;
            var input = rigGo.AddComponent<NeramInputController>();
            input.rig = rig;

            // Generated theatre + patient + modules + controller + lights + presets
            var built = NeramSceneBuilder.Build(mats);
            errors.AddRange(built.Errors);
            if (built.Binder != null && built.ThermalAnchor != null) built.Binder.thermalAnchor = built.ThermalAnchor;
            if (built.Binder == null) errors.Add("generated bundle has no NERAM_Assembly node: modules cannot be bound");

            var refCube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            refCube.name = SceneNames.ReferenceCube;
            refCube.transform.position = new Vector3(-1.6f, -0.35f, -1.4f);
            if (mats.TryGetValue("MAT_TableTop_Ref", out var rc)) refCube.GetComponent<Renderer>().sharedMaterial = rc;
            UnityEngine.Object.DestroyImmediate(refCube.GetComponent<Collider>());
            refCube.SetActive(false); // enable to compare CAD scale (1 m edge)

            // Application object
            var app = new GameObject("NERAM_App");
            var doc = app.AddComponent<UIDocument>();
            var loader = app.AddComponent<ReplayLoader>();
            var clock = app.AddComponent<ReplayClock>();
            var neram = app.AddComponent<NeramApp>();
            neram.document = doc;
            neram.loader = loader;
            neram.clock = clock;
            neram.cameraRig = rig;
            neram.assembly = built.Binder;
            neram.wearableAnchor = built.WearableAnchor;
            neram.inputController = input;
            input.document = doc;
            var modes = app.AddComponent<VisualModeController>();
            modes.assembly = built.Binder;
            modes.skinGhost = Mat(mats, "MAT_Skin_Ghost", errors);
            modes.gownGhost = Mat(mats, "MAT_Gown_Ghost", errors);
            modes.drapeGhost = Mat(mats, "MAT_Drape_Ghost", errors);
            modes.thermalMaterial = Mat(mats, "MAT_Thermal", errors);
            modes.pulseMaterial = Mat(mats, "MAT_Pulse", errors);
            neram.visualModes = modes;
            if (built.VesselRoot == null) errors.Add("generated bundle has no Illustrative_Vessels node: Internal View would be empty");
            else built.VesselRoot.gameObject.SetActive(false);
            AssignDocument(doc, ps, AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(UxmlPath), errors);

            EnsureEventSystem(errors);

            var stamp = new GameObject("NERAM_Scene_Stamp").AddComponent<NeramSceneStamp>();
            stamp.generatorVersion = NeramVersion.Value;
            stamp.generatedUtc = DateTime.UtcNow.ToString("u");

            var note = new GameObject("README_SCENE");
            var marker = note.AddComponent<PlaceholderMarker>();
            marker.role = "(scene)";
            marker.note = "Generated by NERAM > 1. Run full setup from tools/gen_neram_scene.py output. All geometry is a visual stand-in " +
                          "(not CAD, not design dimensions). Coordinate contract: metres, Y up, origin = table-top centre, +Z toward the head, " +
                          "patient supine => patient's LEFT = +X. Values on screen come only from validated replay files.";

            // Neharika's CAD (Assets/NERAM_CAD) replaces the stand-ins it covers; stand-ins stay for roles without CAD.
            var cadLog = NeramCadPlacement.PlaceAll(built.Assembly, out int cadPlaced);
            if (cadPlaced > 0)
            {
                marker.note += " Exception: " + cadPlaced + " object(s) use Neharika's CAD from Assets/NERAM_CAD (see NERAM > CAD).";
                Debug.Log("[NERAM CAD]\n" + cadLog);
            }

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) errors.Add("could not save " + ScenePath);
            var list = new List<EditorBuildSettingsScene> { new EditorBuildSettingsScene(ScenePath, true) };
            foreach (var s in EditorBuildSettings.scenes) if (s.path != ScenePath) list.Add(s);
            EditorBuildSettings.scenes = list.ToArray();
            VerifySavedScene(errors);
            return built;
        }

        private static Material Mat(Dictionary<string, Material> mats, string name, List<string> errors)
        {
            if (mats.TryGetValue(name, out var m)) return m;
            errors.Add("material " + name + " missing from the palette (regenerate with tools/gen_neram_scene.py)");
            return null;
        }

        /// <summary>Assign UXML + PanelSettings through serialization (the persisted fields), then read them back.</summary>
        public static void AssignDocument(UIDocument doc, PanelSettings ps, VisualTreeAsset uxml, List<string> errors)
        {
            // Each reference is assigned independently, so one missing asset never blanks the other (v2 returned early).
            if (ps == null) errors.Add("PanelSettings asset missing (" + PanelSettingsPath + "): the dashboard would not render");
            if (uxml == null) errors.Add(UxmlPath + " did not import: the dashboard would not render");
            var so = new SerializedObject(doc);
            var pProp = so.FindProperty("m_PanelSettings");
            var uProp = so.FindProperty("sourceAsset");
            if (pProp != null && ps != null) pProp.objectReferenceValue = ps;
            if (uProp != null && uxml != null) uProp.objectReferenceValue = uxml;
            if (pProp == null) errors.Add("UIDocument serialized field m_PanelSettings not found (UI Toolkit API changed?)");
            if (uProp == null) errors.Add("UIDocument serialized field sourceAsset not found (UI Toolkit API changed?)");
            so.ApplyModifiedPropertiesWithoutUndo();
            // Public setters as well (covers a serialized-field rename in a future UI Toolkit version).
            if (ps != null && doc.panelSettings != ps) doc.panelSettings = ps;
            if (uxml != null && doc.visualTreeAsset != uxml) doc.visualTreeAsset = uxml;
            EditorUtility.SetDirty(doc);
            if (doc.panelSettings == null) errors.Add("UIDocument.panelSettings is still null after assignment");
            if (doc.visualTreeAsset == null) errors.Add("UIDocument.visualTreeAsset is still null after assignment");
        }

        /// <summary>Re-open the saved scene file and check the persisted UIDocument references (fail loudly).</summary>
        private static void VerifySavedScene(List<string> errors)
        {
            var full = Path.Combine(Path.GetDirectoryName(Application.dataPath) ?? "", ScenePath);
            if (!File.Exists(full)) { errors.Add("scene file not written: " + ScenePath); return; }
            var text = File.ReadAllText(full);
            if (text.Contains("m_PanelSettings: {fileID: 0}")) errors.Add("saved scene still has an empty UIDocument PanelSettings reference (m_PanelSettings: {fileID: 0})");
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var app = UnityEngine.Object.FindAnyObjectByType<NeramApp>();
            if (app == null || app.document == null) { errors.Add("NERAM_App/UIDocument missing in the saved scene"); return; }
            if (app.document.panelSettings == null) errors.Add("UIDocument PanelSettings is null in the saved scene");
            if (app.document.visualTreeAsset == null) errors.Add("UIDocument UXML is null in the saved scene");
            var st = UnityEngine.Object.FindAnyObjectByType<NeramSceneStamp>();
            if (st == null || st.generatorVersion != NeramVersion.Value) errors.Add("scene version stamp missing or wrong after save");
        }

        /// <summary>
        /// EventSystem + InputSystemUIInputModule (Active Input Handling = Input System). Added through reflection so the
        /// editor assembly needs no extra references; if the types are missing this is reported as an error.
        /// </summary>
        public static void EnsureEventSystem(List<string> errors)
        {
            var esType = Type.GetType("UnityEngine.EventSystems.EventSystem, UnityEngine.UI");
            var moduleType = Type.GetType("UnityEngine.InputSystem.UI.InputSystemUIInputModule, Unity.InputSystem");
            if (esType == null) { errors.Add("EventSystem type not found (package com.unity.ugui missing?)"); return; }
            var go = new GameObject("EventSystem");
            go.AddComponent(esType);
            if (moduleType != null)
            {
                var module = go.AddComponent(moduleType);
                var assign = moduleType.GetMethod("AssignDefaultActions", BindingFlags.Public | BindingFlags.Instance);
                if (assign != null) assign.Invoke(module, null);
            }
            else
            {
#if ENABLE_LEGACY_INPUT_MANAGER
                var standalone = Type.GetType("UnityEngine.EventSystems.StandaloneInputModule, UnityEngine.UI");
                if (standalone != null) go.AddComponent(standalone);
#else
                errors.Add("InputSystemUIInputModule not found and the legacy Input Manager is disabled: install com.unity.inputsystem");
#endif
            }
        }
    }
}
