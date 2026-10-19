using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Neram.Core;
using UnityEngine;

namespace Neram.Unity
{
    /// <summary>
    /// Loads configuration and replay files from StreamingAssets, validates replays off the main thread and publishes a
    /// ReplaySession. A replay that fails validation is never handed to the views: LoadFailed fires instead and the
    /// Data Error screen is shown. Unity never computes model, controller or physiology values; it only reads them.
    ///
    /// StreamingAssets layout (populated by NERAM > Sync from repository):
    ///   config/enums.json, params.json, unity_display.json, unity_scenarios.json, interface_spec.csv,
    ///   config/fault_codes.csv (Shreehan's file, optional; a plan-derived PLACEHOLDER is used until it exists)
    ///   replays/*.jsonl | *.jsonl.gz
    /// </summary>
    public sealed class ReplayLoader : MonoBehaviour
    {
        [Tooltip("Scenario loaded automatically at start, if available.")]
        [SerializeField] private string defaultScenarioId = "SCN_C";
        [Tooltip("Override folder for replays (absolute). Empty = StreamingAssets/replays.")]
        [SerializeField] private string replayFolderOverride = "";

        public EnumRegistry Enums { get; private set; }
        public DisplayConfig Display { get; private set; }
        public FaultCodeTable Faults { get; private set; }
        public List<CatalogEntry> Catalog { get; private set; } = new List<CatalogEntry>();
        public List<ScenarioListing> Scenarios { get; private set; } = new List<ScenarioListing>();
        /// <summary>Human-readable configuration warnings shown in Diagnostics and as chips (e.g. placeholder fault table).</summary>
        public List<string> ConfigWarnings { get; } = new List<string>();
        public ReplaySession Current { get; private set; }
        public ScenarioListing CurrentListing { get; private set; }
        public bool IsLoading => _task != null;
        public int LinesParsed => Volatile.Read(ref _lines);
        public float LastLoadSeconds { get; private set; }

        public event Action<List<ScenarioListing>> CatalogChanged;
        public event Action<ScenarioListing> LoadStarted;
        public event Action<ReplaySession> SessionLoaded;
        /// <summary>(listing, parse result or null, message). The previous session stays unloaded; nothing invalid is displayed.</summary>
        public event Action<ScenarioListing, ReplayParseResult, string> LoadFailed;
        public event Action LoadCancelled;

        private string _paramsJson;
        private string _paramsOrigin;
        private Task<ReplayParseResult> _task;
        private CancellationTokenSource _cts;
        private ScenarioListing _pending;
        private int _lines;
        private float _startTime;
        private bool _started;

        public string ConfigDir => Path.Combine(Application.streamingAssetsPath, "config");
        public string ReplayDir => string.IsNullOrEmpty(replayFolderOverride) ? Path.Combine(Application.streamingAssetsPath, "replays") : replayFolderOverride;

        private void Start()
        {
            LoadConfiguration();
            RefreshCatalog();
            _started = true;
            var first = Scenarios.Find(s => s.Id == defaultScenarioId && s.Availability == ScenarioAvailability.Available)
                        ?? Scenarios.Find(s => s.Availability == ScenarioAvailability.Available);
            if (first != null) Load(first);
        }

        /// <summary>Read every configuration file. Missing or broken files fall back to plan v0.1 defaults with a visible warning.</summary>
        public void LoadConfiguration()
        {
            ConfigWarnings.Clear();
            Enums = ReadOr("enums.json", t => EnumRegistry.FromJson(t, "config/enums.json"), EnumRegistry.BuiltInDefault,
                "enums.json not readable: using the built-in plan v0.1 enumeration");
            Display = ReadOr("unity_display.json", t => DisplayConfig.FromJson(t, "config/unity_display.json"), DisplayConfig.BuiltInDefault,
                "unity_display.json not readable: using built-in display defaults");
            var paramsPath = Path.Combine(ConfigDir, "params.json");
            try
            {
                _paramsJson = File.ReadAllText(paramsPath);
                ParamsRegistry.FromJson(_paramsJson, "config/params.json"); // validate once now
                _paramsOrigin = "config/params.json";
            }
            catch (Exception ex)
            {
                _paramsJson = null;
                ConfigWarnings.Add("params.json not readable (" + ex.Message + "): parameters panel will be empty; thresholds come only from replay headers");
            }
            var faultPath = Path.Combine(ConfigDir, "fault_codes.csv");
            if (File.Exists(faultPath))
            {
                try { Faults = FaultCodeTable.FromCsv(File.ReadAllText(faultPath), "hardware/interfaces/fault_codes.csv", false); }
                catch (Exception ex)
                {
                    ConfigWarnings.Add("fault_codes.csv is invalid (" + ex.Message + "): using the PLACEHOLDER table derived from the plan");
                    Faults = null;
                }
            }
            if (Faults == null)
            {
                Faults = FaultCodeTable.FromCsv(FaultCodeTable.PlaceholderCsvFromPlan(), "PLACEHOLDER fault table (plan section 3W)", true);
                ConfigWarnings.Add("Fault-code display texts are PLACEHOLDERS derived from the plan until Shreehan's fault_codes.csv is synced");
            }
            Catalog = ReadOr("unity_scenarios.json", ScenarioCatalog.ParseCatalog, () => new List<CatalogEntry>(),
                "unity_scenarios.json not readable: only replay files found on disk are listed");
        }

