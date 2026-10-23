using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Neram.Unity;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Neram.EditorTools
{
    /// <summary>
    /// Presentation pass for the theatre (Sai, 19 Oct 2026): soft high-resolution shadows, screen-space ambient
    /// occlusion, ACES tonemapping with gentle colour grading and bloom, a warmer key light, shadowing surgical lamps,
    /// soft ceiling fill lights, a box-projected reflection probe and per-material smoothness. Visual only: none of this
    /// changes replay data or any displayed value. Menu: NERAM > Scene > Apply presentation look (automation job "look").
    /// </summary>
    public static class NeramLook
    {
        [MenuItem("NERAM/Scene/Apply presentation look (lighting, AO, grading)", priority = 31)]
        public static void Menu() => EditorUtility.DisplayDialog("NERAM look", Apply(), "OK");

        public static string Apply()
        {
            var sb = new StringBuilder();
            var scene = EditorSceneManager.GetActiveScene();
            if (scene.path != NeramSetup.ScenePath) scene = EditorSceneManager.OpenScene(NeramSetup.ScenePath);
            Pipeline(sb);
            Post(sb);
            Lights(sb);
            Materials(sb);
            DefaultScenario(sb);
            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
            sb.Insert(0, "presentation look applied " + DateTime.Now.ToString("u") + "\n");
            return sb.ToString();
        }

        // ------------------------------------------------------------------ URP asset + renderer
        private static void Pipeline(StringBuilder sb)
        {
            var asset = GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
            if (asset == null) { sb.AppendLine("URP asset not active"); return; }
            var so = new SerializedObject(asset);
            void F(string n, float v) { var p = so.FindProperty(n); if (p != null) p.floatValue = v; else sb.AppendLine("  (no " + n + ")"); }
            void I(string n, int v) { var p = so.FindProperty(n); if (p != null) { if (p.propertyType == SerializedPropertyType.Enum) p.enumValueIndex = v; else p.intValue = v; } else sb.AppendLine("  (no " + n + ")"); }
            void B(string n, bool v) { var p = so.FindProperty(n); if (p != null) p.boolValue = v; else sb.AppendLine("  (no " + n + ")"); }
            F("m_ShadowDistance", 9f);
            I("m_ShadowCascadeCount", 4);
            I("m_MainLightShadowmapResolution", 4096);
            I("m_AdditionalLightsShadowmapResolution", 4096);
            B("m_AdditionalLightShadowsSupported", true);
            B("m_SoftShadowsSupported", true);
            I("m_AdditionalLightsPerObjectLimit", 8);
            B("m_SupportsHDR", true);
            I("m_MSAA", 4);
            F("m_RenderScale", 1f);
            var sq = so.FindProperty("m_SoftShadowQuality"); if (sq != null) sq.intValue = 3;   // High
            so.ApplyModifiedProperties();
            EditorUtility.SetDirty(asset);
            sb.AppendLine("URP: 4096 shadow maps, 4 cascades, soft shadows (high), MSAA 4x, HDR");

            // SSAO renderer feature on every renderer of the asset
            var rdList = new SerializedObject(asset).FindProperty("m_RendererDataList");
            for (int i = 0; rdList != null && i < rdList.arraySize; i++)
            {
                var rd = rdList.GetArrayElementAtIndex(i).objectReferenceValue as ScriptableRendererData;
                if (rd == null) continue;
                var t = typeof(UniversalRenderPipelineAsset).Assembly.GetTypes().FirstOrDefault(x => x.Name == "ScreenSpaceAmbientOcclusion");
                if (t == null) { sb.AppendLine("SSAO feature type not found"); break; }
                var feat = rd.rendererFeatures.FirstOrDefault(f => f != null && f.GetType() == t);
                if (feat == null)
                {
                    feat = (ScriptableRendererFeature)ScriptableObject.CreateInstance(t);
                    feat.name = "NERAM_SSAO";
                    AssetDatabase.AddObjectToAsset(feat, rd);
                    rd.rendererFeatures.Add(feat);
                    AssetDatabase.TryGetGUIDAndLocalFileIdentifier(feat, out _, out long lid);
                    var rso = new SerializedObject(rd);
                    var map = rso.FindProperty("m_RendererFeatureMap");
                    if (map != null) { map.arraySize++; map.GetArrayElementAtIndex(map.arraySize - 1).longValue = lid; }
                    rso.ApplyModifiedProperties();
                }
                var fso = new SerializedObject(feat);
                void FS(string n, float v) { var p = fso.FindProperty("m_Settings." + n); if (p != null) { if (p.propertyType == SerializedPropertyType.Float) p.floatValue = v; else if (p.propertyType == SerializedPropertyType.Boolean) p.boolValue = v > 0.5f; else p.intValue = (int)v; } }
                FS("Intensity", 1.1f); FS("Radius", 0.22f); FS("DirectLightingStrength", 0.3f); FS("Downsample", 0f);
                FS("AfterOpaque", 0f); FS("Falloff", 2.5f); FS("BlurQuality", 0f); FS("SampleCount", 1f);
                fso.ApplyModifiedProperties();
                feat.SetActive(true);
                EditorUtility.SetDirty(feat);
                EditorUtility.SetDirty(rd);
                sb.AppendLine("SSAO: on (" + rd.name + ")");
            }
        }

        // ------------------------------------------------------------------ volume profile
        private static T Get<T>(VolumeProfile p) where T : VolumeComponent
        {
            if (!p.TryGet<T>(out var c)) { c = p.Add<T>(true); c.name = typeof(T).Name; AssetDatabase.AddObjectToAsset(c, p); }
            c.active = true;
            return c;
        }

        private static void Post(StringBuilder sb)
        {
            var profile = NeramSetup.EnsureVolumeProfile();
            Get<Tonemapping>(profile).mode.Override(TonemappingMode.ACES);
            var bloom = Get<Bloom>(profile);
            bloom.threshold.Override(1.0f); bloom.intensity.Override(0.35f); bloom.scatter.Override(0.62f);
            bloom.highQualityFiltering.Override(true);
            var ca = Get<ColorAdjustments>(profile);
            ca.postExposure.Override(0.35f); ca.contrast.Override(14f); ca.saturation.Override(6f);
            var wb = Get<WhiteBalance>(profile);
            wb.temperature.Override(-4f); wb.tint.Override(2f);
            var smh = Get<ShadowsMidtonesHighlights>(profile);
            smh.shadows.Override(new Vector4(0.96f, 0.99f, 1.06f, -0.02f));
            smh.highlights.Override(new Vector4(1.03f, 1.01f, 0.97f, 0.0f));
            var vig = Get<Vignette>(profile);
            vig.intensity.Override(0.22f); vig.smoothness.Override(0.5f);
            if (profile.TryGet<FilmGrain>(out var fg)) fg.active = false;
            EditorUtility.SetDirty(profile);
            foreach (var v in UnityEngine.Object.FindObjectsByType<Volume>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                if (v.isGlobal && v.sharedProfile == null) v.sharedProfile = profile;
            foreach (var c in UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                var ad = c.GetUniversalAdditionalCameraData();
                ad.renderPostProcessing = true;
                ad.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing;
                ad.antialiasingQuality = AntialiasingQuality.High;
                ad.renderShadows = true;
                c.allowHDR = true;
                c.allowMSAA = true;
            }
            sb.AppendLine("post: ACES, bloom 0.35, exposure +0.35, contrast 14, cool white balance, vignette 0.22, SMAA high");
        }

        // ------------------------------------------------------------------ lights
        private static void Lights(StringBuilder sb)
        {
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.58f, 0.63f, 0.70f);
            RenderSettings.ambientEquatorColor = new Color(0.42f, 0.45f, 0.49f);
            RenderSettings.ambientGroundColor = new Color(0.20f, 0.21f, 0.23f);
            int key = 0, spots = 0, others = 0;
            foreach (var l in UnityEngine.Object.FindObjectsByType<Light>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                if (l.name.StartsWith("__")) continue;          // heater glow lights stay as they are
                if (l.transform.GetComponentInParent<NeramExtrasMarker>() != null && l.name.StartsWith("NERAM_Fill")) continue;
                if (l.type == LightType.Directional)
                {
                    l.shadows = LightShadows.Soft; l.shadowStrength = 0.85f; l.shadowResolution = LightShadowResolution.VeryHigh;
                    l.shadowBias = 0.02f; l.shadowNormalBias = 0.25f; l.color = new Color(1.0f, 0.97f, 0.92f);
                    l.intensity = Mathf.Clamp(l.intensity, 0.9f, 1.2f);
                    key++;
                }
                else if (l.type == LightType.Spot)
                {
                    l.shadows = LightShadows.Soft; l.shadowResolution = LightShadowResolution.VeryHigh; l.shadowStrength = 0.9f;
                    l.shadowBias = 0.01f; l.shadowNormalBias = 0.3f;
                    l.useColorTemperature = true; l.colorTemperature = 4600f; l.color = Color.white;
                    l.innerSpotAngle = Mathf.Max(l.innerSpotAngle, l.spotAngle * 0.55f);
                    spots++;
                }
                else { l.shadows = l.range > 3f ? LightShadows.Soft : LightShadows.None; others++; }
                EditorUtility.SetDirty(l);
            }
            // soft ceiling fill (no shadows): four panels above the room, keeps faces readable under the lamps
            var asm = GameObject.Find(SceneNames.Assembly);
            Transform parent = asm != null ? asm.transform : null;
            foreach (var old in UnityEngine.Object.FindObjectsByType<Light>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                if (old != null && old.name.StartsWith("NERAM_Fill")) UnityEngine.Object.DestroyImmediate(old.gameObject);
            var pts = new[] { new Vector3(-1.4f, 1.95f, -1.6f), new Vector3(1.4f, 1.95f, -1.6f), new Vector3(-1.4f, 1.95f, 1.4f), new Vector3(1.4f, 1.95f, 1.4f) };
            for (int i = 0; i < pts.Length; i++)
            {
                var go = new GameObject("NERAM_Fill_" + i);
                go.AddComponent<NeramExtrasMarker>();
                if (parent != null) go.transform.SetParent(parent, false);
                go.transform.localPosition = pts[i];
                var l = go.AddComponent<Light>();
                l.type = LightType.Point; l.range = 4.2f; l.intensity = 0.55f; l.shadows = LightShadows.None;
                l.useColorTemperature = true; l.colorTemperature = 5600f;
            }
            // reflection probe: box projection over the room, refreshed once at start
            foreach (var rp in UnityEngine.Object.FindObjectsByType<ReflectionProbe>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                rp.boxProjection = true; rp.resolution = 256; rp.hdr = true; rp.intensity = 1f;
                rp.mode = ReflectionProbeMode.Realtime; rp.refreshMode = ReflectionProbeRefreshMode.OnAwake;
                rp.timeSlicingMode = ReflectionProbeTimeSlicingMode.NoTimeSlicing;
                if (rp.size.x < 5f) rp.size = new Vector3(6.6f, 3.2f, 7.2f);
                EditorUtility.SetDirty(rp);
            }
            sb.AppendLine($"lights: {key} key (soft, very high), {spots} surgical spots (soft shadows, 4600 K), {others} other, 4 ceiling fills; reflection probe box-projected");
        }

        // ------------------------------------------------------------------ materials
        private static readonly (string match, float smooth, float metal)[] Rules =
        {
            ("Metal", 0.82f, 0.95f), ("Steel", 0.85f, 1.0f), ("Chrome", 0.9f, 1.0f), ("Instrument", 0.86f, 1.0f),
            ("Skin", 0.46f, 0f), ("Glove", 0.62f, 0f), ("Scrubs", 0.18f, 0f), ("Gown", 0.22f, 0f), ("Drape", 0.28f, 0f),
            ("Floor", 0.55f, 0f), ("Wall", 0.30f, 0f), ("Equip", 0.55f, 0f), ("Screen", 0.92f, 0f), ("Glass", 0.95f, 0f),
            ("Pad", 0.40f, 0f), ("Cabinet", 0.50f, 0f), ("Plastic", 0.55f, 0f),
        };

        private static void Materials(StringBuilder sb)
        {
            int n = 0;
            foreach (var guid in AssetDatabase.FindAssets("t:Material", new[] { NeramSetup.MaterialsDir }))
            {
                var m = AssetDatabase.LoadAssetAtPath<Material>(AssetDatabase.GUIDToAssetPath(guid));
                if (m == null || !m.HasProperty("_Smoothness")) continue;
                foreach (var (match, smooth, metal) in Rules)
                {
                    if (m.name.IndexOf(match, StringComparison.OrdinalIgnoreCase) < 0) continue;
                    if (m.name.Contains("MAT_Halo")) break;
                    m.SetFloat("_Smoothness", smooth);
                    if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", metal);
                    if (m.HasProperty("_SpecularHighlights")) m.SetFloat("_SpecularHighlights", 1f);
                    if (m.HasProperty("_EnvironmentReflections")) m.SetFloat("_EnvironmentReflections", 1f);
                    EditorUtility.SetDirty(m);
                    n++;
                    break;
                }
            }
            sb.AppendLine("materials tuned: " + n);
        }

        // ------------------------------------------------------------------ start-up scenario
        private static void DefaultScenario(StringBuilder sb)
        {
            foreach (var rl in UnityEngine.Object.FindObjectsByType<ReplayLoader>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                var so = new SerializedObject(rl);
                var p = so.FindProperty("defaultScenarioId");
                if (p == null) continue;
                p.stringValue = "SCN_C";
                so.ApplyModifiedProperties();
                sb.AppendLine("start-up scenario: SCN_C (Suchita's controller TC07, closed loop)");
            }
        }
    }
}
