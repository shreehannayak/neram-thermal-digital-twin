using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Neram.Core;
using Neram.Unity;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UIElements;

namespace Neram.EditorTools
{
    /// <summary>
    /// Project validation (menu NERAM > 4. Validate project). Each check prints PASS / WARN / FAIL.
    /// FAIL = the viewer would show wrong or missing information, or would not show the dashboard at all.
    /// WARN = only for a genuinely pending team deliverable (CAD geometry, hardware fault table, exploded offsets).
    /// Real failures are never downgraded to warnings. AI-assistant / package-service messages in the Console
    /// (e.g. "NoSubscription") are unrelated to NERAM and are not checked here.
    /// </summary>
    public static class NeramValidation
    {
        /// <summary>Element names the runtime looks up with UiUtil.Req (kept in sync by tests/test_unity_ui_contract.py).</summary>
        public static readonly string[] RequiredUiNames =
        {
            "badges-toggle", "banner-chips", "banner-head", "banner-src", "banner-state", "banner-sub", "banner-substate",
            "brand-sub", "btn-badges", "btn-camera", "btn-capture", "btn-capture-side", "btn-details", "btn-diagnostics",
            "btn-events", "btn-fields", "btn-fullscreen", "btn-hide-all", "btn-menu", "btn-panels", "btn-panels-drawer",
            "btn-params", "btn-presentation", "btn-reset-layout", "btn-scenarios", "btn-settings", "btn-show-all",
            "cam-freeroam", "cam-inspect", "cam-preset-label", "cam-reset", "channel-fault-strip", "channel-fault-text",
            "chart-a-head", "chart-a-host", "chart-a-legend", "chart-a-note", "chart-a-panel", "chart-a-src",
            "chart-a-value", "chart-c-head", "chart-c-host", "chart-c-legend", "chart-c-note", "chart-c-panel",
            "chart-c-src", "chart-c-value", "clock-sub", "clock-time", "controller-banner", "data-error", "detail-panel",
            "dp-actions", "dp-body", "dp-collapse", "dp-sub", "dp-title", "drawer-diagnostics", "drawer-events",
            "drawer-fields", "drawer-panels", "drawer-params", "drawer-scenarios", "drawer-settings", "drawer-sources",
            "event-filters", "event-scroll", "events-close", "exp-ch1", "exp-ch2", "exp-ch3", "exp-ch4", "exp-controls",
            "exp-reset", "exploded-legend", "exploded-title", "fields-close", "footer-right", "footer-text",
            "forecast-cards", "forecast-head", "forecast-hidden", "forecast-panel", "forecast-prov", "forecast-src",
            "forecast-title", "freeroam-hint", "hdr-assumed", "hdr-disclaimer", "hdr-model", "hdr-play-state", "hdr-speed",
            "hdr-synthetic", "hover-tip", "inspector", "internal-legend", "j-clinician", "j-fault", "j-flag", "j-safety",
            "j-transition", "loading", "mode-legend", "module-inspector", "mon-page-channels", "mon-page-flow",
            "mon-page-graphs", "mon-page-values", "monitor-close", "monitor-empty", "monitor-to-analysis",
            "monitor-to-theatre", "ov-card-temp", "ov-card-twin", "ov-channels", "ov-ctrl", "ov-head-temp", "ov-head-twin",
            "ov-obs-src", "ov-pair", "ov-quality", "ov-test", "ov-test-sub", "ov-tobs", "ov-tobs-sub", "ov-twin-src",
            "ov-twin-valid", "ov-unavailable", "panels-close", "panels-hide-all", "panels-reset", "panels-scroll",
            "panels-show-all", "panels-title", "pipeline-head", "pipeline-note", "pipeline-stages", "pipeline-strip",
            "placeholder-mark", "safety-banner", "safety-detail", "safety-released", "safety-reset", "safety-title",
            "scenario-chips", "scenario-id", "scenario-title", "sec-ch", "sec-ch-head", "sec-ctrl", "sec-ctrl-head",
            "sec-na", "sec-na-head", "sec-quality", "sec-quality-head", "set-autodetails", "set-charts-tall",
            "set-details", "set-display-info", "set-fullscreen", "set-labels-compact", "set-labels-detailed",
            "set-labels-off", "set-pipeline", "set-presentation", "settings-close", "sidebar", "sidebar-close",
            "sources-close", "stage", "t-next-event", "t-play", "t-prev-event", "t-restart", "t-speed-1", "t-speed-10",
            "t-speed-2", "t-speed-4", "t-speed-60", "t-status", "t-step-back", "t-step-fwd", "tab-analysis", "tab-monitor",
            "tab-theatre", "telemetry-collapse", "telemetry-scroll", "telemetry-time", "tg-autoscale", "tg-compare",
            "tg-flags", "tg-uncertainty", "thermal-chart-host", "thermal-head", "thermal-legend", "thermal-legend-bar",
            "thermal-legend-value", "thermal-mode-legend", "thermal-panel", "thermal-src", "timeline", "tl-end",
            "tl-start", "viewport", "wearable-screen", "world-layer",
        };

