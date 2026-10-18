using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>
    /// Locates the NERAM workspace root (the folder that holds config/ and integration/replays/) by MARKER FOLDERS, not
    /// by a fixed depth or an absolute path. The Unity project can therefore live at any depth below the workspace, e.g.
    ///   NERAM_Unity_Workspace_v2/unity_editor/Assets                     (v2 layout)
    ///   ...\NERAM_unity_layer_1\unity_editor\Assets                       (existing layout)
    ///   NERAM_Unity_Project_Ready/unity/Assets                           (v1 layout)
    ///
    /// Resolution order (first match wins):
    ///   1. EditorPrefs override "NERAM.WorkspaceRoot" (menu NERAM > Workspace > Choose workspace folder...)
    ///   2. environment variable NERAM_WORKSPACE_ROOT (or legacy NERAM_REPO_ROOT)
    ///   3. walk upward from the Unity project folder, at most <see cref="MaxLevels"/> levels
    /// A candidate is accepted only if it contains BOTH markers: config/enums.json and the directory integration/replays.
    /// If nothing matches, <see cref="Root"/> is null and <see cref="Describe"/> lists every folder that was searched;
    /// callers must report that as a FAILURE (it is never downgraded to a warning).
    /// </summary>
    public static class NeramWorkspace
    {
        public const string PrefKey = "NERAM.WorkspaceRoot";
        public const int MaxLevels = 6;
        public static readonly string[] MarkerFiles = { "config/enums.json" };
        public static readonly string[] MarkerDirs = { "integration/replays" };

        private static readonly List<string> _searched = new List<string>();
        private static string _source = "";

        /// <summary>Unity project folder (parent of Assets).</summary>
        public static string ProjectDir => Path.GetFullPath(Path.Combine(Application.dataPath, ".."));

        /// <summary>The workspace root, or null when no folder with the marker files was found.</summary>
        public static string Root => Resolve();

        /// <summary>How the root was found ("EditorPrefs override", "environment", "parent search") or why not.</summary>
        public static string Source { get { Resolve(); return _source; } }

        public static bool IsWorkspace(string dir)
        {
            if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir)) return false;
            foreach (var f in MarkerFiles) if (!File.Exists(Path.Combine(dir, f))) return false;
            foreach (var d in MarkerDirs) if (!Directory.Exists(Path.Combine(dir, d))) return false;
            return true;
        }

        public static string Resolve()
        {
            _searched.Clear();
            var pref = EditorPrefs.GetString(PrefKey, "");
            if (!string.IsNullOrEmpty(pref))
            {
                _searched.Add(pref + "  (EditorPrefs override)");
                if (IsWorkspace(pref)) { _source = "EditorPrefs override"; return Path.GetFullPath(pref); }
            }
            foreach (var env in new[] { "NERAM_WORKSPACE_ROOT", "NERAM_REPO_ROOT" })
            {
                var v = Environment.GetEnvironmentVariable(env);
                if (string.IsNullOrEmpty(v)) continue;
                _searched.Add(v + "  (environment " + env + ")");
                if (IsWorkspace(v)) { _source = "environment " + env; return Path.GetFullPath(v); }
            }
            var d = new DirectoryInfo(ProjectDir);
            for (int level = 0; d != null && level <= MaxLevels; level++, d = d.Parent)
            {
                _searched.Add(d.FullName);
                if (IsWorkspace(d.FullName)) { _source = "parent search (" + level + " level" + (level == 1 ? "" : "s") + " above the Unity project)"; return d.FullName; }
            }
            _source = "NOT FOUND";
            return null;
        }

        /// <summary>Human-readable result including every searched folder (for logs and validation).</summary>
        public static string Describe()
        {
            var root = Resolve();
            if (root != null) return "workspace root: " + root + "  [" + _source + "]";
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("workspace root NOT FOUND. A workspace folder must contain config/enums.json and integration/replays/.");
            sb.AppendLine("Searched:");
            foreach (var s in _searched) sb.AppendLine("  " + s);
            sb.Append("Fix: keep the Unity project inside the workspace (e.g. <workspace>/unity_editor), or use NERAM > Workspace > Choose workspace folder...");
            return sb.ToString();
        }

        [MenuItem("NERAM/Workspace/Show workspace root", priority = 40)]
        public static void ShowMenu()
        {
            var text = Describe();
            Debug.Log("[NERAM] " + text);
            EditorUtility.DisplayDialog("NERAM workspace", text, "OK");
        }

        [MenuItem("NERAM/Workspace/Choose workspace folder...", priority = 41)]
        public static void ChooseMenu()
        {
            var start = Resolve() ?? ProjectDir;
            var picked = EditorUtility.OpenFolderPanel("Select the NERAM workspace folder (contains config/ and integration/)", start, "");
            if (string.IsNullOrEmpty(picked)) return;
            if (!IsWorkspace(picked))
            {
                EditorUtility.DisplayDialog("NERAM workspace", "That folder does not contain config/enums.json and integration/replays/.\nNothing was changed.", "OK");
                return;
            }
            EditorPrefs.SetString(PrefKey, picked);
            Debug.Log("[NERAM] workspace override set: " + picked);
        }

        [MenuItem("NERAM/Workspace/Clear workspace override", priority = 42)]
        public static void ClearMenu()
        {
            EditorPrefs.DeleteKey(PrefKey);
            Debug.Log("[NERAM] workspace override cleared; " + Describe());
        }
    }
}
