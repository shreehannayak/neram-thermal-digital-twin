using System;
using System.Collections.Generic;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Whole-replay timeline: one coloured segment per controller-state run (exact change frames from the replay),
    /// Twin_Valid lane, event ticks by category and the current-frame cursor. Click or drag to scrub.
    /// </summary>
    public sealed class TimelineStripElement : VisualElement
    {
        private struct Run { public double T0, T1; public Color C; }

        private ReplaySession _s;
        private readonly List<Run> _states = new List<Run>();
        private readonly List<Run> _twin = new List<Run>();
        private int _frame;
        private bool _dragging;
        private readonly Label _tip;

        /// <summary>Fraction 0..1 requested by the user (click / drag).</summary>
        public event Action<double> Scrub;

        private static readonly Color Bg = new Color32(15, 19, 25, 255);
        private static readonly Color Lane = new Color32(23, 28, 36, 255);
        private static readonly Color Cursor = new Color32(226, 232, 240, 255);
        private static readonly Color TickSafety = new Color32(239, 68, 68, 255);
        private static readonly Color TickFault = new Color32(251, 146, 60, 255);
        private static readonly Color TickClin = new Color32(56, 189, 248, 255);
        private static readonly Color TickTwin = new Color32(234, 179, 8, 255);
        private static readonly Color TickFlag = new Color32(148, 163, 184, 255);
        private static readonly Color TwinValid = new Color32(30, 64, 110, 255);
        private static readonly Color TwinInit = new Color32(51, 65, 85, 255);
        private static readonly Color TwinDegraded = new Color32(113, 63, 18, 255);

        public TimelineStripElement()
        {
            generateVisualContent += Draw;
            RegisterCallback<PointerDownEvent>(OnDown);
            RegisterCallback<PointerMoveEvent>(OnMove);
            RegisterCallback<PointerUpEvent>(OnUp);
            RegisterCallback<PointerLeaveEvent>(_ => UiUtil.Show(_tip, false));
            RegisterCallback<GeometryChangedEvent>(_ => MarkDirtyRepaint());
            _tip = UiUtil.Label("", "tooltip", "hidden");
            _tip.pickingMode = PickingMode.Ignore;
            Add(_tip);
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            _states.Clear();
            _twin.Clear();
            var t = s.Table;
            int start = 0;
            for (int f = 1; f <= t.FrameCount; f++)
            {
                if (f == t.FrameCount || t.GetInt(s.F.State, f) != t.GetInt(s.F.State, start))
                {
                    var name = s.Enums.NameOf(EnumNames.ControllerState, t.GetInt(s.F.State, start));
                    _states.Add(new Run { T0 = t.T[start], T1 = f < t.FrameCount ? t.T[f] : t.EndTime, C = UiUtil.StateColor(name) });
                    start = f;
                }
            }
            start = 0;
            for (int f = 1; f <= t.FrameCount; f++)
            {
                if (f == t.FrameCount || t.GetInt(s.F.TwinValid, f) != t.GetInt(s.F.TwinValid, start))
                {
                    int tv = t.GetInt(s.F.TwinValid, start);
                    var c = tv == s.TvValid ? TwinValid : tv == s.TvDegraded ? TwinDegraded : TwinInit;
                    _twin.Add(new Run { T0 = t.T[start], T1 = f < t.FrameCount ? t.T[f] : t.EndTime, C = c });
                    start = f;
                }
            }
            MarkDirtyRepaint();
        }

        public void Unbind()
        {
            _s = null;
            _states.Clear();
            _twin.Clear();
            MarkDirtyRepaint();
        }

        public void SetFrame(int frame)
        {
            _frame = frame;
            MarkDirtyRepaint();
        }

        private float X(double t)
        {
            var r = contentRect;
            if (_s == null || _s.Table.Duration <= 0) return 0;
            return (float)((t - _s.Table.StartTime) / _s.Table.Duration) * r.width;
        }

        private void Draw(MeshGenerationContext mgc)
        {
            var p = mgc.painter2D;
            var r = contentRect;
            Fill(p, 0, 0, r.width, r.height, Bg);
            if (_s == null) return;
            float stateTop = 16, stateH = 22, twinTop = 41, twinH = 5;
            Fill(p, 0, stateTop, r.width, stateH, Lane);
            foreach (var run in _states) Fill(p, X(run.T0), stateTop, Math.Max(1, X(run.T1) - X(run.T0)), stateH, run.C);
            foreach (var run in _twin) Fill(p, X(run.T0), twinTop, Math.Max(1, X(run.T1) - X(run.T0)), twinH, run.C);
            foreach (var e in _s.Events.All)
            {
                Color c;
                float y0 = 2, h = 10;
                if ((e.Category & EventCategory.Safety) != 0) c = TickSafety;
                else if ((e.Category & EventCategory.Fault) != 0) c = TickFault;
                else if ((e.Category & EventCategory.Clinician) != 0) c = TickClin;
                else if ((e.Category & EventCategory.Twin) != 0) c = TickTwin;
                else if ((e.Category & EventCategory.Flag) != 0) { c = TickFlag; y0 = 5; h = 7; }
                else continue;
                Fill(p, X(e.T) - 1, y0, 2, h, c);
            }
            var cx = X(_s.Table.T[_frame]);
            Fill(p, cx - 1, 0, 2, r.height, Cursor);
            p.fillColor = Cursor;
            p.BeginPath();
            p.MoveTo(new Vector2(cx - 5, 0));
            p.LineTo(new Vector2(cx + 5, 0));
            p.LineTo(new Vector2(cx, 6));
            p.ClosePath();
            p.Fill();
        }

        private static void Fill(Painter2D p, float x, float y, float w, float h, Color c)
        {
            p.fillColor = c;
            p.BeginPath();
            p.MoveTo(new Vector2(x, y));
            p.LineTo(new Vector2(x + w, y));
            p.LineTo(new Vector2(x + w, y + h));
            p.LineTo(new Vector2(x, y + h));
            p.ClosePath();
            p.Fill();
        }

        private double FractionAt(float x) => Math.Max(0, Math.Min(1, x / Math.Max(1, contentRect.width)));

        private void OnDown(PointerDownEvent e)
        {
            if (_s == null || e.button != 0) return;
            _dragging = true;
            this.CapturePointer(e.pointerId);
            Scrub?.Invoke(FractionAt(e.localPosition.x));
        }

        private void OnMove(PointerMoveEvent e)
        {
            if (_s == null) return;
            if (_dragging) Scrub?.Invoke(FractionAt(e.localPosition.x));
            var t = _s.Table.StartTime + FractionAt(e.localPosition.x) * _s.Table.Duration;
            int f = _s.Table.FrameAtTime(t);
            string near = null;
            double best = double.MaxValue;
            foreach (var ev in _s.Events.All)
            {
                var d = Math.Abs(X(ev.T) - e.localPosition.x);
                if (d < 4 && d < best) { best = d; near = ev.Title; }
            }
            _tip.text = Fmt.Time(t) + "  " + _s.Enums.NameOf(EnumNames.ControllerState, _s.Table.GetInt(_s.F.State, f)) + (near != null ? "\n" + near : "");
            UiUtil.Show(_tip, true);
            _tip.style.left = Mathf.Clamp(e.localPosition.x + 10, 0, contentRect.width - 220);
            _tip.style.top = -44;
        }

        private void OnUp(PointerUpEvent e)
        {
            if (!_dragging) return;
            _dragging = false;
            this.ReleasePointer(e.pointerId);
        }
    }
}