        public static readonly RegionId[] RequiredRegions =
        {
            RegionId.HandLeft, RegionId.HandRight, RegionId.ArmLeft, RegionId.ArmRight, RegionId.Torso, RegionId.LegLeft,
            RegionId.LegRight, RegionId.FootLeft, RegionId.FootRight, RegionId.Wearable, RegionId.Controller,
        };

        private sealed class Log
        {
            public readonly StringBuilder Sb = new StringBuilder();
            public int Fail, Warn, Pass;
            public void P(string m) { Pass++; Sb.AppendLine("PASS  " + m); }
            public void W(string m) { Warn++; Sb.AppendLine("WARN  " + m); }
            public void F(string m) { Fail++; Sb.AppendLine("FAIL  " + m); }
            public void Check(bool ok, string m) { if (ok) P(m); else F(m); }
        }

        [MenuItem("NERAM/4. Validate project", priority = 4)]
        public static void ValidateMenu()
        {
            var ok = Run(out var report);
            if (ok) Debug.Log(report); else Debug.LogError(report);
            var fails = report.Split('\n').Where(l => l.StartsWith("FAIL", StringComparison.Ordinal)).Take(8);
            EditorUtility.DisplayDialog("NERAM validation", ok ? "PASSED (see Console for any WARN items)." : "FAILED:\n\n" + string.Join("\n", fails), "OK");
        }

        [MenuItem("NERAM/5. Validate all replays in StreamingAssets", priority = 5)]
        public static void ValidateReplaysMenu()
        {
            var log = new Log();
            CheckReplays(log);
            Debug.Log(log.Sb.ToString());
            EditorUtility.DisplayDialog("NERAM replays", log.Fail == 0 ? "All replays valid." : log.Fail + " replay(s) invalid — see Console.", "OK");
        }

        public static bool Run(out string report)
        {
            var log = new Log();
            log.Sb.AppendLine("=== NERAM project validation " + DateTime.UtcNow.ToString("u") + " ===");
            CheckWorkspace(log);
            CheckPipeline(log);
            CheckInput(log);
            CheckConfig(log);
            CheckReplays(log);
            CheckUi(log);
            CheckGenerated(log);
            CheckMaterials(log);
            CheckScene(log);
            log.Sb.AppendLine("=== " + log.Pass + " PASS, " + log.Warn + " WARN, " + log.Fail + " FAIL ===");
            report = log.Sb.ToString();
            return log.Fail == 0;
        }

        private static void CheckWorkspace(Log log)
        {
            var root = NeramWorkspace.Root;
            if (root != null) log.P(NeramWorkspace.Describe());
            else log.F(NeramWorkspace.Describe());
        }

        private static void CheckPipeline(Log log)
        {
            var rp = GraphicsSettings.defaultRenderPipeline;
            log.Check(rp is UniversalRenderPipelineAsset, "URP pipeline asset active (" + (rp != null ? rp.name : "none") + ")");
            log.Check(Shader.Find("Universal Render Pipeline/Lit") != null, "URP Lit shader available");
        }

        private static void CheckInput(Log log)
        {
#if ENABLE_INPUT_SYSTEM
            log.P("Input System backend enabled (UI Toolkit events drive replay controls, camera and selection)");
            log.Check(Type.GetType("UnityEngine.InputSystem.UI.InputSystemUIInputModule, Unity.InputSystem") != null, "InputSystemUIInputModule type available");
#elif ENABLE_LEGACY_INPUT_MANAGER
            log.P("legacy Input Manager enabled");
#else
            log.F("no input backend: install com.unity.inputsystem or enable Active Input Handling");
#endif
            log.Check(Type.GetType("UnityEngine.EventSystems.EventSystem, UnityEngine.UI") != null, "EventSystem type available (com.unity.ugui)");
        }

        private static string Sa(params string[] parts) => Path.Combine(new[] { Application.streamingAssetsPath }.Concat(parts).ToArray());

