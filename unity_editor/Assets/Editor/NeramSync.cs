using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Neram.Core;
using UnityEditor;
using UnityEngine;

namespace Neram.EditorTools
{
    /// <summary>
    /// Copies team outputs from the repository into StreamingAssets (same behaviour as tools/sync_unity_streaming_assets.py):
    ///   config/{enums.json, params.json, unity_display.json, unity_scenarios.json, interface_spec.csv} -> StreamingAssets/config/
    ///   hardware/interfaces/fault_codes.csv (Shreehan, optional)                                   -> StreamingAssets/config/
    ///   cad/exploded_offsets.csv (Neharika, optional)                                              -> StreamingAssets/cad/
    ///   integration/replays/*.jsonl(.gz)                                                           -> StreamingAssets/replays/
    /// HOLDOUT GUARD: every replay is fully validated before it is copied. A file whose header cohort is not SYNTHETIC or
    /// DEVELOPMENT (or that fails validation for any other reason) is NOT copied, so final-holdout data can never reach
    /// the Unity build, demo, screenshots or videos.
    /// </summary>
    public static class NeramSync
    {
        public static readonly string[] ConfigFiles = { "enums.json", "params.json", "unity_display.json", "unity_scenarios.json", "interface_spec.csv" };

        /// <summary>Workspace root located by marker folders (config/enums.json + integration/replays/); null if not found.
        /// See <see cref="NeramWorkspace"/>. No fixed depth and no absolute path is assumed.</summary>
        public static string RepoRoot => NeramWorkspace.Root;
        public static string StreamingAssets => Application.streamingAssetsPath;

        public sealed class Result
        {
            public readonly List<string> Copied = new List<string>();
            public readonly List<string> Skipped = new List<string>();
            public readonly List<string> Rejected = new List<string>();
            public readonly List<string> Missing = new List<string>();
            /// <summary>Non-empty when the sync could not run at all (e.g. workspace not found). Always a FAILURE.</summary>
            public string Fatal;
            public bool Ok => Fatal == null && Rejected.Count == 0;

            public override string ToString()
            {
                var sb = new StringBuilder();
                if (Fatal != null) { sb.AppendLine("NERAM sync FAILED: " + Fatal); return sb.ToString(); }
                sb.AppendLine("NERAM sync from " + NeramWorkspace.Describe());
                sb.AppendLine("copied: " + Copied.Count + ", unchanged: " + Skipped.Count + ", REJECTED: " + Rejected.Count + ", missing (optional/awaiting): " + Missing.Count);
                foreach (var r in Rejected) sb.AppendLine("  REJECTED " + r);
                foreach (var m in Missing) sb.AppendLine("  missing  " + m);
                foreach (var c in Copied) sb.AppendLine("  copied   " + c);
                return sb.ToString();
            }
        }

        [MenuItem("NERAM/2. Sync config + replays from repository", priority = 2)]
        public static void SyncMenu()
        {
            var r = Sync();
            Debug.Log(r.ToString());
            EditorUtility.DisplayDialog("NERAM sync", r.ToString(), "OK");
        }

        public static Result Sync()
        {
            var res = new Result();
            var repo = RepoRoot;
            if (repo == null)
            {
                res.Fatal = NeramWorkspace.Describe();
                Debug.LogError("[NERAM] " + res.Fatal);
                return res;
            }
            var cfgDst = Path.Combine(StreamingAssets, "config");
            var repDst = Path.Combine(StreamingAssets, "replays");
            var cadDst = Path.Combine(StreamingAssets, "cad");
            Directory.CreateDirectory(cfgDst);
            Directory.CreateDirectory(repDst);
            Directory.CreateDirectory(cadDst);

            foreach (var f in ConfigFiles) CopyIfExists(Path.Combine(repo, "config", f), Path.Combine(cfgDst, f), res, required: true);
            CopyIfExists(Path.Combine(repo, "hardware", "interfaces", "fault_codes.csv"), Path.Combine(cfgDst, "fault_codes.csv"), res, required: false);
            CopyIfExists(Path.Combine(repo, "cad", "exploded_offsets.csv"), Path.Combine(cadDst, "exploded_offsets.csv"), res, required: false);

            // Enum registry for validation: the repository copy (falls back to the plan v0.1 built-in table).
            EnumRegistry enums;
            try { enums = EnumRegistry.FromJson(File.ReadAllText(Path.Combine(repo, "config", "enums.json")), "config/enums.json"); }
            catch { enums = EnumRegistry.BuiltInDefault(); }

            var src = Path.Combine(repo, "integration", "replays");
            if (!Directory.Exists(src)) res.Missing.Add("integration/replays/ (no replay files yet)");
            else
            {
                foreach (var path in Directory.GetFiles(src))
                {
                    if (!ScenarioCatalog.IsReplayFile(path)) continue;
                    var name = Path.GetFileName(path);
                    var pr = ReplayValidator.ParseFile(path, new ReplayParseOptions { Enums = enums });
                    if (!pr.Report.IsValid)
                    {
                        res.Rejected.Add(name + " — " + pr.Report.Summary() + FirstErrors(pr.Report));
                        // A rejected file must not linger from an earlier sync.
                        var stale = Path.Combine(repDst, name);
                        if (File.Exists(stale)) { File.Delete(stale); DeleteMeta(stale); }
                        continue;
                    }
                    CopyIfExists(path, Path.Combine(repDst, name), res, required: true);
                }
            }
            AssetDatabase.Refresh();
            return res;
        }

        private static string FirstErrors(ValidationReport rep)
        {
            var sb = new StringBuilder();
            int n = 0;
            foreach (var i in rep.Issues)
            {
                if (i.Severity != IssueSeverity.Error) continue;
                sb.Append(" | ").Append(i.ToString());
                if (++n == 3) break;
            }
            return sb.ToString();
        }

        private static void CopyIfExists(string src, string dst, Result res, bool required)
        {
            if (!File.Exists(src))
            {
                res.Missing.Add(Rel(src) + (required ? "" : " (optional, team deliverable not yet in repo)"));
                return;
            }
            if (File.Exists(dst) && SameBytes(src, dst)) { res.Skipped.Add(Rel(src)); return; }
            File.Copy(src, dst, true);
            res.Copied.Add(Rel(src));
        }

        private static bool SameBytes(string a, string b)
        {
            var fa = new FileInfo(a);
            var fb = new FileInfo(b);
            if (fa.Length != fb.Length) return false;
            return Convert.ToBase64String(File.ReadAllBytes(a)) == Convert.ToBase64String(File.ReadAllBytes(b));
        }

        private static void DeleteMeta(string path)
        {
            var meta = path + ".meta";
            if (File.Exists(meta)) File.Delete(meta);
        }

        private static string Rel(string p)
        {
            var rr = RepoRoot;
            if (rr == null) return p;
            var root = rr.Replace('\\', '/').TrimEnd('/') + "/";
            var s = p.Replace('\\', '/');
            return s.StartsWith(root, StringComparison.Ordinal) ? s.Substring(root.Length) : s;
        }
    }
}
