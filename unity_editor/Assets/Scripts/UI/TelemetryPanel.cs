using System.Collections.Generic;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Live engineering telemetry. Every value comes straight from the replay row of the current frame (units from the
    /// field registry); missing values show an em dash. Trend arrows compare with the value one twin period (60 s)
    /// earlier and are display aids only. Groups carry their source badge. Collapsible.
    /// </summary>
    public sealed class TelemetryPanel : IReplayView
    {
        private sealed class Row
        {
            public FieldDef Field;
            public Label Value, Trend;
            public bool ShowTrend;
        }

        private sealed class Group
        {
            public string Key;
            public VisualElement Root;
            public SourceBadge Badge;
        }

        private readonly ScrollView _scroll;
        private readonly Label _time;
        private readonly List<Row> _rows = new List<Row>();
        private readonly List<Group> _groups = new List<Group>();
        private readonly Label[,] _ch = new Label[4, 8];
        private ReplaySession _s;
        private bool _collapsed;

        private static readonly string[] ChannelColumns = { "Heat %", "T A °C", "T B °C", "I A", "Conn", "Cutoff", "Fault", "Status" };

        public TelemetryPanel(VisualElement root)
        {
            _scroll = UiUtil.Req<ScrollView>(root, "telemetry-scroll");
            _time = UiUtil.Req<Label>(root, "telemetry-time");
            var collapse = UiUtil.Req<Button>(root, "telemetry-collapse");
            collapse.clicked += () =>
            {
                _collapsed = !_collapsed;
                UiUtil.Show(_scroll, !_collapsed);
                collapse.text = _collapsed ? "+" : "−";
            };
            Build();
        }

        private void Build()
        {
            _scroll.Clear();
            _rows.Clear();
            _groups.Clear();
            AddGroup("obs", "OBSERVATION", new[] { "obs.T_obs", "obs.obs_missing" }, new[] { "obs.T_obs" });
            AddGroup("twin", "TWIN", new[] { "twin.T_est", "twin.T_est_sd", "twin.Twin_Valid", "twin.P_outlier", "twin.P_level_shift",
                "twin.P_below_hypo_20", "twin.P_below_hypo_30", "twin.P_below_hypo_60" }, new[] { "twin.T_est" });
            AddGroup("ctrl", "CONTROLLER", new[] { "ctrl.Controller_State", "ctrl.Degraded_Substate", "ctrl.Trigger_Reason", "ctrl.Alert",
                "ctrl.Demand_Global", "ctrl.Safety_Shutdown", "ctrl.Fault_Latched", "ctrl.fault_code", "ctrl.Clinician_Mode",
                "ctrl.Data_Stale_Twin", "ctrl.Data_Stale_HW" }, new string[0]);
            BuildChannelTable();
            AddGroup("plant", "PLANT (SIMULATED / ASSUMED)", new[] { "plant.T_plant", "plant.dT_heat", "plant.plant_mode" }, new[] { "plant.T_plant" });
        }

        private void AddGroup(string key, string title, string[] fields, string[] trendFields)
        {
            var g = new Group { Key = key, Root = UiUtil.Box("tele-group") };
            var head = UiUtil.Box("tele-group-head");
            head.Add(UiUtil.Label(title, "tele-group-title"));
            head.Add(UiUtil.Box("spacer"));
            g.Badge = new SourceBadge(key);
            head.Add(g.Badge.Root);
            g.Root.Add(head);
            foreach (var key2 in fields)
            {
                var parts = key2.Split('.');
                var f = ReplayFields.Get(parts[0], parts[1]);
                var r = new Row { Field = f, ShowTrend = System.Array.IndexOf(trendFields, key2) >= 0 };
                var row = UiUtil.Box("tele-row");
                var name = UiUtil.Label(f.Name, "tele-name");
                name.tooltip = f.Label + (f.Proposed ? " (proposed field)" : "") + (f.Optional ? " (optional)" : "");
                row.Add(name);
                r.Value = UiUtil.Label("—", "tele-value");
                r.Trend = UiUtil.Label("", "tele-trend");
                row.Add(r.Value);
                row.Add(r.Trend);
                g.Root.Add(row);
                _rows.Add(r);
            }
            _groups.Add(g);
            _scroll.Add(g.Root);
        }

        private void BuildChannelTable()
        {
            var g = new Group { Key = "hw", Root = UiUtil.Box("tele-group") };
            var head = UiUtil.Box("tele-group-head");
            head.Add(UiUtil.Label("CHANNELS (HARDWARE SIGNALS)", "tele-group-title"));
            head.Add(UiUtil.Box("spacer"));
            g.Badge = new SourceBadge("hw");
            head.Add(g.Badge.Root);
            g.Root.Add(head);
            var colHead = UiUtil.Box("ch-table-head");
            colHead.Add(UiUtil.Label("", "ch-label"));
            for (int c = 0; c < 4; c++) colHead.Add(UiUtil.Label("CH" + (c + 1), "ch-cell", "ch-head"));
            g.Root.Add(colHead);
            for (int k = 0; k < ChannelColumns.Length; k++)
            {
                var row = UiUtil.Box("tele-row");
                row.Add(UiUtil.Label(ChannelColumns[k], "ch-label"));
                for (int c = 0; c < 4; c++)
                {
                    _ch[c, k] = UiUtil.Label("—", "ch-cell");
                    row.Add(_ch[c, k]);
                }
                g.Root.Add(row);
            }
            var limbs = UiUtil.Label("CH1 left hand · CH2 right hand · CH3 left foot · CH4 right foot", "t-xs", "c-3");
            g.Root.Add(limbs);
            _groups.Add(g);
            _scroll.Add(g.Root);
        }

        public void Bind(ReplaySession s) => _s = s;

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var t = _s.Table;
            UiUtil.SetText(_time, Fmt.Time(t.T[frame]));
            int prevFrame = t.FrameAtTime(t.T[frame] - t.TwinPeriodS);
            foreach (var r in _rows)
            {
                double v = t.Get(r.Field, frame);
                UiUtil.SetText(r.Value, Describe(r.Field, v, frame));
                r.Value.EnableInClassList("tele-missing", double.IsNaN(v));
                if (r.ShowTrend)
                {
                    double pv = t.Get(r.Field, prevFrame);
                    UiUtil.SetText(r.Trend, frame == prevFrame ? "" : Fmt.Trend(v - pv, 2, _s.Display.TrendDeadband) + "/min");
                }
            }
            for (int c = 0; c < 4; c++)
            {
                var cv = ChannelRules.Compute(_s, frame, c + 1);
                UiUtil.SetText(_ch[c, 0], Fmt.Number(cv.Heat, 0));
                UiUtil.SetText(_ch[c, 1], Fmt.Number(cv.TempA, 2));
                UiUtil.SetText(_ch[c, 2], Fmt.Number(cv.TempB, 2));
                UiUtil.SetText(_ch[c, 3], Fmt.Number(cv.Current, 2));
                UiUtil.SetText(_ch[c, 4], cv.Connected ? "yes" : "NO");
                UiUtil.SetText(_ch[c, 5], cv.Cutoff ? "TRIP" : "-");
                UiUtil.SetText(_ch[c, 6], cv.FaultCode > 0 ? cv.FaultCode.ToString() : "0");
                UiUtil.SetText(_ch[c, 7], cv.Status.ToString().ToUpperInvariant());
                _ch[c, 6].tooltip = cv.FaultText ?? "";
            }
            foreach (var g in _groups) g.Badge.Set(_s, g.Key, frame);
        }

        private string Describe(FieldDef f, double v, int frame)
        {
            if (double.IsNaN(v)) return Fmt.Missing;
            switch (f.Kind)
            {
                case FieldKind.Enum:
                    return _s.Enums.NameOf(f.EnumName, (int)v);
                case FieldKind.StringEnum:
                    return _s.Table.GetString(f, frame);
                case FieldKind.Int:
                    return f.Name == "fault_code" && v > 0 ? ((int)v) + " " + _s.Faults.NameOf((int)v) : ((int)v).ToString();
                default:
                    return Fmt.Value(v, f);
            }
        }

        public void Unbind()
        {
            _s = null;
            foreach (var r in _rows) { UiUtil.SetText(r.Value, Fmt.Missing); UiUtil.SetText(r.Trend, ""); }
        }
    }
}