        private static void CheckConfig(Log log)
        {
            foreach (var f in NeramSync.ConfigFiles) log.Check(File.Exists(Sa("config", f)), "StreamingAssets/config/" + f + " present");
            Try(log, "enums.json parses", () => EnumRegistry.FromJson(File.ReadAllText(Sa("config", "enums.json")), "enums.json"));
            Try(log, "params.json parses (TBD params carry no value)", () => ParamsRegistry.FromJson(File.ReadAllText(Sa("config", "params.json")), "params.json"));
            Try(log, "unity_display.json parses", () => DisplayConfig.FromJson(File.ReadAllText(Sa("config", "unity_display.json")), "unity_display.json"));
            Try(log, "unity_scenarios.json parses", () => ScenarioCatalog.ParseCatalog(File.ReadAllText(Sa("config", "unity_scenarios.json"))));
            if (File.Exists(Sa("config", "fault_codes.csv")))
                Try(log, "fault_codes.csv (hardware) parses", () => FaultCodeTable.FromCsv(File.ReadAllText(Sa("config", "fault_codes.csv")), "fault_codes.csv", false));
            else log.W("fault_codes.csv not synced: fault display texts are PLACEHOLDERS derived from the plan (hardware deliverable pending)");
            if (!File.Exists(Sa("cad", "exploded_offsets.csv"))) log.W("cad/exploded_offsets.csv not present: exploded view uses default visual offsets (CAD deliverable pending)");
        }

        private static void Try(Log log, string what, Action a)
        {
            try { a(); log.P(what); }
            catch (Exception ex) { log.F(what + ": " + ex.Message); }
        }

        private static void CheckReplays(Log log)
        {
            var dir = Sa("replays");
            if (!Directory.Exists(dir)) { log.F("StreamingAssets/replays missing (run NERAM > 2. Sync)"); return; }
            EnumRegistry enums;
            try { enums = EnumRegistry.FromJson(File.ReadAllText(Sa("config", "enums.json")), "enums.json"); }
            catch { enums = EnumRegistry.BuiltInDefault(); }
            int n = 0;
            foreach (var path in Directory.GetFiles(dir).Where(ScenarioCatalog.IsReplayFile).OrderBy(p => p, StringComparer.Ordinal))
            {
                n++;
                var r = ReplayValidator.ParseFile(path, new ReplayParseOptions { Enums = enums });
                var name = Path.GetFileName(path);
                if (r.Report.IsValid)
                {
                    log.P("replay " + name + ": " + r.Report.Summary() + " · cohort " + r.Header.Cohort + (r.Header.Placeholder ? " · labelled PLACEHOLDER/synthetic" : ""));
                }
                else
                {
                    var first = r.Report.Issues.FirstOrDefault(i => i.Severity == IssueSeverity.Error);
                    log.F("replay " + name + ": " + r.Report.Summary() + (first != null ? " | " + first : ""));
                }
            }
            if (n == 0) log.F("no replay files in StreamingAssets/replays");
        }

        private static void CheckUi(Log log)
        {
            var uxml = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(NeramSetup.UxmlPath);
            log.Check(uxml != null, NeramSetup.UxmlPath + " imports");
            var full = Path.Combine(Path.GetDirectoryName(Application.dataPath) ?? "", NeramSetup.UxmlPath);
            if (File.Exists(full))
            {
                var names = new HashSet<string>(Regex.Matches(File.ReadAllText(full), "name=\"([^\"]+)\"").Cast<Match>().Select(m => m.Groups[1].Value));
                var missing = RequiredUiNames.Where(x => !names.Contains(x)).ToList();
                log.Check(missing.Count == 0, "UXML contains all " + RequiredUiNames.Length + " required elements" + (missing.Count > 0 ? " — missing: " + string.Join(", ", missing) : ""));
            }
            var ps = AssetDatabase.LoadAssetAtPath<PanelSettings>(NeramSetup.PanelSettingsPath);
            log.Check(ps != null, "PanelSettings asset at " + NeramSetup.PanelSettingsPath + " (Resources: runtime fallback possible)");
            log.Check(ps != null && ps.themeStyleSheet != null, "PanelSettings has the runtime theme");
            log.Check(ps != null && ps.scaleMode == PanelScaleMode.ScaleWithScreenSize && ps.referenceResolution.x == 1600 && ps.referenceResolution.y == 900 && ps.screenMatchMode == PanelScreenMatchMode.Shrink, "PanelSettings scales from a 1600x900 reference, shrink-to-fit (cause if FAIL: older asset; fix: NERAM > 1. Run full setup)");
            foreach (var font in new[] { "Inter-Regular", "Inter-Medium", "Inter-SemiBold", "JetBrainsMono-Regular", "JetBrainsMono-Medium" })
                log.Check(AssetDatabase.LoadAssetAtPath<Font>("Assets/Resources/NERAM/Fonts/" + font + ".ttf") != null, "font " + font);
        }

