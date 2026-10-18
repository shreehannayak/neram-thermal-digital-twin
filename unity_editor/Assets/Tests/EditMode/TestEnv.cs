using System;
using System.IO;
using Neram.Core;

namespace Neram.Tests
{
    /// <summary>Locates the repository, configuration and replay files for tests, inside or outside Unity.</summary>
    public static class TestEnv
    {
        private static string _root;

        /// <summary>Workspace root: the folder that contains config/enums.json and integration/replays/ (marker search,
        /// no fixed depth). Works for &lt;ws&gt;/unity_editor (v2), &lt;ws&gt;/unity (v1) and any deeper nesting.</summary>
        public static string RepoRoot
        {
            get
            {
                if (_root != null) return _root;
                foreach (var name in new[] { "NERAM_WORKSPACE_ROOT", "NERAM_REPO_ROOT" })
                {
                    var env = Environment.GetEnvironmentVariable(name);
                    if (IsWorkspace(env)) return _root = env;
                }
#if UNITY_5_3_OR_NEWER
                var start = UnityEngine.Application.dataPath;
#else
                var start = AppContext.BaseDirectory;
#endif
                var d = new DirectoryInfo(start);
                while (d != null)
                {
                    if (IsWorkspace(d.FullName)) return _root = d.FullName;
                    d = d.Parent;
                }
                return _root = null;
            }
        }

        public static bool IsWorkspace(string dir) =>
            !string.IsNullOrEmpty(dir) && File.Exists(Path.Combine(dir, "config", "enums.json")) && Directory.Exists(Path.Combine(dir, "integration", "replays"));

        public static string UnityAssets
        {
            get
            {
#if UNITY_5_3_OR_NEWER
                return UnityEngine.Application.dataPath;
#else
                foreach (var project in new[] { "unity_editor", "unity" })
                {
                    var p = Path.Combine(RepoRoot, project, "Assets");
                    if (Directory.Exists(Path.Combine(p, "Tests"))) return p;
                }
                return Path.Combine(RepoRoot, "unity_editor", "Assets");
#endif
            }
        }

        public static string Fixtures => Path.Combine(UnityAssets, "Tests", "Fixtures");

        /// <summary>config/&lt;name&gt; at the repository root, falling back to the StreamingAssets copy.</summary>
        public static string ConfigPath(string name)
        {
            if (RepoRoot != null)
            {
                var p = Path.Combine(RepoRoot, "config", name);
                if (File.Exists(p)) return p;
            }
            return Path.Combine(UnityAssets, "StreamingAssets", "config", name);
        }

        public static string ReplayDir
        {
            get
            {
                if (RepoRoot != null)
                {
                    var p = Path.Combine(RepoRoot, "integration", "replays");
                    if (Directory.Exists(p)) return p;
                }
                return Path.Combine(UnityAssets, "StreamingAssets", "replays");
            }
        }

        public static string ReplayPath(string scenarioId) => Path.Combine(ReplayDir, scenarioId + ".jsonl.gz");

        public static EnumRegistry Enums() => EnumRegistry.FromJson(File.ReadAllText(ConfigPath("enums.json")), "config/enums.json");
        public static ParamsRegistry Params() => ParamsRegistry.FromJson(File.ReadAllText(ConfigPath("params.json")), "config/params.json");
        public static DisplayConfig Display() => DisplayConfig.FromJson(File.ReadAllText(ConfigPath("unity_display.json")), "config/unity_display.json");
        public static FaultCodeTable Faults() => FaultCodeTable.FromCsv(FaultCodeTable.PlaceholderCsvFromPlan(), "placeholder (plan section 3W)", true);

        public static ReplayParseOptions Options() => new ReplayParseOptions { Enums = Enums(), TwinPeriodS = 60 };

        public static ReplaySession Session(string scenarioId)
        {
            var path = ReplayPath(scenarioId);
            var r = ReplayValidator.ParseFile(path, Options());
            if (!r.Report.IsValid) throw new InvalidOperationException(scenarioId + " is invalid: " + r.Report.Summary());
            return new ReplaySession(r.Header, r.Table, r.Report, Enums(), Params(), Faults(), Display(), path);
        }

        public static ReplayParseResult ParseText(string text) => ReplayValidator.ParseString(text, Options());

        /// <summary>Frame index at replay time mm:ss.</summary>
        public static int FrameAt(ReplaySession s, int minutes, int seconds = 0) => s.Table.FrameAtTime(minutes * 60 + seconds);
    }
}
