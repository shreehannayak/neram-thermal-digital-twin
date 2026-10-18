using System.Collections.Generic;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>Replay controls: play/pause, step, speed (x1/x2/x4/x10/x60, see ReplayClockModel.Speeds), restart, event
    /// navigation and the scrubbing timeline.</summary>
    public sealed class TransportBar : IReplayView
    {
        private readonly ReplayClock _clock;
        private readonly Button _play;
        private readonly List<Button> _speeds = new List<Button>();
        private readonly TimelineStripElement _strip;
        private readonly Label _status, _tlStart, _tlEnd, _clockTime, _clockSub;
        private ReplaySession _s;

        public TransportBar(VisualElement root, ReplayClock clock)
        {
            _clock = clock;
            _play = UiUtil.Req<Button>(root, "t-play");
            _play.clicked += () => _clock.TogglePlay();
            UiUtil.Req<Button>(root, "t-restart").clicked += () => _clock.Restart();
            UiUtil.Req<Button>(root, "t-step-back").clicked += () => _clock.StepBack();
            UiUtil.Req<Button>(root, "t-step-fwd").clicked += () => _clock.StepForward();
            UiUtil.Req<Button>(root, "t-prev-event").clicked += () => Jump(EventCategory.All, false);
            UiUtil.Req<Button>(root, "t-next-event").clicked += () => Jump(EventCategory.All, true);
            UiUtil.Req<Button>(root, "j-transition").clicked += () => Jump(EventCategory.Transition, true);
            UiUtil.Req<Button>(root, "j-fault").clicked += () => Jump(EventCategory.Fault, true);
            UiUtil.Req<Button>(root, "j-safety").clicked += () => Jump(EventCategory.Safety, true);
            UiUtil.Req<Button>(root, "j-clinician").clicked += () => Jump(EventCategory.Clinician, true);
            UiUtil.Req<Button>(root, "j-flag").clicked += () => Jump(EventCategory.Flag, true);
            AddSpeed(root, "t-speed-1", 1);
            AddSpeed(root, "t-speed-2", 2);
            AddSpeed(root, "t-speed-4", 4);
            AddSpeed(root, "t-speed-10", 10);
            AddSpeed(root, "t-speed-60", 60);
            _status = UiUtil.Req<Label>(root, "t-status");
            _tlStart = UiUtil.Req<Label>(root, "tl-start");
            _tlEnd = UiUtil.Req<Label>(root, "tl-end");
            _clockTime = UiUtil.Req<Label>(root, "clock-time");
            _clockSub = UiUtil.Req<Label>(root, "clock-sub");
            _strip = new TimelineStripElement();
            _strip.style.flexGrow = 1;
            UiUtil.Req<VisualElement>(root, "timeline").Add(_strip);
            _strip.Scrub += x => _clock.SeekFraction(x);
            _clock.StateChanged += RefreshState;
        }

        private void AddSpeed(VisualElement root, string name, double speed)
        {
            var b = UiUtil.Req<Button>(root, name);
            b.userData = speed;
            b.clicked += () => _clock.SetSpeed(speed);
            _speeds.Add(b);
        }

        /// <summary>Jump to the next/previous event of a category (also used by keyboard shortcuts).</summary>
        public void Jump(EventCategory mask, bool forward)
        {
            if (_s == null) return;
            var e = forward ? _s.Events.Next(_clock.Frame, mask) : _s.Events.Previous(_clock.Frame, mask);
            if (e != null) _clock.SeekFrame(e.Frame);
            UiUtil.SetText(_status, e != null ? "→ " + e.Title : "no further " + mask.ToString().ToLowerInvariant() + " event");
        }

        private void RefreshState()
        {
            var m = _clock.Model;
            if (m == null) return;
            UiUtil.SetText(_play, m.Playing ? "PAUSE" : "PLAY");
            Button sel = null;
            foreach (var b in _speeds) if (b.userData is double d && d == m.Speed) sel = b;
            UiUtil.Select(_speeds, sel);
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            _strip.Bind(s);
            UiUtil.SetText(_tlStart, Fmt.Time(s.Table.StartTime));
            UiUtil.SetText(_tlEnd, Fmt.Time(s.Table.EndTime));
            RefreshState();
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            _strip.SetFrame(frame);
            var m = _clock.Model;
            UiUtil.SetText(_clockTime, Fmt.Time(_s.Table.T[frame]));
            UiUtil.SetText(_clockSub, "frame " + (frame + 1) + " / " + _s.Table.FrameCount + "  ·  elapsed " + Fmt.Time(m.Elapsed).Substring(2) +
                                      "  ·  " + (m.Playing ? "playing" : "paused") + " x" + m.Speed);
        }

        public void Unbind()
        {
            _s = null;
            _strip.Unbind();
            UiUtil.SetText(_clockTime, "T+00:00:00");
            UiUtil.SetText(_clockSub, "no replay");
        }
    }
}
