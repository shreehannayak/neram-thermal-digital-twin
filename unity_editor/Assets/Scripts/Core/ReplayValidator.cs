using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Neram.Core
{
    public sealed class ReplayParseOptions
    {
        /// <summary>Enum registry used to check integer enums (from config/enums.json).</summary>
        public EnumRegistry Enums;
        /// <summary>Twin update period in seconds (params ts_twin_s, FROZEN = 60). Used only to bucket minutes for display.</summary>
        public double TwinPeriodS = 60.0;
        /// <summary>Called every ProgressEveryLines lines with the current line number (may run on a worker thread).</summary>
        public Action<int> LineProgress;
        public int ProgressEveryLines = 500;
        public CancellationToken Cancel = CancellationToken.None;
    }

    public sealed class ReplayParseResult
    {
        public ReplayHeader Header;
        /// <summary>Non-null only when the file passed validation (Report.IsValid).</summary>
        public ReplayTable Table;
        public ValidationReport Report;
        public int LineCount;
        public bool Cancelled;
        public string SourcePath;
    }

    /// <summary>
    /// Streaming parser + strict validator for NERAM replay JSONL (rules: unity/schema/VALIDATION_RULES.md).
    /// The same rules are implemented in integration/validate_replay.py; both are tested on one fixture corpus.
    /// This class checks that external data is well-formed and self-consistent. It never decides what the
    /// controller should have done.
    /// </summary>
    public static class ReplayValidator
    {
        public static ReplayParseResult ParseFile(string path, ReplayParseOptions options)
        {
            using (var reader = ReplayFileReader.OpenText(path))
            {
                var r = Parse(reader, options);
                r.SourcePath = path;
                return r;
            }
        }

        public static ReplayParseResult ParseString(string text, ReplayParseOptions options)
        {
            using (var reader = new StringReader(text)) return Parse(reader, options);
        }

        public static ReplayParseResult Parse(TextReader reader, ReplayParseOptions options)
        {
            if (options == null) throw new ArgumentNullException(nameof(options));
            if (options.Enums == null) throw new ArgumentException("ReplayParseOptions.Enums is required");
            var ctx = new Context(options);
            string raw;
            while ((raw = reader.ReadLine()) != null)
            {
                ctx.Line++;
                if (options.Cancel.IsCancellationRequested) { ctx.Result.Cancelled = true; break; }
                if (options.LineProgress != null && ctx.Line % options.ProgressEveryLines == 0) options.LineProgress(ctx.Line);
                if (raw.Trim().Length == 0) continue;
                ctx.ProcessLine(raw);
                if (ctx.Fatal || ctx.Report.StopRequested) break;
            }
            return ctx.Finish();
        }

        private sealed class Context
        {
            public readonly ReplayParseOptions Opt;
            public readonly ValidationReport Report = new ValidationReport();
            public readonly ReplayParseResult Result = new ReplayParseResult();
            public int Line;
            public bool Fatal;
            private ReplayHeader _header;
            private readonly ColumnBuilder _cols = new ColumnBuilder(ReplayFields.Count);
            private double _firstStep = double.NaN;
            private string _prevPlantMode;
            private readonly Dictionary<string, string> _prevTags = new Dictionary<string, string>();
            private bool _proposedCtrlNoted;

            // Resolved once: integer values of FROZEN names (integers are PROVISIONAL, names are not).
            private readonly int _valid, _noData, _shutdown, _degraded, _subNone;

            // Field handles
            private readonly FieldDef _t, _tObs, _obsMissing, _tEst, _tEstSd, _twinValid, _state, _sub, _safety,
                _plantMode, _tPlant, _dTHeat;
            private readonly FieldDef[] _forecast, _heat, _chFault;
            private readonly FieldDef[,] _bounds; // [h, 0..4] = mean, L80, U80, L95, U95

            public Context(ReplayParseOptions opt)
            {
                Opt = opt;
                Result.Report = Report;
                var e = opt.Enums;
                _valid = e.ValueOf(EnumNames.TwinValid, "VALID");
                _noData = e.ValueOf(EnumNames.TwinValid, "NO_DATA");
                _shutdown = e.ValueOf(EnumNames.ControllerState, "SAFETY_SHUTDOWN");
                _degraded = e.ValueOf(EnumNames.ControllerState, "TWIN_DEGRADED");
                _subNone = e.ValueOf(EnumNames.DegradedSubstate, "NONE");
                _t = ReplayFields.Get("meta", "t_s");
                _tObs = ReplayFields.Get("obs", "T_obs");
                _obsMissing = ReplayFields.Get("obs", "obs_missing");
                _tEst = ReplayFields.Get("twin", "T_est");
                _tEstSd = ReplayFields.Get("twin", "T_est_sd");
                _twinValid = ReplayFields.Get("twin", "Twin_Valid");
                _state = ReplayFields.Get("ctrl", "Controller_State");
                _sub = ReplayFields.Get("ctrl", "Degraded_Substate");
                _safety = ReplayFields.Get("ctrl", "Safety_Shutdown");
                _plantMode = ReplayFields.Get("plant", "plant_mode");
                _tPlant = ReplayFields.Get("plant", "T_plant");
                _dTHeat = ReplayFields.Get("plant", "dT_heat");
                _forecast = new FieldDef[ReplayFields.ForecastFieldNames.Length];
                for (int i = 0; i < _forecast.Length; i++) _forecast[i] = ReplayFields.Get("twin", ReplayFields.ForecastFieldNames[i]);
                _bounds = new FieldDef[3, 5];
                for (int h = 0; h < 3; h++)
                {
                    var hz = ReplayFields.Horizons[h];
                    _bounds[h, 0] = ReplayFields.Get("twin", "T_pred_" + hz);
                    _bounds[h, 1] = ReplayFields.Get("twin", "L80_" + hz);
                    _bounds[h, 2] = ReplayFields.Get("twin", "U80_" + hz);
                    _bounds[h, 3] = ReplayFields.Get("twin", "L95_" + hz);
                    _bounds[h, 4] = ReplayFields.Get("twin", "U95_" + hz);
                }
                _heat = new FieldDef[4];
                _chFault = new FieldDef[4];
                for (int i = 0; i < 4; i++)
                {
                    _heat[i] = ReplayFields.Get("ctrl", "Heat_" + (i + 1));
                    _chFault[i] = ReplayFields.Get("ctrl", "Channel_Fault_" + (i + 1));
                }
            }

            public void ProcessLine(string raw)
            {
                JToken tok;
                try
                {
                    tok = StrictJson.Parse(raw);
                }
                catch (JsonReaderException ex)
                {
                    var dup = ex.Message.IndexOf("already exists", StringComparison.OrdinalIgnoreCase) >= 0;
                    Report.Error(dup ? "E093" : "E090", Line, null, dup ? "duplicate key: " + ex.Message : "invalid JSON: " + ex.Message);
                    if (_header == null) Fatal = true;
                    return;
                }
                var obj = tok as JObject;
                if (obj == null)
                {
                    Report.Error("E091", Line, null, "line is not a JSON object");
                    if (_header == null) Fatal = true;
                    return;
                }
                if (_header == null)
                {
                    _header = ReplayHeader.Parse(obj, Line, Report);
                    Result.Header = _header;
                    if (_header == null) Fatal = true;
                    return;
                }
                var type = obj["type"];
                if (type == null || type.Type != JTokenType.String)
                {
                    Report.Error("E092", Line, "type", "frame line must have \"type\": \"frame\"");
                    return;
                }
                var ts = (string)type;
                if (ts == "header") { Report.Error("E092", Line, "type", "second header line"); return; }
                if (ts != "frame") { Report.Error("E092", Line, "type", "unknown line type '" + ts + "'"); return; }
                ValidateFrame(obj);
            }

            private void ValidateFrame(JObject obj)
            {
                int row = _cols.AddRow();
                foreach (var p in obj.Properties())
                {
                    if (p.Name == "type") continue;
                    if (!ReplayFields.IsGroup(p.Name)) Report.Error("E080", Line, p.Name, "unknown group");
                }
                foreach (var g in ReplayFields.Groups)
                {
                    var gt = obj[g];
                    if (gt == null) { Report.Error("E010", Line, g, "group missing"); continue; }
                    if (gt.Type != JTokenType.Object) { Report.Error("E011", Line, g, "group must be an object"); continue; }
                    var go = (JObject)gt;
                    foreach (var p in go.Properties())
                        if (!ReplayFields.TryGet(g, p.Name, out _)) Report.Error("E080", Line, g + "." + p.Name, "unknown field");
                    foreach (var f in ReplayFields.InGroup(g)) ReadField(go, f, row);
                }
                CrossChecks(row);
            }

            private void ReadField(JObject go, FieldDef f, int row)
            {
                var tok = go[f.Name];
                if (tok == null)
                {
                    if (!f.Optional) Report.Error("E010", Line, f.Key, "field missing");
                    return;
                }
                if (f.Proposed && !_proposedCtrlNoted)
                {
                    _proposedCtrlNoted = true;
                    Report.Info("I201", Line, f.Key, "proposed frame field present (not yet in interface spec v0.1)");
                }
                if (tok.Type == JTokenType.Null)
                {
                    if (!f.Nullable) Report.Error("E012", Line, f.Key, "null is not allowed");
                    return;
                }
                double v;
                switch (f.Kind)
                {
                    case FieldKind.Number:
                        if (tok.Type != JTokenType.Integer && tok.Type != JTokenType.Float) { TypeError(f, "number"); return; }
                        v = (double)tok;
                        if (double.IsNaN(v) || double.IsInfinity(v)) { Report.Error("E011", Line, f.Key, "NaN/Infinity literals are not allowed; use null"); return; }
                        break;
                    case FieldKind.Int:
                    case FieldKind.Enum:
                        if (tok.Type != JTokenType.Integer) { TypeError(f, "integer"); return; }
                        v = (long)tok;
                        break;
                    case FieldKind.Bool:
                        if (tok.Type != JTokenType.Boolean) { TypeError(f, "true/false"); return; }
                        v = (bool)tok ? 1.0 : 0.0;
                        break;
                    case FieldKind.String:
                        if (tok.Type != JTokenType.String) { TypeError(f, "string"); return; }
                        CheckMetaString(f, (string)tok);
                        return;
                    case FieldKind.StringEnum:
                        if (tok.Type != JTokenType.String) { TypeError(f, "string"); return; }
                        var s = (string)tok;
                        int idx = StringEnums.IndexOf(f.EnumName, s);
                        if (idx < 0) { Report.Error("E014", Line, f.Key, "unknown " + f.EnumName + " '" + s + "'"); return; }
                        if (f.Group == "src" && ReplayFields.AllowedSourceTags.TryGetValue(f.Name, out var allowed) && Array.IndexOf(allowed, s) < 0)
                            Report.Error("E050", Line, f.Key, "source tag '" + s + "' not allowed for group " + f.Name + " (allowed: " + string.Join(", ", allowed) + ")");
                        v = idx;
                        break;
                    default:
                        return;
                }
                if (f.RangeMode != RangeMode.None)
                {
                    bool low = !double.IsNaN(f.Min) && v < f.Min;
                    bool high = !double.IsNaN(f.Max) && v > f.Max;
                    if (low || high)
                    {
                        var msg = "value " + v.ToString(System.Globalization.CultureInfo.InvariantCulture) + " outside [" + Fmt(f.Min) + ", " + Fmt(f.Max) + "]";
                        if (f.RangeMode == RangeMode.Error) Report.Error("E013", Line, f.Key, msg);
                        else Report.Warn("W102", Line, f.Key, msg);
                    }
                }
                if (f.Kind == FieldKind.Enum && !Opt.Enums.IsKnown(f.EnumName, (int)v))
                    Report.Error("E014", Line, f.Key, "value " + (int)v + " is not defined in " + f.EnumName + " (" + Opt.Enums.Origin + ")");
                _cols.Set(f.Id, row, v);
            }

            private void CheckMetaString(FieldDef f, string s)
            {
                if (f.Name == "schema_version" && s != _header.SchemaVersion)
                    Report.Error("E071", Line, f.Key, "frame schema_version '" + s + "' differs from header '" + _header.SchemaVersion + "'");
                if (f.Name == "scenario_id" && s != _header.ScenarioId)
                    Report.Error("E070", Line, f.Key, "frame scenario_id '" + s + "' differs from header '" + _header.ScenarioId + "'");
            }

            private void TypeError(FieldDef f, string expected) => Report.Error("E011", Line, f.Key, "wrong JSON type (expected " + expected + ")");

            private static string Fmt(double d) => double.IsNaN(d) ? "-inf/+inf" : d.ToString(System.Globalization.CultureInfo.InvariantCulture);

            private bool Null(FieldDef f, int row) => double.IsNaN(_cols.Get(f.Id, row));
            private double V(FieldDef f, int row) => _cols.Get(f.Id, row);

            private void CrossChecks(int row)
            {
                // Time
                if (!Null(_t, row) && row > 0 && !Null(_t, row - 1))
                {
                    double step = V(_t, row) - V(_t, row - 1);
                    if (step <= 0) Report.Error("E020", Line, _t.Key, "t_s must be strictly increasing");
                    else if (double.IsNaN(_firstStep)) _firstStep = step;
                    else if (Math.Abs(step - _firstStep) > 1e-6)
                        Report.Warn("W101", Line, _t.Key, "non-uniform step " + step + " s (first step " + _firstStep + " s)");
                }
                // Observation
                if (!Null(_obsMissing, row))
                {
                    bool missing = V(_obsMissing, row) > 0.5;
                    if (missing != Null(_tObs, row))
                        Report.Error("E060", Line, _tObs.Key, missing ? "obs_missing is true but T_obs is not null" : "T_obs is null but obs_missing is false");
                }
                // Twin
                if (!Null(_twinValid, row))
                {
                    int tv = (int)V(_twinValid, row);
                    if (tv == _noData)
                    {
                        if (!Null(_tEst, row) || !Null(_tEstSd, row)) Report.Error("E043", Line, _tEst.Key, "Twin_Valid NO_DATA requires T_est and T_est_sd to be null");
                    }
                    else if (Null(_tEst, row) || Null(_tEstSd, row))
                        Report.Error("E044", Line, _tEst.Key, "T_est and T_est_sd are required unless Twin_Valid is NO_DATA");

                    if (tv != _valid)
                    {
                        int present = 0;
                        foreach (var f in _forecast) if (!Null(f, row)) present++;
                        if (present > 0) Report.Error("E040", Line, "twin.forecast", present + " forecast field(s) present while Twin_Valid is not VALID (must be null)");
                    }
                    else
                    {
                        int missing = 0;
                        foreach (var f in _forecast) if (Null(f, row)) missing++;
                        if (missing > 0) Report.Error("E041", Line, "twin.forecast", missing + " forecast field(s) null while Twin_Valid is VALID");
                        else
                        {
                            for (int h = 0; h < 3; h++)
                            {
                                double m = V(_bounds[h, 0], row), l80 = V(_bounds[h, 1], row), u80 = V(_bounds[h, 2], row),
                                    l95 = V(_bounds[h, 3], row), u95 = V(_bounds[h, 4], row);
                                if (!(l95 <= l80 && l80 <= u80 && u80 <= u95))
                                    Report.Error("E042", Line, "twin.+" + ReplayFields.Horizons[h], "interval bounds must satisfy L95 <= L80 <= U80 <= U95");
                                else if (m < l80 || m > u80)
                                    Report.Warn("W103", Line, "twin.T_pred_" + ReplayFields.Horizons[h], "forecast mean outside its 80% interval");
                            }
                        }
                    }
                }
                // Controller consistency (external log self-consistency only)
                if (!Null(_state, row))
                {
                    int st = (int)V(_state, row);
                    bool inShutdown = st == _shutdown;
                    if (!Null(_safety, row) && (V(_safety, row) > 0.5) != inShutdown)
                        Report.Error("E031", Line, _safety.Key, "Safety_Shutdown must be true exactly when Controller_State is SAFETY_SHUTDOWN");
                    if (inShutdown)
                    {
                        for (int i = 0; i < 4; i++)
                            if (!Null(_heat[i], row) && V(_heat[i], row) > 0)
                                Report.Error("E030", Line, _heat[i].Key, "heating command > 0 during SAFETY_SHUTDOWN");
                    }
                    if (!Null(_sub, row) && ((int)V(_sub, row) != _subNone) != (st == _degraded))
                        Report.Warn("W104", Line, _sub.Key, "Degraded_Substate inconsistent with Controller_State");
                }
                for (int i = 0; i < 4; i++)
                {
                    if (Null(_chFault[i], row)) continue;
                    int code = (int)V(_chFault[i], row);
                    if (code == 0) continue;
                    int lo = 100 * (i + 1) + 1, hi = 100 * (i + 1) + 99;
                    if (code < lo || code > hi)
                        Report.Error("E032", Line, _chFault[i].Key, "channel fault code " + code + " is outside channel " + (i + 1) + "'s range " + lo + "-" + hi);
                    if (!Null(_heat[i], row) && V(_heat[i], row) > 0)
                        Report.Error("E033", Line, _heat[i].Key, "faulted channel " + (i + 1) + " has a heating command > 0");
                }
                // Plant
                if (!Null(_plantMode, row))
                {
                    var mode = StringEnums.PlantModes[(int)V(_plantMode, row)];
                    if (mode == "OPEN_LOOP" && (!Null(_tPlant, row) || !Null(_dTHeat, row)))
                        Report.Error("E061", Line, _plantMode.Key, "OPEN_LOOP requires T_plant and dT_heat to be null (no warming effect exists in open loop)");
                    if (mode != "OPEN_LOOP" && (Null(_tPlant, row) || Null(_dTHeat, row)))
                        Report.Warn("W108", Line, _plantMode.Key, mode + " with T_plant or dT_heat null");
                    if (_prevPlantMode != null && _prevPlantMode != mode)
                        Report.Warn("W107", Line, _plantMode.Key, "plant_mode changed from " + _prevPlantMode + " to " + mode);
                    _prevPlantMode = mode;
                }
                // Source tags + holdout guard
                foreach (var f in ReplayFields.InGroup("src"))
                {
                    if (Null(f, row)) continue;
                    var tag = StringEnums.SourceTags[(int)V(f, row)];
                    if (f.Name == "obs" && tag == "REAL_DEV")
                    {
                        if (_header.Cohort != "DEVELOPMENT")
                            Report.Error("E051", Line, f.Key, "REAL_DEV observations require header.cohort DEVELOPMENT (found '" + _header.Cohort + "')");
                        if (_header.Placeholder)
                            Report.Error("E054", Line, f.Key, "a placeholder file must not contain REAL_DEV observations");
                    }
                    if (_prevTags.TryGetValue(f.Name, out var prev) && prev != tag)
                        Report.Warn("W106", Line, f.Key, "source tag changed from " + prev + " to " + tag);
                    _prevTags[f.Name] = tag;
                }
            }

            public ReplayParseResult Finish()
            {
                Result.LineCount = Line;
                if (Result.Cancelled) return Result;
                if (_header == null && !Report.Has("E001") && !Report.Has("E090") && !Report.Has("E091") && !Report.Has("E093"))
                    Report.Error("E001", 0, null, "empty file: no header line");
                if (_header != null && _cols.Count < 2)
                    Report.Error("E021", 0, null, "a replay needs at least 2 frames (found " + _cols.Count + ")");
                if (Report.IsValid && _header != null)
                    Result.Table = _cols.Build(Opt.TwinPeriodS);
                return Result;
            }
        }
    }

    /// <summary>Opens .jsonl or .jsonl.gz replay files as UTF-8 text, streaming (never the whole file in memory).</summary>
    public static class ReplayFileReader
    {
        public static TextReader OpenText(string path)
        {
            Stream s = File.OpenRead(path);
            if (path.EndsWith(".gz", StringComparison.OrdinalIgnoreCase))
                s = new System.IO.Compression.GZipStream(s, System.IO.Compression.CompressionMode.Decompress);
            return new StreamReader(s, System.Text.Encoding.UTF8, true, 1 << 16);
        }

        /// <summary>Reads and validates only the header line (used by the scenario catalog).</summary>
        public static ReplayHeader ReadHeader(string path, ValidationReport report)
        {
            using (var r = OpenText(path))
            {
                string line;
                int n = 0;
                while ((line = r.ReadLine()) != null)
                {
                    n++;
                    if (line.Trim().Length == 0) continue;
                    JToken tok;
                    try { tok = StrictJson.Parse(line); }
                    catch (JsonReaderException ex) { report.Error("E090", n, null, ex.Message); return null; }
                    return ReplayHeader.Parse(tok as JObject, n, report);
                }
                report.Error("E001", 0, null, "empty file");
                return null;
            }
        }
    }
}
