using System;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    public enum WorldLabelMode { Off, Compact, Detailed }

    /// <summary>
    /// UI elements anchored to 3D positions: one chip per module (channel, limb, status, heating command), a controller
    /// display chip, and the single thermal-state indicator near the patient (no body heat map: the model has no spatial
    /// temperature field). Positions are updated every LateUpdate from the camera; content only when the frame changes.
    ///
    /// Modes (Settings drawer): Compact (default) shows one short line per chip ("CH3 18 %", "CTRL ACTIVE_WARMING") and the
    /// selected region's full name; the twin call-out is hidden because the same values are always visible in the left
    /// column. Detailed restores the full call-outs. Off hides everything except the selected chip.
    /// </summary>
    public sealed class WorldLabels
    {
        private sealed class Chip
        {
            public VisualElement Root;
            public Label Title, Value, Short;
            public Transform Anchor;
            public ChannelStatus? Status;
        }

        private readonly VisualElement _layer;
        private readonly Camera _cam;
        private readonly NeramAssemblyBinder _asm;
        private readonly Chip[] _modules = new Chip[4];
        private readonly Chip _ctrl;
        private readonly VisualElement _ti, _tiScale, _tiDot, _tiHypo, _tiTarget;
        private readonly Label _tiValue, _tiBand, _tiNote;
        private ReplaySession _s;
        private double _scaleMin, _scaleMax;
        private float _offset = 0.12f;
        private int _selected = -1;
        private WorldLabelMode _mode = WorldLabelMode.Compact;

        public WorldLabelMode Mode
        {
            get => _mode;
            set
            {
                _mode = value;
                _layer.EnableInClassList("wl-mode-off", value == WorldLabelMode.Off);
                _layer.EnableInClassList("wl-mode-compact", value == WorldLabelMode.Compact);
                _layer.EnableInClassList("wl-mode-detailed", value == WorldLabelMode.Detailed);
            }
        }

        public event Action<int> ChipClicked;

        public WorldLabels(VisualElement layer, Camera cam, NeramAssemblyBinder asm)
        {
            _layer = layer;
            _cam = cam;
            _asm = asm;
            for (int i = 0; i < 4; i++)
            {
                var c = new Chip { Root = UiUtil.Box("wl-chip", "ui-block") };
                c.Title = UiUtil.Label("CH" + (i + 1) + " · " + ChannelRules.Limbs[i].ToUpperInvariant(), "wl-title");
                c.Value = UiUtil.Label("—", "wl-value");
                c.Short = UiUtil.Label("CH" + (i + 1), "wl-short");
                c.Root.Add(c.Title);
                c.Root.Add(c.Value);
                c.Root.Add(c.Short);
                c.Root.pickingMode = PickingMode.Position;
                c.Root.AddToClassList(i < 2 ? "wl-hand" : "wl-foot");
                int ch = i + 1;
                c.Root.RegisterCallback<ClickEvent>(_ => ChipClicked?.Invoke(ch));
                c.Anchor = asm != null && asm.Modules[i] != null ? asm.Modules[i].transform : null;
                _layer.Add(c.Root);
                _modules[i] = c;
            }
            _ctrl = new Chip { Root = UiUtil.Box("wl-chip", "ui-block") };
            _ctrl.Title = UiUtil.Label("BEDSIDE CONTROLLER (SIMULATED)", "wl-title");
            _ctrl.Value = UiUtil.Label("—", "wl-value");
            _ctrl.Short = UiUtil.Label("CTRL", "wl-short");
            _ctrl.Root.Add(_ctrl.Title);
            _ctrl.Root.Add(_ctrl.Value);
            _ctrl.Root.Add(_ctrl.Short);
            _ctrl.Root.RegisterCallback<ClickEvent>(_ => ChipClicked?.Invoke(0));
            _ctrl.Anchor = asm != null && asm.Controller != null ? asm.Controller.transform : null;
            _layer.Add(_ctrl.Root);

            _ti = UiUtil.Box("wl-chip", "ui-block");
            _ti.name = "thermal-indicator";
            _ti.Add(UiUtil.Label("THERMAL STATE ESTIMATE (TWIN)", "wl-title"));
            _tiValue = UiUtil.Label("—", "wl-value");
            _tiValue.style.fontSize = 18;
            _ti.Add(_tiValue);
            _tiScale = UiUtil.Box("ti-scale");
            _tiHypo = UiUtil.Box("ti-marker");
            _tiHypo.style.backgroundColor = (Color)new Color32(248, 113, 113, 255);
            _tiTarget = UiUtil.Box("ti-marker");
            _tiTarget.style.backgroundColor = (Color)new Color32(52, 211, 153, 255);
            _tiDot = UiUtil.Box("ti-dot");
            _tiScale.Add(_tiHypo);
            _tiScale.Add(_tiTarget);
            _tiScale.Add(_tiDot);
            _ti.Add(_tiScale);
            _tiBand = UiUtil.Label("", "t-xs", "c-2");
            _tiBand.style.marginTop = 4;
            _ti.Add(_tiBand);
            _tiNote = UiUtil.Label("", "t-xs", "c-3", "wrap");
            _tiNote.style.maxWidth = 200;
            _ti.Add(_tiNote);
            _layer.Add(_ti);
            SetVisible(false);
            Mode = WorldLabelMode.Compact;
        }

        public void SetSelected(int channel)
        {
            _selected = channel;
            for (int i = 0; i < 4; i++) _modules[i].Root.EnableInClassList("wl-selected", channel == i + 1);
            _ctrl.Root.EnableInClassList("wl-selected", channel == 0);
        }

        private void SetVisible(bool v)
        {
            UiUtil.Show(_layer, v); // the whole layer, so no mode rule can show a chip without a replay
            foreach (var c in _modules) UiUtil.Show(c.Root, v);
            UiUtil.Show(_ctrl.Root, v);
            UiUtil.Show(_ti, v);
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            _offset = (float)s.Display.ModuleLabelOffsetM;
            var th = ThermalRules.Compute(s, 0);
            double lo = double.IsNaN(th.THypo) ? 35 : th.THypo - 1.5;
            double hi = !double.IsNaN(th.TTarget) ? th.TTarget + 1.0 : (!double.IsNaN(th.THypo) ? th.THypo + 1.5 : 38);
            _scaleMin = lo;
            _scaleMax = hi;
            UiUtil.Show(_tiHypo, !double.IsNaN(th.THypo));
            UiUtil.Show(_tiTarget, !double.IsNaN(th.TTarget));
            if (!double.IsNaN(th.THypo)) _tiHypo.style.left = new StyleLength(new Length(Pct(th.THypo), LengthUnit.Percent));
            if (!double.IsNaN(th.TTarget)) _tiTarget.style.left = new StyleLength(new Length(Pct(th.TTarget), LengthUnit.Percent));
            UiUtil.SetText(_tiNote, "display banding only, not a clinical classification; " + th.ThresholdNote);
            SetVisible(true);
        }

        private float Pct(double v) => Mathf.Clamp01((float)((v - _scaleMin) / (_scaleMax - _scaleMin))) * 100f;

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            for (int i = 0; i < 4; i++)
            {
                var v = ChannelRules.Compute(_s, frame, i + 1);
                var c = _modules[i];
                UiUtil.SetText(c.Value, v.StatusText);
                UiUtil.SetText(c.Short, "CH" + (i + 1) + "  " + (v.Status == ChannelStatus.Heating ? Fmt.Number(v.Heat, 0) + " %" : v.Status == ChannelStatus.Off ? "off" : v.Status.ToString().ToUpperInvariant()));
                if (c.Status != v.Status)
                {
                    if (c.Status.HasValue) c.Root.RemoveFromClassList("wl-status-" + c.Status.Value);
                    c.Root.AddToClassList("wl-status-" + v.Status);
                    c.Status = v.Status;
                }
            }
            var b = BannerRules.Compute(_s, frame);
            UiUtil.SetText(_ctrl.Value, b.StateName + (b.AlertSeverity != "none" ? "  ·  " + b.AlertLabel : ""));
            UiUtil.SetText(_ctrl.Short, "CTRL  " + b.StateName);
            var th = ThermalRules.Compute(_s, frame);
            UiUtil.SetText(_tiValue, double.IsNaN(th.Estimate) ? "—" : Fmt.Number(th.Estimate, 2) + " ± " + Fmt.Number(th.Sd, 2) + " °C");
            UiUtil.SetText(_tiBand, th.BandText);
            foreach (ThermalBand band in Enum.GetValues(typeof(ThermalBand))) _ti.EnableInClassList("band-" + band, band == th.Band);
            UiUtil.Show(_tiDot, !double.IsNaN(th.Estimate));
            if (!double.IsNaN(th.Estimate)) _tiDot.style.left = new StyleLength(new Length(Pct(th.Estimate), LengthUnit.Percent));
        }

        /// <summary>Move anchored elements to their projected positions (call every LateUpdate).</summary>
        public void UpdatePositions()
        {
            if (_s == null || _cam == null || _layer.panel == null) return;
            for (int i = 0; i < 4; i++) Place(_modules[i].Root, _modules[i].Anchor, _offset);
            Place(_ctrl.Root, _ctrl.Anchor, 0.16f);
            Place(_ti, _asm != null ? _asm.thermalAnchor : null, 0f);
        }

        private void Place(VisualElement e, Transform anchor, float up)
        {
            if (anchor == null || !anchor.gameObject.activeInHierarchy) { e.style.visibility = Visibility.Hidden; return; }
            var world = anchor.position + Vector3.up * up;
            var vp = _cam.WorldToViewportPoint(world);
            if (vp.z <= 0) { e.style.visibility = Visibility.Hidden; return; }
            var p = RuntimePanelUtils.CameraTransformWorldToPanel(_layer.panel, world, _cam);
            e.style.visibility = Visibility.Visible;
            e.style.left = p.x;
            e.style.top = p.y;
        }

        public void Unbind()
        {
            _s = null;
            SetVisible(false);
        }
    }
}
