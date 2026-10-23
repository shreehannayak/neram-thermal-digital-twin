using System.Collections.Generic;
using System.Linq;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Engineering diagnostics: replay metadata (header, input hashes, generator), validation report, configuration
    /// origins and warnings, provenance at the current frame, schema facts and load performance.
    /// </summary>
    public sealed class DiagnosticsPanel : IReplayView
    {
        private readonly VisualElement _drawer;
        private readonly ScrollView _body;
        private readonly ReplayLoader _loader;
        private ReplaySession _s;
        private int _frame;
        private bool _details;
        private Button _detailsButton;

        /// <summary>CAD/placeholder binding report from NeramAssemblyBinder (set by NeramApp).</summary>
        public IReadOnlyList<string> AssemblyReport;
        /// <summary>Runtime performance line supplied by NeramApp (frame time, UI refresh rate).</summary>
        public System.Func<string> PerformanceText;

        public DiagnosticsPanel(VisualElement root, ReplayLoader loader)
        {
            _loader = loader;
            _drawer = UiUtil.Req<VisualElement>(root, "drawer-diagnostics");
            var head = UiUtil.Box("drawer-head");
            head.Add(UiUtil.Label("Diagnostics", "drawer-title"));
            _detailsButton = UiUtil.Button("Technical details", () => { _details = !_details; _detailsButton.text = _details ? "Overview" : "Technical details"; Render(); }, "btn-ghost");
            head.Add(_detailsButton);
            head.Add(UiUtil.Button("Refresh", Render, "btn-ghost"));
            head.Add(UiUtil.Button("Close", () => UiUtil.Show(_drawer, false), "btn-ghost"));
            _drawer.Add(head);
            _body = new ScrollView();
            _body.style.flexGrow = 1;
            _drawer.Add(_body);
        }

        public bool IsOpen => UiUtil.IsShown(_drawer);
        public void Close() => UiUtil.Show(_drawer, false);

        public void Toggle()
        {
            UiUtil.Show(_drawer, !IsOpen);
            if (IsOpen) Render();
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            _frame = 0;
            if (IsOpen) Render();
        }

        public void ShowFrame(int frame) => _frame = frame;

        private VisualElement Section(string title)
        {
            var c = UiUtil.Box("card");
            c.Add(UiUtil.Label(title, "card-title"));
            _body.Add(c);
            return c;
        }

        private void Render()
        {
            _body.Clear();
            if (_details) RenderTechnical(); else RenderOverview();
        }

        // ------------------------------------------------------------------ overview (default)

        private static VisualElement Tile(string label, string big, string sub, string cls)
        {
            var t = UiUtil.Box("dg-tile", cls);
            t.Add(UiUtil.Label(label, "dg-tile-label"));
            t.Add(UiUtil.Label(big, "dg-tile-big"));
            if (!string.IsNullOrEmpty(sub)) t.Add(UiUtil.Label(sub, "dg-tile-sub"));
            return t;
        }

        private void RenderOverview()
        {
            if (_s == null) { _body.Add(UiUtil.Label("No replay loaded. Open MENU → Scenarios and load one.", "kp-intro")); return; }
            var h = _s.Header;
            var t = _s.Table;
            int errors = _s.Report.Issues.Count(i => i.Severity == IssueSeverity.Error);
            int warnings = _s.Report.Issues.Count(i => i.Severity == IssueSeverity.Warning);

            _body.Add(UiUtil.Label(h.Title ?? h.ScenarioId, "dg-title"));
            _body.Add(UiUtil.Label(h.ScenarioId + "  ·  " + (h.Cohort ?? "?") + " data", "dg-sub"));

            var tiles = UiUtil.Box("dg-tiles");
            tiles.Add(Tile("REPLAY FILE", _s.Report.IsValid ? "✓ Valid" : "✗ Invalid",
                errors + " errors · " + warnings + " warnings", _s.Report.IsValid ? (warnings == 0 ? "dg-ok" : "dg-warn") : "dg-bad"));
            tiles.Add(Tile("LENGTH", Fmt.Time(t.Duration).Substring(2), t.FrameCount.ToString("N0") + " one-second frames", "dg-neutral"));
            tiles.Add(Tile("TWIN UPDATES", t.MinuteStartFrames.Length.ToString(), "one every " + t.TwinPeriodS.ToString("0") + " s", "dg-neutral"));
            _body.Add(tiles);

            var src = UiUtil.Box("dg-card");
            src.Add(UiUtil.Label("Where each part of the picture comes from", "dg-card-title"));
            foreach (var e in ProvenanceRules.Compute(_s, _frame))
            {
                var row = UiUtil.Box("dg-src-row");
                row.Add(UiUtil.Label(e.Group, "dg-src-group"));
                row.Add(UiUtil.Chip(e.Tag, "tag-" + e.Tag));
                row.Add(UiUtil.Label(e.Meaning, "dg-src-meaning"));
                src.Add(row);
            }
            src.Add(UiUtil.Label("REAL_DEV = development-set measurement · MODEL = NERAM twin output · SIMULATED = generated or test-bench · ASSUMED = illustrative, no data", "dg-legend"));
            _body.Add(src);

            var todo = UiUtil.Box("dg-card");
            todo.Add(UiUtil.Label("Still placeholders — and who replaces them", "dg-card-title"));
            int n = 0;
            if (h.Placeholder) { todo.Add(Todo("This replay is a scripted stand-in, not NERAM twin / controller output", "Suchitha: controller logs with real heating → Sai rebuilds the replay")); n++; }
            if (_s.Faults != null && _s.Faults.IsPlaceholder) { todo.Add(Todo("Fault explanations use built-in placeholder text", "Shreehan: hardware/interfaces/fault_codes.csv")); n++; }
            int phParts = AssemblyReport?.Count(r => r.Contains("PLACEHOLDER")) ?? 0;
            if (phParts > 0) { todo.Add(Todo(phParts + " 3D parts are placeholder shapes", "Neharikaa: FBX exports of the modules and bedside controller")); n++; }
            int phParams = _s.Params.Entries.Values.Count(e => e.IsPlaceholderInUse);
            int noneParams = _s.Params.Entries.Values.Count(e => !e.HasValue && !e.IsPlaceholderInUse);
            if (phParams + noneParams > 0) { todo.Add(Todo(phParams + " parameter values are placeholders, " + noneParams + " not set yet", "Sai (development fit), a clinician, Suchitha, Shreehan — see MENU → Parameters")); n++; }
            if (n == 0) todo.Add(UiUtil.Label("Nothing in this replay is a placeholder.", "dg-done"));
            _body.Add(todo);

            var notable = _s.Report.Issues.Where(i => i.Severity != IssueSeverity.Info).Take(20).ToList();
            var chk = UiUtil.Box("dg-card");
            chk.Add(UiUtil.Label("File checks", "dg-card-title"));
            if (notable.Count == 0) chk.Add(UiUtil.Label("✓ Every frame passed the same validation rules as the Python validator. No problems found.", "dg-done"));
            else foreach (var i in notable) chk.Add(UiUtil.Label((i.Severity == IssueSeverity.Error ? "✗ " : "⚠ ") + i, "dg-issue"));
            _body.Add(chk);
            _body.Add(UiUtil.Label("Engineering detail (file paths, hashes, schema, performance): Technical details ↑", "dg-legend"));
        }

        private static VisualElement Todo(string what, string who)
        {
            var r = UiUtil.Box("dg-todo");
            r.Add(UiUtil.Label("○  " + what, "dg-todo-what"));
            r.Add(UiUtil.Label(who, "dg-todo-who"));
            return r;
        }

        // ------------------------------------------------------------------ technical details (previous full view)

        private void RenderTechnical()
        {
            var cfg = Section("Configuration");
            cfg.Add(UiUtil.KeyValue("enums", _loader.Enums?.Origin ?? "-"));
            cfg.Add(UiUtil.KeyValue("display", _loader.Display?.Origin ?? "-"));
            cfg.Add(UiUtil.KeyValue("fault codes", (_loader.Faults?.Origin ?? "-") + (_loader.Faults != null && _loader.Faults.IsPlaceholder ? "  [PLACEHOLDER]" : "")));
            cfg.Add(UiUtil.KeyValue("config folder", _loader.ConfigDir));
            cfg.Add(UiUtil.KeyValue("replay folder", _loader.ReplayDir));
            foreach (var w in _loader.ConfigWarnings) cfg.Add(UiUtil.Label("⚠ " + w, "card-text"));
            if (AssemblyReport != null)
            {
                var asm = Section("3D assembly (CAD vs PLACEHOLDER)");
                foreach (var r in AssemblyReport) asm.Add(UiUtil.Label(r, "card-text"));
                asm.Add(UiUtil.Label("Replace a placeholder by importing Neharikaa's FBX under NERAM_Assembly with the role name (see docs/unity/CAD_INTEGRATION.md).", "card-text"));
            }
            if (PerformanceText != null)
            {
                var perf = Section("Performance");
                perf.Add(UiUtil.Label(PerformanceText(), "card-text"));
            }
            if (_s == null) { _body.Add(UiUtil.Label("No replay loaded.", "card-text")); return; }

            var h = _s.Header;
            var meta = Section("Replay metadata");
            meta.Add(UiUtil.KeyValue("scenario_id", h.ScenarioId));
            meta.Add(UiUtil.KeyValue("title", h.Title));
            meta.Add(UiUtil.KeyValue("file", _s.SourcePath));
            meta.Add(UiUtil.KeyValue("cohort", h.Cohort + (h.Placeholder ? "  ·  PLACEHOLDER" : "")));
            meta.Add(UiUtil.KeyValue("schema / spec / params", h.SchemaVersion + " / " + h.SpecVersion + " / " + h.ParamsVersion));
            meta.Add(UiUtil.KeyValue("created_utc", h.CreatedUtc));
            meta.Add(UiUtil.KeyValue("generator", h.Generator ?? "-"));
            foreach (var kv in h.Inputs) meta.Add(UiUtil.KeyValue("input " + kv.Key, kv.Value));
            meta.Add(UiUtil.KeyValue("disclaimer", h.Disclaimer));
            if (h.StaticContext != null)
                foreach (var p in h.StaticContext.Properties()) meta.Add(UiUtil.KeyValue("static " + p.Name, p.Value.ToString()));
            else meta.Add(UiUtil.KeyValue("static_context", "none in this replay"));

            var t = _s.Table;
            var rep = Section("Validation report (" + (_s.Report.IsValid ? "VALID" : "INVALID") + ")");
            rep.Add(UiUtil.KeyValue("frames / duration", t.FrameCount + " / " + Fmt.Time(t.Duration).Substring(2)));
            rep.Add(UiUtil.KeyValue("twin updates", t.MinuteStartFrames.Length + " (ts_twin_s " + t.TwinPeriodS + " s)"));
            rep.Add(UiUtil.KeyValue("summary", _s.Report.Summary()));
            foreach (var i in _s.Report.Issues.Take(60)) rep.Add(UiUtil.Label(i.Severity + "  " + i, "card-text"));
            rep.Add(UiUtil.KeyValue("load time", _loader.LastLoadSeconds.ToString("0.00") + " s (parse + validate, worker thread)"));
            rep.Add(UiUtil.KeyValue("column memory", (ReplayFields.Count * t.FrameCount * 8 / 1024) + " KiB"));
            rep.Add(UiUtil.KeyValue("rules", "unity/schema/VALIDATION_RULES.md (identical in integration/validate_replay.py)"));

            var prov = Section("Provenance at " + Fmt.Time(t.T[_frame]));
            foreach (var e in ProvenanceRules.Compute(_s, _frame)) prov.Add(UiUtil.KeyValue(e.Group + "  [" + e.Tag + "]", e.Meaning));
            prov.Add(UiUtil.KeyValue("clinician presses", _s.Events.ClinicianPressesInferred ? "inferred from Trigger_Reason / Alert (optional Clinician_* fields absent)" : "explicit Clinician_* fields"));

            var sch = Section("Schema");
            sch.Add(UiUtil.KeyValue("fields", ReplayFields.Count + " (" + ReplayFields.All.Count(f => f.Proposed) + " proposed, " + ReplayFields.All.Count(f => f.Optional) + " optional)"));
            sch.Add(UiUtil.KeyValue("supported versions", string.Join(", ", ReplayFields.SupportedSchemaVersions)));
            sch.Add(UiUtil.KeyValue("allowed cohorts", string.Join(", ", ReplayFields.AllowedCohorts)));
            sch.Add(UiUtil.KeyValue("events indexed", _s.Events.All.Count.ToString()));
            sch.Add(UiUtil.KeyValue("architecture", "Unity replays data only: no twin, no controller, no physiology in C#. Controller transitions come from the external Simulink/Stateflow log."));
        }

        public void Unbind()
        {
            _s = null;
            if (IsOpen) Render();
        }
    }
}
