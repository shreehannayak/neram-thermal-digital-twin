using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>
    /// Standalone Windows build of the NERAM replay viewer (Windows 64-bit, Mono scripting backend, which ships with every
    /// Windows Editor install).
    ///
    /// Menu:  NERAM > 6. Build Windows player · NERAM > 7. Run Windows player (starts the built NERAM.exe)
    /// Batch: Unity.exe -batchmode -quit -projectPath &lt;workspace&gt;\unity_editor -executeMethod Neram.EditorTools.NeramBuild.BuildWindowsBatch
    ///
    /// Output: &lt;workspace&gt;\build\NERAM_Windows\NERAM.exe (next to unity_editor, outside Assets). The build contains the scene
    /// NERAM_OR_Replay and StreamingAssets (config + validated SYNTHETIC/DEVELOPMENT replays) exactly as setup synced them.
    /// Player defaults: maximised desktop window with the NERAM icon (pinnable to the taskbar), resizable window, runs in background,
    /// so the FULLSCREEN / EXIT FULLSCREEN button and F11 can switch between window and fullscreen.
    /// Build settings are applied to PlayerSettings (they persist in ProjectSettings/ProjectSettings.asset).
    /// </summary>
    public static class NeramBuild
    {
        public const string ProductName = "NERAM Thermal Twin Viewer";
        public const string AppIconPath = "Assets/Settings/neram_app_icon.png";

        [MenuItem("NERAM/6. Build Windows player", priority = 6)]
        public static void BuildWindowsMenu()
        {
            if (!EditorUtility.DisplayDialog("NERAM build",
                    "Build the standalone Windows player?\n\nOutput: " + OutputPath() + "\n\nRun NERAM > 1. Run full setup first so the scene and StreamingAssets are current.",
                    "Build", "Cancel")) return;
            var (ok, msg) = BuildWindows();
            if (ok) Debug.Log(msg); else Debug.LogError(msg);
            EditorUtility.DisplayDialog("NERAM build", msg, "OK");
            if (ok) EditorUtility.RevealInFinder(OutputPath());
        }

        [MenuItem("NERAM/7. Run Windows player", priority = 7)]
        public static void RunWindowsPlayer()
        {
            var exe = OutputPath();
            if (!File.Exists(exe))
            {
                EditorUtility.DisplayDialog("NERAM", "No player found at\n" + exe + "\n\nUse NERAM > 6. Build Windows player first.", "OK");
                return;
            }
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(exe)
            {
                WorkingDirectory = Path.GetDirectoryName(exe) ?? ".",
                UseShellExecute = true,
            });
        }

        /// <summary>Batch entry point. Exit code 0 = build succeeded, 1 = build failed, 2 = exception.</summary>
        public static void BuildWindowsBatch()
        {
            try
            {
                var (ok, msg) = BuildWindows();
                Debug.Log(msg);
                EditorApplication.Exit(ok ? 0 : 1);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                EditorApplication.Exit(2);
            }
        }

        public static string OutputPath()
        {
            var project = Path.GetDirectoryName(Application.dataPath) ?? "";
            var workspace = Path.GetDirectoryName(project) ?? project;
            return Path.Combine(workspace, "build", "NERAM_Windows", "NERAM.exe");
        }

        public static (bool ok, string message) BuildWindows()
        {
            if (!File.Exists(Path.Combine(Path.GetDirectoryName(Application.dataPath) ?? "", NeramSetup.ScenePath)))
                return (false, "Build stopped: " + NeramSetup.ScenePath + " does not exist. Run NERAM > 1. Run full setup first.");

            PlayerSettings.productName = ProductName;
            // Opens as a normal maximised desktop window (title bar, taskbar icon, pinnable); F11 / FULLSCREEN still
            // switch to borderless fullscreen. (18 Oct 2026)
            PlayerSettings.fullScreenMode = FullScreenMode.MaximizedWindow;
            var icon = AssetDatabase.LoadAssetAtPath<Texture2D>(AppIconPath);
            if (icon != null) PlayerSettings.SetIcons(UnityEditor.Build.NamedBuildTarget.Unknown, new[] { icon }, IconKind.Any);
            else Debug.LogWarning("[NERAM] app icon not found at " + AppIconPath + "; the default Unity icon is used");
            PlayerSettings.defaultIsNativeResolution = true;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.defaultScreenWidth = 1600;
            PlayerSettings.defaultScreenHeight = 900;

            var output = OutputPath();
            Directory.CreateDirectory(Path.GetDirectoryName(output) ?? ".");
            var options = new BuildPlayerOptions
            {
                scenes = new[] { NeramSetup.ScenePath },
                locationPathName = output,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None,
            };
            BuildReport report = BuildPipeline.BuildPlayer(options);
            var summary = report.summary;
            if (summary.result == BuildResult.Succeeded)
                return (true, string.Format("NERAM Windows player built: {0} ({1:0.0} MB, {2:0} s). Run NERAM.exe; F11 or FULLSCREEN toggles fullscreen.",
                    output, summary.totalSize / (1024.0 * 1024.0), summary.totalTime.TotalSeconds));
            return (false, "NERAM Windows build " + summary.result + " with " + summary.totalErrors + " error(s). See the Console. " +
                           "If the error mentions the Windows build target, add 'Windows Build Support' for 6000.3.26f1 in Unity Hub > Installs.");
        }
    }
}
