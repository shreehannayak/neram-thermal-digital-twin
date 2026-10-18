using System;
using System.Collections.Generic;
using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Event log + diagnostic inspector. Events are bookmarks derived from changes in the replay columns (EventIndex);
    /// clicking one seeks the clock. Model-probability flags are labelled "Possible artefact" / "Possible level shift"
    /// with their probability, never as confirmed physiological events. The inspector shows the selected point (chart click)
    /// or, by default, the current twin update: timestamp, event type, probability, observation, estimate, model source.
    /// </summary>
    public sealed class EventLogPanel : IReplayView
    {
        private readonly ScrollView _scroll;
        private readonly VisualElement _inspector, _filters;
        private readonly Action<int> _seek;
        private readonly List<(ReplayEvent ev, VisualElement row)> _rows = new List<(ReplayEvent, VisualElement)>();
        private readonly List<Button> _filterButtons = new List<Button>();
        private EventCategory _mask = EventCategory.All;
        private ReplaySession _s;
        private int _pinnedFrame = -1;
        private int _lastPast = -1;
        private int _lastInspected = -1;
        private bool _lastPinned;

        private static readonly (string label, EventCategory mask)[] Filters =
        {
            ("All", EventCategory.All), ("State", EventCategory.Transition), ("Safety", EventCategory.Safety | EventCategory.Fault),
            ("Clinician", EventCategory.Clinician), ("Twin", EventCategory.Twin), ("Flags", EventCategory.Flag), ("Alerts", EventCategory.Alert),
        };

        public EventLogPanel(VisualElement root, Action<int> seekFrame)
        {
            _seek = seekFrame;
            _scroll = UiUtil.Req<ScrollView>(root, "event-scroll");
            _inspector = UiUtil.Req<VisualElement>(root, "inspector");
            _filters = UiUtil.Req<VisualElement>(root, "event-filters");
            foreach (var (label, mask) in Filters)
            {
                var m = mask;
                Button b = null;
                b = UiUtil.Button(label, () => { _mask = m; UiUtil.Select(_filterButtons, b); ApplyFilter(); }, "btn-ghost");
                b.style.minHeight = 20;
                b.style.fontSize = 10;
                _filterButtons.Add(b);
                _filters.Add(b);
            }
            UiUtil.Select(_filterButtons, _filterButtons[0]);
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            _pinnedFrame = -1;
            _lastPast = -1;
            _lastInspected = -1;
            _scroll.Clear();
            _rows.Clear();
            foreach (var e in s.Events.All)
            {
                var row = UiUtil.Box("ev-row", "ev-sev-" + e.Severity);
                row.Add(UiUtil.Label(Fmt.Time(e.T), "ev-time"));
                row.Add(UiUtil.Box("ev-dot"));
                var title = UiUtil.Label(e.Title + (e.Inferred ? "  (inferred)" : ""), "ev-title");
                row.Add(title);
                row.tooltip = (e.Detail ?? "") + (e.Inferred ? "\nInferred because the replay has no explicit Clinician_* fields." : "");
                var ev = e;
                row.RegisterCallback<ClickEvent>(_ => { _pinnedFrame = ev.Frame; _seek(ev.Frame); });
                _scroll.Add(row);
                _rows.Add((e, row));
            }
            ApplyFilter();
        }

        /// <summary>Pin the inspector to a minute clicked in the thermal chart.</summary>
        public void Inspect(int frame)
        {
            _pinnedFrame = frame;
            _lastInspected = -1;
            RenderInspector(frame, true);
        }

        private void ApplyFilter()
        {
            foreach (var (ev, row) in _rows) UiUtil.Show(row, (ev.Category & _mask) != 0);
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            int past = _s.Events.CountUpTo(frame);
            if (past != _lastPast)
            {
                for (int i = 0; i < _rows.Count; i++) _rows[i].row.EnableInClassList("ev-future", i >= past);
                if (past > 0 && past <= _rows.Count && UiUtil.IsShown(_rows[past - 1].row)) _scroll.ScrollTo(_rows[past - 1].row);
                _lastPast = past;
            }
            RenderInspector(_pinnedFrame >= 0 ? _pinnedFrame : frame, _pinnedFrame >= 0);
        }

        private void RenderInspector(int frame, bool pinned)
        {
            var t = _s.Table;
            var f = _s.F;
            int mf = t.MinuteStartFrames[t.FrameMinute[frame]];
            if (mf == _lastInspected && pinned == _lastPinned) return; // only rebuild when the twin update changes
            _lastInspected = mf;
            _lastPinned = pinned;
            _inspector.Clear();
            var head = UiUtil.Box("row");
            head.Add(UiUtil.Label(pinned ? "SELECTED POINT" : "CURRENT TWIN UPDATE", "panel-title"));
            head.Add(UiUtil.Box("spacer"));
            if (pinned) head.Add(UiUtil.Button("follow replay", () => { _pinnedFrame = -1; _lastInspected = -1; }, "btn-ghost"));
            _inspector.Add(head);
            double po = t.Get(f.POutlier, mf), pl = t.Get(f.PLevelShift, mf);
            string type = "none flagged";
            if (!double.IsNaN(po) && po >= _s.Display.FlagOutlier) type = "Possible artefact (model probability)";
            if (!double.IsNaN(pl) && pl >= _s.Display.FlagLevelShift) type = "Possible level shift (model probability)";
            _inspector.Add(UiUtil.KeyValue("timestamp", Fmt.Time(t.T[mf]) + "  (twin update)"));
            _inspector.Add(UiUtil.KeyValue("event type", type));
            _inspector.Add(UiUtil.KeyValue("P(artefact)", Fmt.Probability(po) + "   display flag ≥ " + Fmt.Probability(_s.Display.FlagOutlier)));
            _inspector.Add(UiUtil.KeyValue("P(level shift)", Fmt.Probability(pl) + "   display flag ≥ " + Fmt.Probability(_s.Display.FlagLevelShift)));
            _inspector.Add(UiUtil.KeyValue("observation", t.GetBool(f.ObsMissing, mf) ? "missing (no value)" : Fmt.Value(t.Get(f.TObs, mf), f.TObs)));
            _inspector.Add(UiUtil.KeyValue("estimated state", Fmt.Value(t.Get(f.TEst, mf), f.TEst) + " ± " + Fmt.Value(t.Get(f.TEstSd, mf), f.TEstSd)));
            _inspector.Add(UiUtil.KeyValue("twin validity", _s.Enums.NameOf(EnumNames.TwinValid, t.GetInt(f.TwinValid, mf))));
            var tag = _s.Tag("twin", mf);
            _inspector.Add(UiUtil.KeyValue("model source", tag + " — " + ProvenanceRules.Meaning("twin", tag, _s, mf)));
        }

        public void Unbind()
        {
            _s = null;
            _scroll.Clear();
            _rows.Clear();
            _inspector.Clear();
        }
    }
}