        private static void CheckGenerated(Log log)
        {
            log.Check(AssetDatabase.LoadAssetAtPath<TextAsset>(NeramSceneBuilder.BundlePath) != null, "generated scene bundle " + NeramSceneBuilder.BundlePath);
            log.Check(AssetDatabase.LoadAssetAtPath<TextAsset>(NeramSceneBuilder.MaterialsJsonPath) != null, "material palette " + NeramSceneBuilder.MaterialsJsonPath);
            log.Check(AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(NeramSceneBuilder.MeshAssetPath) != null, "mesh asset " + NeramSceneBuilder.MeshAssetPath + " (created by setup)");
        }

        private static void CheckMaterials(Log log)
        {
            foreach (var m in SceneNames.Materials.Concat(new[] { "MAT_Halo", "MAT_Skin", "MAT_Gown", "MAT_GloveFabric", "MAT_HeaterPanel", "MAT_HeaterLayer", "MAT_BootFabric", "MAT_Outsole" }))
                log.Check(AssetDatabase.LoadAssetAtPath<Material>(NeramSetup.MaterialsDir + "/" + m + ".mat") != null, "material " + m);
        }

        /// <summary>CAD object if present, else the placeholder (explicit null checks: Unity objects overload ==).</summary>
        private static Transform FindRole(Transform asm, string role)
        {
            var cad = asm.Find(role);
            if (cad != null) return cad;
            return asm.Find(role + SceneNames.PlaceholderSuffix);
        }