        private T ReadOr<T>(string file, Func<string, T> parse, Func<T> fallback, string warning)
        {
            var path = Path.Combine(ConfigDir, file);
            try { return parse(File.ReadAllText(path)); }
            catch (Exception ex)
            {
                ConfigWarnings.Add(warning + " (" + ex.Message + ")");
                Debug.LogWarning("[NERAM] " + warning + ": " + ex.Message);
                return fallback();
            }
        }

        public void RefreshCatalog()
        {
            Scenarios = ScenarioCatalog.Discover(ReplayDir, Catalog);
            CatalogChanged?.Invoke(Scenarios);
        }

        public ParamsRegistry NewParams() =>
            _paramsJson != null ? ParamsRegistry.FromJson(_paramsJson, _paramsOrigin) : ParamsRegistry.Empty("no params.json");

        public double TwinPeriodSeconds()
        {
            var p = NewParams().GetOrNull("ts_twin_s");
            var v = p != null ? p.EffectiveScalar : double.NaN;
            return double.IsNaN(v) || v <= 0 ? 60.0 : v;
        }

        /// <summary>Start loading a scenario. Any load in progress is cancelled.</summary>
        public void Load(ScenarioListing listing)
        {
            if (listing == null || listing.FilePath == null) return;
            Cancel();
            _pending = listing;
            _lines = 0;
            _cts = new CancellationTokenSource();
            var opts = new ReplayParseOptions
            {
                Enums = Enums,
                TwinPeriodS = TwinPeriodSeconds(),
                LineProgress = n => Volatile.Write(ref _lines, n),
                Cancel = _cts.Token,
            };
            var path = listing.FilePath;
            _startTime = Time.realtimeSinceStartup;
            _task = Task.Run(() => ReplayValidator.ParseFile(path, opts));
            LoadStarted?.Invoke(listing);
        }

        public void Cancel()
        {
            if (_task == null) return;
            _cts?.Cancel();
        }

        private void Update()
        {
            if (!_started || _task == null || !_task.IsCompleted) return;
            var task = _task;
            var listing = _pending;
            _task = null;
            _pending = null;
            LastLoadSeconds = Time.realtimeSinceStartup - _startTime;
            if (task.IsFaulted)
            {
                var msg = task.Exception?.GetBaseException().Message ?? "unknown error";
                Debug.LogError("[NERAM] replay load failed: " + msg);
                LoadFailed?.Invoke(listing, null, msg);
                return;
            }
            var result = task.Result;
            if (result.Cancelled) { LoadCancelled?.Invoke(); return; }
            if (!result.Report.IsValid || result.Table == null)
            {
                Debug.LogWarning("[NERAM] replay rejected: " + listing.FilePath + " - " + result.Report.Summary());
                LoadFailed?.Invoke(listing, result, "Replay rejected by validation");
                return;
            }
            try
            {
                var session = new ReplaySession(result.Header, result.Table, result.Report, Enums, NewParams(), Faults, Display, listing.FilePath);
                Current = session;
                CurrentListing = listing;
                SessionLoaded?.Invoke(session);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                LoadFailed?.Invoke(listing, result, "Session could not be built: " + ex.Message);
            }
        }

        private void OnDestroy() => _cts?.Cancel();
    }
}
