using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Controller state banner. Shows exactly what the external controller log says (Controller_State, Degraded_Substate,
    /// Trigger_Reason, Alert, Safety_Shutdown, Fault_Latched, Clinician_Mode, optional Data_Stale_*). Unity does NOT compute
    /// transitions: there is no state machine in this project's C# code. The state timeline is drawn by TimelineStripElement.
    /// </summary>
    public sealed class ControllerStatePanel : IReplayView
    {
        private readonly VisualElement _banner, _chips;
        private readonly Label _state, _sub, _subline;
        private readonly SourceBadge _badge;
        private readonly Label _cSafety, _cLatched, _cClin, _cStaleT, _cStaleH, _cAlert;
        private ReplaySession _s;

        public ControllerStatePanel(VisualElement root)
        {
            _banner = UiUtil.Req<VisualElement>(root, "controller-banner");
            _state = UiUtil.Req<Label>(root, "banner-state");
            _sub = UiUtil.Req<Label>(root, "banner-substate");
            _subline = UiUtil.Req<Label>(root, "banner-sub");
            _chips = UiUtil.Req<VisualElement>(root, "banner-chips");
            _badge = new SourceBadge("ctrl");
            UiUtil.Req<VisualElement>(root, "banner-src").Add(_badge.Root);
            _cAlert = UiUtil.Chip("", "chip-info");
            _cSafety = UiUtil.Chip("SAFETY SHUTDOWN", "chip-crit");
            _cLatched = UiUtil.Chip("FAULT LATCHED", "chip-warn");
            _cClin = UiUtil.Chip("CLINICIAN MODE", "chip-info");
            _cStaleT = UiUtil.Chip("TWIN DATA STALE", "chip-warn");
            // Stale hardware data is a data-quality warning, not a critical state (red is reserved for shutdown/critical).
            _cStaleH = UiUtil.Chip("HW DATA STALE", "chip-warn");
            foreach (var c in new[] { _cAlert, _cSafety, _cLatched, _cClin, _cStaleT, _cStaleH }) _chips.Add(c);
            HideChips(); // nothing is shown before a replay frame says so (seen in Unity: all chips visible while loading)
        }

        private void HideChips()
        {
            foreach (var c in new[] { _cAlert, _cSafety, _cLatched, _cClin, _cStaleT, _cStaleH }) UiUtil.Show(c, false);
        }

        public void Bind(ReplaySession s) => _s = s;

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var v = BannerRules.Compute(_s, frame);
            UiUtil.SetText(_state, v.StateLabel.ToUpperInvariant());
            _state.style.color = UiUtil.StateColor(v.StateName);
            UiUtil.SetText(_sub, v.SubstateLabel != null ? "· " + v.SubstateLabel : "");
            UiUtil.SetText(_subline, v.StateName + "  ·  since " + Fmt.Time(v.SinceT) + "  ·  reason: " + v.ReasonLabel);
            _banner.EnableInClassList("tone-neutral", v.Tone == BannerTone.Neutral);
            _banner.EnableInClassList("tone-warming", v.Tone == BannerTone.Warming);
            _banner.EnableInClassList("tone-degraded", v.Tone == BannerTone.Degraded);
            _banner.EnableInClassList("tone-critical", v.Tone == BannerTone.Critical);
            _banner.tooltip = v.StateDescription ?? "";

            bool alert = v.AlertSeverity != "none";
            UiUtil.Show(_cAlert, alert);
            if (alert)
            {
                UiUtil.SetText(_cAlert, "ALERT: " + v.AlertLabel.ToUpperInvariant());
                _cAlert.EnableInClassList("chip-crit", v.AlertSeverity == "critical");
                _cAlert.EnableInClassList("chip-warn", v.AlertSeverity == "warning");
                _cAlert.EnableInClassList("chip-info", v.AlertSeverity == "info");
            }
            UiUtil.Show(_cSafety, v.SafetyShutdown);
            UiUtil.Show(_cLatched, v.FaultLatched);
            UiUtil.Show(_cClin, v.ClinicianMode);
            UiUtil.Show(_cStaleT, !double.IsNaN(v.DataStaleTwin) && v.DataStaleTwin > 0.5);
            UiUtil.Show(_cStaleH, !double.IsNaN(v.DataStaleHw) && v.DataStaleHw > 0.5);
            _badge.Set(_s, "ctrl", frame);
        }

        public void Unbind()
        {
            _s = null;
            UiUtil.SetText(_state, "NO REPLAY");
            UiUtil.SetText(_sub, "");
            UiUtil.SetText(_subline, "");
            HideChips();
        }
    }
}
