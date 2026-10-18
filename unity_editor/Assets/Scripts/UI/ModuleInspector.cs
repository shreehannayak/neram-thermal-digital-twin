using System;
using System.Collections.Generic;
using System.Globalization;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Card for the selected 3D object: a warming module (channel 1-4) or the bedside controller (0).
    /// Shows only replayed values (heating command, sensor A/B, current, connection, cutoff, fault code) and whether the
    /// geometry is CAD or PLACEHOLDER. Buttons: exploded view (modules), focus camera, close.
    /// Sensor values are hardware telemetry from the replay "hw" group; Unity does not compare them to any limit.
    /// </summary>
    public sealed class ModuleInspector : IReplayView
    {
        private readonly VisualElement _root;
        private readonly NeramAssemblyBinder _asm;
        private readonly CameraRig _rig;
        private readonly Label _title, _sub, _status, _geom;
        private readonly VisualElement _rows;
        private readonly Button _explode, _focus;
        private readonly Dictionary<string, Label> _values = new Dictionary<string, Label>();
        private ReplaySession _s;
        private int _selected = -1;
        private int _lastFrame = -1;

        /// <summary>Raised when the card is closed, so the app can clear the 3D selection.</summary>
        public event Action Closed;

        public int Selected => _selected;

        public ModuleInspector(VisualElement appRoot, NeramAssemblyBinder asm, CameraRig rig)
        {
            _root = UiUtil.Req<VisualElement>(appRoot, "module-inspector");
            _asm = asm;
            _rig = rig;
            _root.Clear();
            var head = UiUtil.Box("row", "panel-head");
            var titles = UiUtil.Box();
            titles.style.flexGrow = 1;
            _title = UiUtil.Label("—", "panel-title");
            _sub = UiUtil.Label("", "t-xs", "c-3");
            titles.Add(_title);
            titles.Add(_sub);
            head.Add(titles);
            head.Add(UiUtil.Button("x", Close, "btn-ghost", "btn-icon"));
            _root.Add(head);

            _status = UiUtil.Label("—", "mi-status");
            _status.style.fontSize = 16;
            _status.style.marginTop = 4;
            _status.style.marginBottom = 4;
            _root.Add(_status);

            _rows = UiUtil.Box();
            _root.Add(_rows);

            _geom = UiUtil.Label("", "t-xs", "c-3", "wrap");
            _geom.style.marginTop = 6;
            _root.Add(_geom);

            var buttons = UiUtil.Box("row");
            buttons.style.marginTop = 8;
            _explode = UiUtil.Button("Exploded view", ToggleExploded, "btn-ghost");
            _focus = UiUtil.Button("Focus camera", Focus, "btn-ghost");
            buttons.Add(_explode);
            buttons.Add(_focus);
            _root.Add(buttons);

            var note = UiUtil.Label("Replayed values only. Unity applies no limits and computes no controller output.", "t-xs", "c-3", "wrap");
            note.style.marginTop = 6;
            _root.Add(note);
            UiUtil.Show(_root, false);
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            _lastFrame = -1;
        }

        public void Unbind()
        {
            _s = null;
            Close();
        }

        /// <summary>Open the card for a channel (1-4), the controller (0); -1 closes.</summary>
        public void Select(int target, int frame)
        {
            if (target < 0) { Close(); return; }
            _selected = target;
            BuildRows();
            UiUtil.Show(_root, true);
            _lastFrame = -1;
            ShowFrame(frame);
        }

        private void Close()
        {
            bool wasOpen = _selected >= 0;
            _selected = -1;
            UiUtil.Show(_root, false);
            if (wasOpen) Closed?.Invoke();
        }

        private void BuildRows()
        {
            _rows.Clear();
            _values.Clear();
            string[] keys = _selected == 0
                ? new[] { "Controller state", "Degraded substate", "Trigger reason", "Alert", "Safety shutdown", "Fault latched", "Fault code", "Clinician mode", "Data stale (twin)", "Data stale (HW)", "Source tag (ctrl)" }
                : new[] { "Heating command", "Sensor A", "Sensor B", "Heater current", "Connected", "HW cutoff", "Channel fault", "Source tag (hw)" };
            foreach (var k in keys)
            {
                _rows.Add(UiUtil.KeyValue(k, Fmt.Missing, out var v));
                _values[k] = v;
            }
            bool module = _selected >= 1;
            UiUtil.Show(_explode, module && _asm != null && _asm.Modules[_selected - 1] != null);
            if (module)
            {
                _title.text = "CH" + _selected + " · " + ChannelRules.Limbs[_selected - 1].ToUpperInvariant() + " MODULE";
                _sub.text = SceneNames.Modules[_selected - 1] + " · flexible resistive heater module (prototype)";
                var mv = _asm != null ? _asm.Modules[_selected - 1] : null;
                _explode.text = mv != null && mv.Exploded ? "Assembled view" : "Exploded view";
            }
            else
            {
                _title.text = "BEDSIDE CONTROLLER";
                _sub.text = SceneNames.Controller + " · SIMULATED + CLINICIAN-SUPERVISED PROTOTYPE (mains bedside unit)";
            }
            _geom.text = GeometryText();
        }

        private string GeometryText()
        {
            if (_asm == null) return "Geometry: assembly binder not found.";
            string role = _selected == 0 ? SceneNames.Controller : SceneNames.Modules[_selected - 1];
            foreach (var r in _asm.Report)
                if (r.StartsWith(role + ":", StringComparison.Ordinal))
                    return "Geometry: " + r.Substring(role.Length + 1).Trim() + (r.EndsWith("PLACEHOLDER", StringComparison.Ordinal)
                        ? " — generated stand-in; dimensions are not CAD" : "");
            return "Geometry: unknown";
        }

        private void Set(string key, string value)
        {
            if (_values.TryGetValue(key, out var l)) UiUtil.SetText(l, value);
        }

        private static string YesNo(ReplayTable t, FieldDef f, int frame)
        {
            if (f == null) return Fmt.Missing;
            double v = t.Get(f, frame);
            return double.IsNaN(v) ? Fmt.Missing : (v != 0 ? "yes" : "no");
        }

        public void ShowFrame(int frame)
        {
            if (_s == null || _selected < 0 || frame == _lastFrame) return;
            _lastFrame = frame;
            var t = _s.Table;
            var f = _s.F;
            if (_selected == 0)
            {
                var b = BannerRules.Compute(_s, frame);
                UiUtil.SetText(_status, b.StateLabel ?? b.StateName ?? Fmt.Missing);
                _status.style.color = UiUtil.StateColor(b.StateName);
                Set("Controller state", b.StateName ?? Fmt.Missing);
                Set("Degraded substate", string.IsNullOrEmpty(b.SubstateLabel) ? Fmt.Missing : b.SubstateLabel);
                Set("Trigger reason", string.IsNullOrEmpty(b.ReasonLabel) ? Fmt.Missing : b.ReasonLabel);
                Set("Alert", string.IsNullOrEmpty(b.AlertLabel) ? Fmt.Missing : b.AlertLabel + " (" + b.AlertSeverity + ")");
                Set("Safety shutdown", YesNo(t, f.SafetyShutdown, frame));
                Set("Fault latched", YesNo(t, f.FaultLatched, frame));
                double code = t.Get(f.FaultCode, frame);
                Set("Fault code", double.IsNaN(code) ? Fmt.Missing : code == 0 ? "0 (none)" : ((int)code).ToString(CultureInfo.InvariantCulture) + " — " + _s.Faults.Describe((int)code));
                Set("Clinician mode", YesNo(t, f.ClinicianMode, frame));
                Set("Data stale (twin)", f.DataStaleTwin == null ? Fmt.Missing : YesNo(t, f.DataStaleTwin, frame));
                Set("Data stale (HW)", f.DataStaleHw == null ? Fmt.Missing : YesNo(t, f.DataStaleHw, frame));
                Set("Source tag (ctrl)", _s.Tag("ctrl", frame) ?? Fmt.Missing);
                return;
            }
            var v = ChannelRules.Compute(_s, frame, _selected);
            UiUtil.SetText(_status, v.StatusText);
            Color c = v.Status == ChannelStatus.Heating ? new Color32(245, 158, 11, 255)
                : v.Status == ChannelStatus.Cutoff || v.Status == ChannelStatus.Shutdown ? new Color32(239, 68, 68, 255)
                : v.Status == ChannelStatus.Fault || v.Status == ChannelStatus.Disconnected ? new Color32(234, 179, 8, 255)
                : new Color32(148, 163, 184, 255);
            _status.style.color = c;
            int i = _selected - 1;
            Set("Heating command", Fmt.Value(v.Heat, f.Heat[i]));
            Set("Sensor A", Fmt.Value(v.TempA, f.TempA[i]));
            Set("Sensor B", Fmt.Value(v.TempB, f.TempB[i]));
            Set("Heater current", Fmt.Value(v.Current, f.Current[i]));
            Set("Connected", YesNo(t, f.Connected[i], frame));
            Set("HW cutoff", YesNo(t, f.Cutoff[i], frame));
            Set("Channel fault", v.FaultCode > 0 ? v.FaultCode.ToString(CultureInfo.InvariantCulture) + " — " + v.FaultText : "0 (none)");
            Set("Source tag (hw)", _s.Tag("hw", frame) ?? Fmt.Missing);
        }

        private void ToggleExploded()
        {
            if (_asm == null || _selected < 1) return;
            var mv = _asm.Modules[_selected - 1];
            if (mv == null) return;
            mv.SetExploded(!mv.Exploded);
            _explode.text = mv.Exploded ? "Assembled view" : "Exploded view";
            if (mv.Exploded) Focus();
        }

        private void Focus()
        {
            if (_rig == null || _asm == null || _selected < 0) return;
            Transform target = _selected == 0 ? (_asm.Controller != null ? _asm.Controller.transform : null)
                : (_asm.Modules[_selected - 1] != null ? _asm.Modules[_selected - 1].transform : null);
            if (target == null) return;
            _rig.Focus(Bounds(target).center, _selected == 0 ? 0.9f : 0.6f);
        }

        private static Bounds Bounds(Transform t)
        {
            var rs = t.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(t.position, Vector3.one * 0.1f);
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return b;
        }
    }
}
