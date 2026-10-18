using System.Globalization;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Header status chips: play state, playback speed, controller state + twin validity at the current frame,
    /// SYNTHETIC REPLAY badge (header cohort), and an ASSUMED / SIMULATED marker whenever any group in the replay carries
    /// a SIMULATED or ASSUMED source tag. All values are read from the replay; nothing is inferred.
    /// </summary>
    public sealed class HeaderStatus : IReplayView
    {
        private readonly ReplayClock _clock;
        private readonly Label _play, _speed, _model, _synthetic, _assumed, _disclaimer;
        private ReplaySession _s;

        public HeaderStatus(VisualElement root, ReplayClock clock)
        {
            _clock = clock;
            _play = UiUtil.Req<Label>(root, "hdr-play-state");
            _speed = UiUtil.Req<Label>(root, "hdr-speed");
            _model = UiUtil.Req<Label>(root, "hdr-model");
            _synthetic = UiUtil.Req<Label>(root, "hdr-synthetic");
            _assumed = UiUtil.Req<Label>(root, "hdr-assumed");
            _disclaimer = UiUtil.Req<Label>(root, "hdr-disclaimer");
            _clock.StateChanged += RefreshClock;
            Unbind();
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            bool synthetic = s.Header.IsSynthetic;
            _synthetic.text = synthetic ? "SYNTHETIC REPLAY" : "DEVELOPMENT REPLAY";
            UiUtil.Show(_synthetic, true);
            _synthetic.EnableInClassList("hdr-badge-synthetic", synthetic);
            bool anySimOrAssumed = false;
            foreach (var g in ProvenanceRules.Groups)
            {
                var tag = s.Tag(g, 0);
                if (tag == "SIMULATED" || tag == "ASSUMED") anySimOrAssumed = true;
            }
            // The persistent footer and every panel tag already mark SIMULATED / ASSUMED values; a header badge here was
            // clipped at 1366 px, so it stays hidden (18 Oct 2026).
            UiUtil.Show(_assumed, false);
            _assumed.EnableInClassList("has-sim-assumed", anySimOrAssumed);
            _assumed.text = "SIM / ASSUMED";
            _assumed.tooltip = "SIMULATED and ASSUMED values are marked where they appear";
            _disclaimer.text = string.IsNullOrEmpty(s.Header.Disclaimer)
                ? "Proof-of-concept replay viewer · not for treatment decisions"
                : s.Header.Disclaimer;
            RefreshClock();
        }

        public void Unbind()
        {
            _s = null;
            UiUtil.Show(_synthetic, false);
            UiUtil.Show(_assumed, false);
            _model.text = "no replay";
            _disclaimer.text = "Proof-of-concept replay viewer · not for treatment decisions";
            RefreshClock();
        }

        private void RefreshClock()
        {
            var m = _clock.Model;
            if (m == null)
            {
                UiUtil.SetText(_play, "NO REPLAY");
                UiUtil.SetText(_speed, "×—");
                return;
            }
            string st = m.Playing ? "PLAYING" : m.AtEnd ? "END" : "PAUSED";
            UiUtil.SetText(_play, st);
            _play.EnableInClassList("hdr-playing", m.Playing);
            UiUtil.SetText(_speed, "×" + m.Speed.ToString("0", CultureInfo.InvariantCulture));
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var t = _s.Table;
            var state = _s.Enums.LabelOf(EnumNames.ControllerState, t.GetInt(_s.F.State, frame));
            var tv = _s.Enums.LabelOf(EnumNames.TwinValid, t.GetInt(_s.F.TwinValid, frame));
            string twinTag = _s.Tag("twin", frame);
            UiUtil.SetText(_model, "Ctrl " + state + " · Twin " + tv);
            _model.tooltip = "Controller: " + state + " · Twin: " + tv + " (" + twinTag + ")";
            RefreshClock();
        }
    }
}
