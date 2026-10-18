using System;
using System.Collections.Generic;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Left "Patient &amp; channel overview": only fields that exist in the replay schema, each with its source tag.
    ///  - Patient temperature signal T_obs (missing frames show "no observation", never the previous value).
    ///  - Twin estimate T_est ± T_est_sd and twin validity (as supplied by the replay; nothing recomputed here).
    ///  - Channel table CH1-CH4: replay-derived status, heat command (%), module temperatures A/B (°C). Heater current and
    ///    the full channel record are in the region panel (select the channel).
    ///  - Vital signs the schema does not contain (HR, SpO2, MAP) are listed as N/A with the reason (one compact row).
    /// Clicking a channel row selects that region in the 3D view.
    /// </summary>
    public sealed class OverviewPanel : IReplayView
    {
        private readonly Label _tobs, _tobsSub, _test, _testSub, _twinValid;
        private readonly SourceBadge _obsBadge, _twinBadge;
        private readonly VisualElement _rowsHost;
        private readonly List<(VisualElement row, Label status, Label heat, Label ta, Label tb)> _rows = new List<(VisualElement, Label, Label, Label, Label)>();
        private static readonly string[] ShortLimb = { "L hand", "R hand", "L foot", "R foot" };
        private ReplaySession _s;
        private readonly List<(Label value, Label tag, Func<int, string> get, string group)> _info = new List<(Label, Label, Func<int, string>, string)>();

        public event Action<int> ChannelClicked;

        public OverviewPanel(VisualElement root)
        {
            _tobs = UiUtil.Req<Label>(root, "ov-tobs");
            _tobsSub = UiUtil.Req<Label>(root, "ov-tobs-sub");
            _test = UiUtil.Req<Label>(root, "ov-test");
            _testSub = UiUtil.Req<Label>(root, "ov-test-sub");
            _twinValid = UiUtil.Req<Label>(root, "ov-twin-valid");
            _obsBadge = new SourceBadge("obs");
            _twinBadge = new SourceBadge("twin");
            UiUtil.Req<VisualElement>(root, "ov-obs-src").Add(_obsBadge.Root);
            UiUtil.Req<VisualElement>(root, "ov-twin-src").Add(_twinBadge.Root);
            var na = UiUtil.Req<VisualElement>(root, "ov-unavailable");
            {
                // One compact row: these vital signs do not exist in replay schema v1.0, so they are never shown as numbers.
                var row = UiUtil.Box("na-row");
                row.Add(UiUtil.Label("HR · SpO₂ · MAP", "na-name"));
                row.Add(UiUtil.Label("N/A", "na-value"));
                row.Add(UiUtil.Label("not in replay schema v1.0", "na-why"));
                row.tooltip = "Heart rate, SpO₂ and mean arterial pressure are not fields of replay schema v1.0. They are never invented.";
                na.Add(row);
            }
            BuildInfo(UiUtil.Req<VisualElement>(root, "ov-ctrl"), new (string, Func<int, string>, string)[]
            {
                ("Controller state", fr => _s.Enums.LabelOf(EnumNames.ControllerState, _s.Table.GetInt(_s.F.State, fr)), "ctrl"),
                ("Alert", fr => { var a = _s.Table.GetInt(_s.F.Alert, fr); return a == 0 ? "none" : _s.Enums.LabelOf(EnumNames.AlertCode, a); }, "ctrl"),
                ("Fault", fr => { var c = _s.Table.GetInt(_s.F.FaultCode, fr); return c == 0 ? (_s.Table.GetBool(_s.F.FaultLatched, fr) ? "latched" : "none") : c + " · " + _s.Faults.Describe(c); }, "ctrl"),
                ("Safety shutdown", fr => _s.Table.GetBool(_s.F.SafetyShutdown, fr) ? "ACTIVE" : "no", "ctrl"),
            });
            BuildInfo(UiUtil.Req<VisualElement>(root, "ov-quality"), new (string, Func<int, string>, string)[]
            {
                ("Observation now", fr => ObsMissing(fr) ? "MISSING" : "present", "obs"),
                ("Missing, last 10 min", fr => MissingShare(fr, 600), "obs"),
                ("P(outlier)", fr => Fmt.Probability(_s.Table.Get(_s.F.POutlier, fr)), "twin"),
                ("P(level shift)", fr => Fmt.Probability(_s.Table.Get(_s.F.PLevelShift, fr)), "twin"),
                ("Twin data stale", fr => _s.Table.GetBool(_s.F.DataStaleTwin, fr) ? "STALE" : "fresh", "ctrl"),
                ("Hardware data stale", fr => _s.Table.GetBool(_s.F.DataStaleHw, fr) ? "STALE" : "fresh", "ctrl"),
            });
            _rowsHost = UiUtil.Req<VisualElement>(root, "ov-channels");
            var head = UiUtil.Box("ch-row", "ch-row-head");
            foreach (var (t, cls) in new[] { ("CH", "ch-c-id"), ("Status", "ch-c-status"), ("Cmd %", "ch-c-num"), ("T_A °C", "ch-c-num"), ("T_B °C", "ch-c-num") })
                head.Add(UiUtil.Label(t, cls, "ch-head"));
            _rowsHost.Add(head);
            for (int i = 0; i < 4; i++)
            {
                int ch = i + 1;
                var row = UiUtil.Box("ch-row", "ch-row-data", ch <= 2 ? "ch-hand" : "ch-foot");
                var id = UiUtil.Label("CH" + ch + " " + ShortLimb[i], "ch-c-id");
                var st = UiUtil.Label("—", "ch-c-status");
                var heat = UiUtil.Label("—", "ch-c-num", "mono");
                var ta = UiUtil.Label("—", "ch-c-num", "mono");
                var tb = UiUtil.Label("—", "ch-c-num", "mono");
                row.Add(id); row.Add(st); row.Add(heat); row.Add(ta); row.Add(tb);
                row.RegisterCallback<ClickEvent>(_ => ChannelClicked?.Invoke(ch));
                row.tooltip = "CH" + ch + " " + ChannelRules.Limbs[i].ToLowerInvariant() + ": replayed heat command (%) and SIMULATED module temperatures A/B (°C). Click to select it in the 3D view.";
                _rowsHost.Add(row);
                _rows.Add((row, st, heat, ta, tb));
            }
        }

        private void BuildInfo(VisualElement host, (string name, Func<int, string> get, string group)[] rows)
        {
            foreach (var r in rows)
            {
                var row = UiUtil.Box("ov-row");
                row.Add(UiUtil.Label(r.name, "ov-row-k"));
                var v = UiUtil.Label("—", "ov-row-v");
                row.Add(v);
                var tag = UiUtil.Label("", "dp-tag");
                row.Add(tag);
                host.Add(row);
                _info.Add((v, tag, r.get, r.group));
            }
        }

        private bool ObsMissing(int fr) => double.IsNaN(_s.Table.Get(_s.F.TObs, fr)) || _s.Table.GetBool(_s.F.ObsMissing, fr);

        /// <summary>Share of frames without an observation in the window ending at this frame (display arithmetic only).</summary>
        private string MissingShare(int fr, double windowS)
        {
            var t = _s.Table;
            int n = 0, miss = 0;
            for (int k = fr; k >= 0 && t.T[fr] - t.T[k] <= windowS; k--) { n++; if (ObsMissing(k)) miss++; }
            return n == 0 ? Fmt.Missing : (100.0 * miss / n).ToString("0", System.Globalization.CultureInfo.InvariantCulture) + " %";
        }

        public void SetSelectedChannel(int ch)
        {
            for (int i = 0; i < _rows.Count; i++) _rows[i].row.EnableInClassList("selected", i + 1 == ch);
        }

        public void Bind(ReplaySession s) => _s = s;

        public void Unbind()
        {
            _s = null;
            _tobs.text = "—";
            _tobsSub.text = "no replay loaded";
            _test.text = "—";
            _testSub.text = "";
            _twinValid.text = "";
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var t = _s.Table;
            var f = _s.F;
            double obs = t.Get(f.TObs, frame);
            bool missing = double.IsNaN(obs) || t.GetBool(f.ObsMissing, frame);
            UiUtil.SetText(_tobs, missing ? "—" : Fmt.Value(obs, f.TObs));
            UiUtil.SetText(_tobsSub, missing ? "no observation at this frame (not carried forward)" : "patient temperature signal · site not established");
            _tobs.EnableInClassList("value-missing", missing);
            double est = t.Get(f.TEst, frame), sd = t.Get(f.TEstSd, frame);
            UiUtil.SetText(_test, double.IsNaN(est) ? "—" : Fmt.Value(est, f.TEst));
            UiUtil.SetText(_testSub, double.IsNaN(est) ? "estimate unavailable at this frame" : double.IsNaN(sd) ? "± SD not supplied" : "± " + Fmt.Value(sd, f.TEstSd) + " (1 SD, as supplied)");
            _test.EnableInClassList("value-missing", double.IsNaN(est));
            var tv = _s.Enums.LabelOf(EnumNames.TwinValid, t.GetInt(f.TwinValid, frame));
            UiUtil.SetText(_twinValid, "Twin validity: " + tv);
            var ot = _s.Tag("obs", frame);
            _obsBadge.Set(ot, ProvenanceRules.Meaning("obs", ot, _s, frame));
            var tt = _s.Tag("twin", frame);
            _twinBadge.Set(tt, ProvenanceRules.Meaning("twin", tt, _s, frame));
            foreach (var (value, tag, get, group) in _info)
            {
                string txt;
                try { txt = get(frame); } catch (Exception ex) { txt = "error: " + ex.Message; }
                UiUtil.SetText(value, txt);
                value.EnableInClassList("value-alert", txt == "MISSING" || txt == "STALE" || txt == "ACTIVE");
                var tg = _s.Tag(group, frame) ?? "";
                UiUtil.SetText(tag, tg);
                if (tag.userData is string prev && prev != "tag-" + tg) tag.RemoveFromClassList(prev);
                tag.AddToClassList("tag-" + tg);
                tag.userData = "tag-" + tg;
            }
            for (int i = 0; i < 4; i++)
            {
                var cv = ChannelRules.Compute(_s, frame, i + 1);
                var r = _rows[i];
                UiUtil.SetText(r.status, ShortStatus(cv));
                var cls = "ch-st-" + cv.Status;
                if (r.status.userData is string prev && prev != cls) r.status.RemoveFromClassList(prev);
                r.status.AddToClassList(cls);
                r.status.userData = cls;
                UiUtil.SetText(r.heat, Fmt.Number(cv.Heat, 0));
                UiUtil.SetText(r.ta, Fmt.Number(cv.TempA, 1));
                UiUtil.SetText(r.tb, Fmt.Number(cv.TempB, 1));
            }
        }

        /// <summary>Status word for the narrow table (the full text, incl. fault description, is in the region panel).</summary>
        private static string ShortStatus(ChannelView v)
        {
            switch (v.Status)
            {
                case ChannelStatus.Heating: return "HEATING";
                case ChannelStatus.Off: return "OFF";
                case ChannelStatus.Shutdown: return "SHUTDOWN";
                case ChannelStatus.Cutoff: return "HW CUTOFF";
                case ChannelStatus.Disconnected: return "DISCONN.";
                case ChannelStatus.Fault: return "FAULT " + v.FaultCode.ToString(System.Globalization.CultureInfo.InvariantCulture);
                default: return v.StatusText;
            }
        }
    }
}
