using System;
using System.Collections.Generic;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Right-hand detail panel for the selected 3D region (e.g. "LEFT FOOT — CH3"). Values are grouped by what they ARE:
    ///   PATIENT-LEVEL SIGNAL           one replay-wide signal; not measured at the selected limb
    ///   CHANNEL COMMAND                controller output for this channel (source tag of the ctrl group)
    ///   HARDWARE TELEMETRY             module sensors / heater current / connection / cutoff (hw group tag)
    ///   ASSUMED PROTOTYPE RESPONSE     plant-group values: SIMULATED / ASSUMED, never measurements
    /// A null value in the replay is shown as "unavailable (null in replay)"; nothing is carried forward or invented.
    /// Regions with no field in the replay (arms, legs, torso, wearable) say so explicitly.
    /// </summary>
    public sealed class RegionDetailPanel : IReplayView
    {
        private sealed class Row
        {
            public Label Value;
            public Label Tag;
            public Func<int, string> Get;
            public Func<int, string> TagOf;
        }

        private readonly Label _title, _sub;
        private readonly ScrollView _body;
        private readonly VisualElement _actions;
        private readonly List<Row> _rows = new List<Row>();
        private ReplaySession _s;
        private int _frame;

        public RegionId Region { get; private set; } = RegionId.None;
        public event Action FocusRequested;
        public event Action ExplodeRequested;
        public event Action InspectorRequested;
        public event Action<RegionId> RegionRequested;
        public event Action<WearableScreen.Mode> WearableModeRequested;
        public WearableScreen.Mode WearableMode = WearableScreen.Mode.MirrorReplay;

        public RegionDetailPanel(VisualElement root)
        {
            _title = UiUtil.Req<Label>(root, "dp-title");
            _sub = UiUtil.Req<Label>(root, "dp-sub");
            _body = UiUtil.Req<ScrollView>(root, "dp-body");
            _actions = UiUtil.Req<VisualElement>(root, "dp-actions");
            Select(RegionId.None);
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            Select(Region);
        }

        public void Unbind()
        {
            _s = null;
            Select(Region);
        }

        public void Select(RegionId region)
        {
            Region = region;
            _rows.Clear();
            _body.Clear();
            _actions.Clear();
            if (region == RegionId.None)
            {
                _title.text = "SELECT A REGION";
                _sub.text = "Click a hand, foot, arm, leg, the torso, the wrist wearable or the bedside controller in the 3D view, or a channel row on the left.";
                Note("Hover highlights a region; click selects it. Drag to orbit, right-drag to pan, wheel to zoom.");
                return;
            }
            _title.text = NeramRegion.Title(region);
            int ch = NeramRegion.ChannelOf(region);
            if (_s == null)
            {
                _sub.text = "No replay loaded.";
                return;
            }
            switch (region)
            {
                case RegionId.HandLeft:
                case RegionId.HandRight:
                case RegionId.FootLeft:
                case RegionId.FootRight:
                    BuildChannel(ch);
                    break;
                case RegionId.ArmLeft:
                case RegionId.ArmRight:
                case RegionId.LegLeft:
                case RegionId.LegRight:
                    BuildLimb(region);
                    break;
                case RegionId.Torso:
                    BuildTorso();
                    break;
                case RegionId.Wearable:
                    BuildWearable();
                    break;
                case RegionId.Controller:
                    BuildController();
                    break;
            }
            ShowFrame(_frame);
        }

        // ------------------------------------------------------------------ section builders

        private void BuildChannel(int ch)
        {
            int i = ch - 1;
            var f = _s.F;
            _sub.text = (ch <= 2 ? "Hand warming mitt" : "Foot warming boot with layered heated sole") + " · prototype concept geometry (not CAD)";
            Section("PATIENT-LEVEL SIGNAL", "shared by all regions · not measured at this " + (ch <= 2 ? "hand" : "foot"));
            PatientSignalRows();
            Section("CHANNEL COMMAND — CH" + ch, "controller output from the replay");
            Add("Heat command", fr => Fmt.Value(_s.Table.Get(f.Heat[i], fr), f.Heat[i]), "ctrl");
            Add("Channel status", fr => ChannelRules.Compute(_s, fr, ch).StatusText, "ctrl");
            Add("Channel fault", fr =>
            {
                var code = _s.Table.GetInt(f.ChannelFault[i], fr);
                return code > 0 ? code + " · " + _s.Faults.Describe(code) : "none (0)";
            }, "ctrl");
            Add("Global demand", fr => Fmt.Value(_s.Table.Get(f.Demand, fr), f.Demand), "ctrl");
            Add("Controller state", fr => _s.Enums.LabelOf(EnumNames.ControllerState, _s.Table.GetInt(f.State, fr)), "ctrl");
            Section("HARDWARE TELEMETRY — CH" + ch, "module sensors and heater electrical state");
            Add("Module temp sensor A", fr => Val(f.TempA[i], fr), "hw");
            Add("Module temp sensor B", fr => Val(f.TempB[i], fr), "hw");
            Add("Heater current", fr => Val(f.Current[i], fr), "hw");
            Add("Module connected", fr => _s.Table.GetBool(f.Connected[i], fr) ? "yes" : "NO — disconnected", "hw");
            Add("Hardware cutoff", fr => _s.Table.GetBool(f.Cutoff[i], fr) ? "TRIPPED" : "not tripped", "hw");
            Section("ASSUMED PROTOTYPE RESPONSE", "plant group · whole-patient values, not per channel, not measured");
            Add("Assumed warming contribution dT_heat", fr => Val(f.DTHeat, fr), "plant");
            Add("Simulated patient signal T_plant", fr => Val(f.TPlant, fr), "plant");
            Add("Plant mode", fr => _s.Table.GetString(f.PlantMode, fr) ?? Fmt.Missing, "plant");
            Note("VitalDB does not provide warming-system response data. Any warming response shown here is a SIMULATED or ASSUMED prototype response.");
            AddAction("Focus camera", () => FocusRequested?.Invoke());
            AddAction("Exploded layers", () => ExplodeRequested?.Invoke());
            AddAction("Hardware inspector", () => InspectorRequested?.Invoke());
        }

        private void BuildLimb(RegionId region)
        {
            bool arm = region == RegionId.ArmLeft || region == RegionId.ArmRight;
            bool left = region == RegionId.ArmLeft || region == RegionId.LegLeft;
            var linked = arm ? (left ? RegionId.HandLeft : RegionId.HandRight) : (left ? RegionId.FootLeft : RegionId.FootRight);
            int ch = NeramRegion.ChannelOf(linked);
            _sub.text = "No sensor or warming channel is modelled on the " + (arm ? "arm" : "leg") + ". The nearest channel is CH" + ch + ".";
            Section("PATIENT-LEVEL SIGNAL", "shared by all regions · no " + (arm ? "arm" : "leg") + "-specific measurement exists in the replay");
            PatientSignalRows();
            Section("NEAREST CHANNEL — CH" + ch, NeramRegion.Title(linked));
            var f = _s.F;
            Add("Heat command", fr => Fmt.Value(_s.Table.Get(f.Heat[ch - 1], fr), f.Heat[ch - 1]), "ctrl");
            Add("Channel status", fr => ChannelRules.Compute(_s, fr, ch).StatusText, "ctrl");
            AddAction("Select CH" + ch, () => RegionRequested?.Invoke(linked));
            AddAction("Focus camera", () => FocusRequested?.Invoke());
        }

        private void BuildTorso()
        {
            var f = _s.F;
            _sub.text = "No sensor or actuator is modelled on the chest/torso in this prototype.";
            Section("PATIENT-LEVEL SIGNAL", "the anatomical measurement site of this signal has not been established");
            PatientSignalRows();
            Section("FORECAST (as supplied by the replay)", "twin group");
            for (int h = 0; h < 3; h++)
            {
                int hh = h;
                string lbl = h == 0 ? "+20 min" : h == 1 ? "+30 min" : "+60 min";
                Add("Forecast mean " + lbl, fr => Val(f.PredMean[hh], fr), "twin");
                Add("80 % interval " + lbl, fr =>
                {
                    double lo = _s.Table.Get(f.L80[hh], fr), hi = _s.Table.Get(f.U80[hh], fr);
                    return double.IsNaN(lo) || double.IsNaN(hi) ? "unavailable (null in replay)" : Fmt.Number(lo, 2) + " – " + Fmt.Number(hi, 2) + " °C";
                }, "twin");
            }
            Section("CONTROLLER (whole patient)", "replay ctrl group");
            Add("Controller state", fr => _s.Enums.LabelOf(EnumNames.ControllerState, _s.Table.GetInt(f.State, fr)), "ctrl");
            Add("Global demand", fr => Fmt.Value(_s.Table.Get(f.Demand, fr), f.Demand), "ctrl");
            Add("Trigger reason", fr => _s.Enums.LabelOf(EnumNames.TriggerReason, _s.Table.GetInt(f.Reason, fr)), "ctrl");
            AddAction("Focus camera", () => FocusRequested?.Invoke());
        }

        private void BuildWearable()
        {
            var f = _s.F;
            _sub.text = "Concept wrist wearable. Replay schema v1.0 has NO wearable channel: this device produces no data in the replay.";
            Section("SCREEN CONTENT", "what the watch face overlay shows");
            Add("Screen mode", _ => WearableMode == WearableScreen.Mode.MirrorReplay ? "mirror of replay values (labelled with source tags)" : "SYNTHETIC DEMO pattern (deterministic, labelled, not data)", null);
            AddAction("Mirror replay values", () => { WearableMode = WearableScreen.Mode.MirrorReplay; WearableModeRequested?.Invoke(WearableMode); Select(Region); });
            AddAction("Synthetic demo (labelled)", () => { WearableMode = WearableScreen.Mode.SyntheticDemo; WearableModeRequested?.Invoke(WearableMode); Select(Region); });
            Section("PATIENT-LEVEL SIGNAL", "mirrored on the watch face in replay mode");
            PatientSignalRows();
            Add("Controller state", fr => _s.Enums.LabelOf(EnumNames.ControllerState, _s.Table.GetInt(f.State, fr)), "ctrl");
            AddAction("Focus camera", () => FocusRequested?.Invoke());
        }

        private void BuildController()
        {
            var f = _s.F;
            _sub.text = "Bedside controller (prototype concept geometry). Values below are the replayed controller outputs.";
            Section("CONTROLLER STATE", "replay ctrl group");
            Add("State", fr => _s.Enums.LabelOf(EnumNames.ControllerState, _s.Table.GetInt(f.State, fr)), "ctrl");
            Add("Degraded substate", fr => _s.Enums.LabelOf(EnumNames.DegradedSubstate, _s.Table.GetInt(f.Substate, fr)), "ctrl");
            Add("Trigger reason", fr => _s.Enums.LabelOf(EnumNames.TriggerReason, _s.Table.GetInt(f.Reason, fr)), "ctrl");
            Add("Alert", fr => _s.Enums.LabelOf(EnumNames.AlertCode, _s.Table.GetInt(f.Alert, fr)), "ctrl");
            Add("Global demand", fr => Fmt.Value(_s.Table.Get(f.Demand, fr), f.Demand), "ctrl");
            Add("Safety shutdown", fr => _s.Table.GetBool(f.SafetyShutdown, fr) ? "ACTIVE" : "no", "ctrl");
            Add("Fault latched", fr => _s.Table.GetBool(f.FaultLatched, fr) ? "yes" : "no", "ctrl");
            Add("Highest-priority fault", fr =>
            {
                var code = _s.Table.GetInt(f.FaultCode, fr);
                return code > 0 ? code + " · " + _s.Faults.Describe(code) : "none (0)";
            }, "ctrl");
            Add("Clinician mode", fr => _s.Table.GetBool(f.ClinicianMode, fr) ? "yes" : "no", "ctrl");
            Add("Twin data stale", fr => _s.Table.GetBool(f.DataStaleTwin, fr) ? "STALE" : "fresh", "ctrl");
            Add("Hardware data stale", fr => _s.Table.GetBool(f.DataStaleHw, fr) ? "STALE" : "fresh", "ctrl");
            Section("CHANNEL COMMANDS", "replay ctrl group");
            for (int c = 0; c < 4; c++)
            {
                int cc = c;
                Add("CH" + (c + 1) + " " + ChannelRules.Limbs[c].ToLowerInvariant(), fr => ChannelRules.Compute(_s, fr, cc + 1).StatusText, "ctrl");
            }
            AddAction("Focus camera", () => FocusRequested?.Invoke());
        }

        private void PatientSignalRows()
        {
            var f = _s.F;
            Add("Patient temperature signal T_obs", fr =>
            {
                double v = _s.Table.Get(f.TObs, fr);
                bool miss = double.IsNaN(v) || _s.Table.GetBool(f.ObsMissing, fr);
                return miss ? "no observation at this frame" : Fmt.Value(v, f.TObs);
            }, "obs");
            Add("Twin estimate T_est ± SD", fr =>
            {
                double v = _s.Table.Get(f.TEst, fr), sd = _s.Table.Get(f.TEstSd, fr);
                if (double.IsNaN(v)) return "unavailable (null in replay)";
                return Fmt.Value(v, f.TEst) + (double.IsNaN(sd) ? " (SD not supplied)" : " ± " + Fmt.Number(sd, 3));
            }, "twin");
            Add("Twin validity", fr => _s.Enums.LabelOf(EnumNames.TwinValid, _s.Table.GetInt(f.TwinValid, fr)), "twin");
        }

        private string Val(FieldDef fd, int fr)
        {
            double v = _s.Table.Get(fd, fr);
            return double.IsNaN(v) ? "unavailable (null in replay)" : Fmt.Value(v, fd);
        }

        // ------------------------------------------------------------------ element helpers

        private void Section(string title, string sub)
        {
            var box = UiUtil.Box("dp-section");
            box.Add(UiUtil.Label(title, "dp-section-title"));
            if (!string.IsNullOrEmpty(sub)) box.Add(UiUtil.Label(sub, "dp-section-sub"));
            _body.Add(box);
        }

        private void Note(string text) => _body.Add(UiUtil.Label(text, "dp-note"));

        private void Add(string name, Func<int, string> get, string group)
        {
            var row = UiUtil.Box("dp-row");
            row.Add(UiUtil.Label(name, "dp-name"));
            var v = UiUtil.Label("—", "dp-value");
            row.Add(v);
            Label tag = null;
            if (group != null)
            {
                tag = UiUtil.Label("", "dp-tag");
                row.Add(tag);
            }
            _body.Add(row);
            _rows.Add(new Row { Value = v, Tag = tag, Get = get, TagOf = group == null ? (Func<int, string>)null : fr => _s.Tag(group, fr) });
        }

        private void AddAction(string text, System.Action onClick) => _actions.Add(UiUtil.Button(text, onClick, "btn", "btn-small"));

        public void ShowFrame(int frame)
        {
            _frame = frame;
            if (_s == null) return;
            foreach (var r in _rows)
            {
                string v;
                try { v = r.Get(frame); }
                catch (Exception ex) { v = "error: " + ex.Message; }
                UiUtil.SetText(r.Value, v);
                r.Value.EnableInClassList("value-missing", v != null && (v.StartsWith("unavailable") || v.StartsWith("no observation") || v == Fmt.Missing));
                if (r.Tag != null && r.TagOf != null)
                {
                    var tag = r.TagOf(frame) ?? "";
                    UiUtil.SetText(r.Tag, tag);
                    var cls = "tag-" + tag;
                    if (r.Tag.userData is string prev && prev != cls) r.Tag.RemoveFromClassList(prev);
                    r.Tag.AddToClassList(cls);
                    r.Tag.userData = cls;
                }
            }
        }
    }
}
