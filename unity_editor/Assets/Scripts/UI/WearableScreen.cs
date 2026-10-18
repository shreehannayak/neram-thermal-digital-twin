using System;
using System.Globalization;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Watch-face overlay anchored to the wrist wearable's screen. Two explicit modes:
    ///   MirrorReplay  - shows replay values (T_obs, controller state) with their source tag. The wearable itself has
    ///                   no channel in replay schema v1.0, so the face says "MIRROR" and never implies the watch measured it.
    ///   SyntheticDemo - a deterministic pattern derived only from replay TIME, labelled "SYNTHETIC DEMO · not data".
    /// </summary>
    public sealed class WearableScreen : IReplayView
    {
        public enum Mode { MirrorReplay, SyntheticDemo }

        private readonly VisualElement _card;
        private readonly Label _mode, _value, _sub;
        private readonly Camera _cam;
        private readonly Transform _anchor;
        private ReplaySession _s;
        private int _frame;
        public Mode CurrentMode = Mode.MirrorReplay;

        public WearableScreen(VisualElement root, Camera cam, Transform anchor)
        {
            _cam = cam;
            _anchor = anchor;
            _card = UiUtil.Req<VisualElement>(root, "wearable-screen");
            _card.pickingMode = PickingMode.Ignore;
            _mode = UiUtil.Label("", "ws-mode");
            _value = UiUtil.Label("", "ws-value");
            _sub = UiUtil.Label("", "ws-sub");
            _card.Add(_mode);
            _card.Add(_value);
            _card.Add(_sub);
            UiUtil.Show(_card, false);
        }

        public void SetMode(Mode m)
        {
            CurrentMode = m;
            ShowFrame(_frame);
        }

        public void Bind(ReplaySession s) => _s = s;

        public void Unbind()
        {
            _s = null;
            UiUtil.Show(_card, false);
        }

        public void ShowFrame(int frame)
        {
            _frame = frame;
            if (_s == null) return;
            if (CurrentMode == Mode.MirrorReplay)
            {
                UiUtil.SetText(_mode, "MIRROR · replay " + _s.Tag("obs", frame));
                double v = _s.Table.Get(_s.F.TObs, frame);
                bool miss = double.IsNaN(v) || _s.Table.GetBool(_s.F.ObsMissing, frame);
                UiUtil.SetText(_value, miss ? "— °C" : Fmt.Value(v, _s.F.TObs));
                UiUtil.SetText(_sub, _s.Enums.LabelOf(EnumNames.ControllerState, _s.Table.GetInt(_s.F.State, frame)));
                _card.EnableInClassList("ws-synthetic", false);
            }
            else
            {
                double t = _s.Table.T[frame] - _s.Table.StartTime;
                int pattern = (int)(50 + 20 * Math.Sin(t / 90.0));
                UiUtil.SetText(_mode, "SYNTHETIC DEMO · not data");
                UiUtil.SetText(_value, pattern.ToString(CultureInfo.InvariantCulture) + " %");
                UiUtil.SetText(_sub, "demo pattern from replay time");
                _card.EnableInClassList("ws-synthetic", true);
            }
        }

        /// <summary>Keep the card on the projected screen anchor (call every LateUpdate).</summary>
        public void UpdatePosition()
        {
            if (_s == null || _cam == null || _anchor == null || _card.panel == null) { UiUtil.Show(_card, false); return; }
            var sp = _cam.WorldToScreenPoint(_anchor.position);
            var rb = _card.panel.visualTree.worldBound;
            float dist = Vector3.Distance(_cam.transform.position, _anchor.position);
            bool visible = sp.z > 0 && dist < 3.2f && sp.x >= 0 && sp.x <= Screen.width && sp.y >= 0 && sp.y <= Screen.height;
            UiUtil.Show(_card, visible);
            if (!visible || Screen.width <= 0 || Screen.height <= 0) return;
            float x = sp.x / Screen.width * rb.width;
            float y = (Screen.height - sp.y) / Screen.height * rb.height;
            _card.style.left = x;
            _card.style.top = y;
        }
    }
}
