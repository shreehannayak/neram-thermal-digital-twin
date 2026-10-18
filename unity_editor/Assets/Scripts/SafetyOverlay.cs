using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Safety presentation driven only by the replay:
    ///  - SAFETY_SHUTDOWN: full-width banner with the fault code and its display text, affected channels, latch time and
    ///    the reset state (awaiting / blocked); a short "released" notice after a clinician reset.
    ///  - Channel faults without shutdown: a strip listing each faulted channel and code.
    /// Heaters going dark is not decided here: it follows from Heat_i = 0 in the replay (ModuleView).
    /// </summary>
    public sealed class SafetyOverlay : IReplayView
    {
        private readonly VisualElement _root, _banner, _strip;
        private readonly Label _title, _detail, _reset, _released, _stripText;
        private ReplaySession _s;

        /// <summary>v4: false while the presenter has hidden the banner (×). The layout then reserves no space for it; the
        /// controller state stays visible in the header ("Controller: Safety shutdown").</summary>
        public System.Func<bool> BannerVisible;

        public SafetyOverlay(VisualElement root)
        {
            _root = root;
            _banner = UiUtil.Req<VisualElement>(root, "safety-banner");
            _title = UiUtil.Req<Label>(root, "safety-title");
            _detail = UiUtil.Req<Label>(root, "safety-detail");
            _reset = UiUtil.Req<Label>(root, "safety-reset");
            _released = UiUtil.Req<Label>(root, "safety-released");
            _strip = UiUtil.Req<VisualElement>(root, "channel-fault-strip");
            _stripText = UiUtil.Req<Label>(root, "channel-fault-text");
        }

        public void Bind(ReplaySession s) => _s = s;

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var v = SafetyRules.Compute(_s, frame);
            UiUtil.Show(_banner, v.InShutdown);
            _root.EnableInClassList("with-safety", v.InShutdown && (BannerVisible == null || BannerVisible()));
            if (v.InShutdown)
            {
                UiUtil.SetText(_title, v.Title);
                var chans = v.AffectedChannels.Count > 0 ? string.Join("   |   ", v.AffectedChannels) : "system-level fault (no single channel)";
                UiUtil.SetText(_detail, "fault_code " + v.FaultCode + " " + v.FaultName + ": " + v.FaultText + "\n" + chans +
                                        "\nlatched since " + Fmt.Time(v.LatchedAtT) + "  ·  all heating commands 0  ·  alert: " + v.AlertText);
                UiUtil.SetText(_reset, v.ResetText);
                _reset.EnableInClassList("blocked", v.Reset == ResetState.Blocked);
            }
            UiUtil.Show(_released, v.Reset == ResetState.Released);
            if (v.Reset == ResetState.Released) UiUtil.SetText(_released, v.ResetText);
            bool strip = !v.InShutdown && v.ChannelFaults.Count > 0 && v.Reset != ResetState.Released;
            UiUtil.Show(_strip, strip);
            if (strip) UiUtil.SetText(_stripText, "CHANNEL FAULT (latched, channel isolated): " + string.Join("   |   ", v.ChannelFaults));
        }

        public void Unbind()
        {
            _s = null;
            UiUtil.Show(_banner, false);
            UiUtil.Show(_strip, false);
            UiUtil.Show(_released, false);
            _root.EnableInClassList("with-safety", false);
        }
    }
}