        private static void CheckScene(Log log)
        {
            var full = Path.Combine(Path.GetDirectoryName(Application.dataPath) ?? "", NeramSetup.ScenePath);
            if (!File.Exists(full)) { log.F("scene " + NeramSetup.ScenePath + " missing (run NERAM > 1. Run full setup)"); return; }
            var sceneText = File.ReadAllText(full);
            log.Check(!sceneText.Contains("m_PanelSettings: {fileID: 0}"), "scene file: UIDocument PanelSettings reference is not empty (cause if FAIL: scene saved by an older/failed setup; fix: NERAM > 1. Run full setup)");
            log.Check(sceneText.Contains("generatorVersion: " + NeramVersion.Value), "scene generated by setup v" + NeramVersion.Value + " (cause if FAIL: outdated scene from an older setup; fix: NERAM > 1. Run full setup)");
            var active = EditorSceneManager.GetActiveScene();
            if (active.path != NeramSetup.ScenePath)
            {
                if (active.isDirty) { log.F("scene checks could not run: the open scene has unsaved changes; save it and open " + NeramSetup.ScenePath); return; }
                EditorSceneManager.OpenScene(NeramSetup.ScenePath);
            }
            log.Check(EditorBuildSettings.scenes.Any(s => s.path == NeramSetup.ScenePath && s.enabled), "scene in Build Settings");

            var asm = GameObject.Find(SceneNames.Assembly);
            if (asm == null) { log.F(SceneNames.Assembly + " root missing"); return; }
            log.Check(asm.GetComponent<NeramAssemblyBinder>() != null, "NeramAssemblyBinder on " + SceneNames.Assembly);
            var roles = new List<string> { SceneNames.Table, SceneNames.Mannequin, SceneNames.Controller };
            roles.AddRange(SceneNames.Modules);
            for (int ch = 1; ch <= 4; ch++) roles.Add(SceneNames.Cable(ch));
            foreach (var role in roles)
            {
                var cad = asm.transform.Find(role);
                var ph = asm.transform.Find(role + SceneNames.PlaceholderSuffix);
                if (cad != null) log.P(role + ": CAD geometry present");
                else if (ph != null) log.W(role + ": generated stand-in geometry (CAD deliverable pending)");
                else log.F(role + ": neither CAD nor generated geometry found");
            }
            for (int i = 0; i < 4; i++)
            {
                int ch = i + 1;
                var root = FindRole(asm.transform, SceneNames.Modules[i]);
                if (root == null) continue;
                var names = new HashSet<string>(root.GetComponentsInChildren<Transform>(true).Select(t => t.name));
                // CHn_Cutoff is optional in plan section W ("[CH1_Cutoff]"); a CAD module missing other parts is a CAD
                // deliverable gap (WARN, listed by name), a generated stand-in missing parts is a setup error (FAIL).
                bool isCad = asm.transform.Find(SceneNames.Modules[i]) != null;
                var missing = SceneNames.ModuleParts.Where(p => p != "Cutoff").Select(p => SceneNames.Part(ch, p)).Where(n => !names.Contains(n)).ToList();
                if (missing.Count == 0) log.P(SceneNames.Modules[i] + ": all CH" + ch + "_* parts named per CAD contract");
                else if (isCad) log.W(SceneNames.Modules[i] + ": CAD has no " + string.Join(", ", missing) + " (Neharika to add)");
                else log.F(SceneNames.Modules[i] + ": missing parts " + string.Join(", ", missing));
                var conn = asm.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == SceneNames.Connector(ch));
                log.Check(conn != null, SceneNames.Connector(ch) + " present (connection state shown at the plug)");
            }
            var ctrl = FindRole(asm.transform, SceneNames.Controller);
            if (ctrl != null)
            {
                var names = new HashSet<string>(ctrl.GetComponentsInChildren<Transform>(true).Select(t => t.name));
                var missing = SceneNames.ControllerParts.Where(n => !names.Contains(n)).ToList();
                log.Check(missing.Count == 0, "controller: all BC_* parts present" + (missing.Count > 0 ? " — missing " + string.Join(", ", missing) : ""));
            }
            var regions = UnityEngine.Object.FindObjectsByType<NeramRegion>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            foreach (var r in RequiredRegions)
            {
                var reg = regions.FirstOrDefault(x => x.region == r);
                log.Check(reg != null && reg.GetComponentInChildren<Collider>(true) != null, "selectable region " + r + " (with collider)");
            }
            log.Check(GameObject.Find("Wearable_Screen_Anchor") != null, "wearable screen anchor present");
            var input = UnityEngine.Object.FindAnyObjectByType<NeramInputController>();
            log.Check(input != null && input.rig != null && input.document != null, "NeramInputController on the camera rig (camera, hover, selection, Free Roam)");
            var modes = UnityEngine.Object.FindAnyObjectByType<VisualModeController>();
            log.Check(modes != null && modes.skinGhost != null && modes.gownGhost != null && modes.drapeGhost != null && modes.thermalMaterial != null && modes.pulseMaterial != null,
                "VisualModeController with ghost, thermal and pulse materials (Internal / Thermal views)");
            var vessels = UnityEngine.Object.FindObjectsByType<NeramVessel>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            log.Check(vessels.Length >= 10 && vessels.All(v => v.Waypoints().Length >= 2), "illustrative vessel network (" + vessels.Length + " vessels with pulse paths)");
            log.Check(UnityEngine.Object.FindObjectsByType<IvDripAnimator>(FindObjectsInactive.Include, FindObjectsSortMode.None).Length == 1, "IV drip-chamber droplet (demonstration prop)");
            var nav = UnityEngine.Object.FindObjectsByType<NeramNavVolume>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            log.Check(nav.Count(n => n.isRoom) == 1 && nav.Count(n => !n.isRoom) >= 5, "Free Roam bounds: room volume + " + nav.Count(n => !n.isRoom) + " keep-out volumes");
            log.Check(GameObject.Find(SceneNames.ThermalAnchor) != null, SceneNames.ThermalAnchor + " present");
            log.Check(UnityEngine.Object.FindObjectsByType<CameraPreset>(FindObjectsInactive.Include, FindObjectsSortMode.None).Length >= 6, "camera presets present (overview, soles, hands, wearable, torso, controller, theatre)");
            log.Check(UnityEngine.Object.FindObjectsByType<Light>(FindObjectsInactive.Exclude, FindObjectsSortMode.None).Length >= 3, "theatre lights present");
            var app = UnityEngine.Object.FindAnyObjectByType<NeramApp>();
            log.Check(app != null && app.document != null && app.loader != null && app.clock != null && app.cameraRig != null && app.assembly != null, "NeramApp references wired");
            if (app != null && app.document != null)
            {
                log.Check(app.document.visualTreeAsset != null, "UIDocument has the dashboard UXML");
                log.Check(app.document.panelSettings != null, "UIDocument has PanelSettings (without it the dashboard is invisible)");
            }
            var esType = Type.GetType("UnityEngine.EventSystems.EventSystem, UnityEngine.UI");
            log.Check(esType != null && UnityEngine.Object.FindAnyObjectByType(esType) != null, "EventSystem in the scene");
            var cam = UnityEngine.Object.FindAnyObjectByType<Camera>();
            log.Check(cam != null && cam.GetComponent<UniversalAdditionalCameraData>() != null, "camera with URP data");
        }
    }
}
