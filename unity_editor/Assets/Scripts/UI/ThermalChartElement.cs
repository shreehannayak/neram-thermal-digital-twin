using System;
using System.Collections.Generic;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Rolling thermal chart (Painter2D): 60 min of history left of "now", the forecast region right of it.
    /// Drawing rules (scientific boundaries):
    ///  - T_obs: one dot per twin update (minute), never connected; missing minutes are hollow markers on a strip,
    ///    never interpolated.
    ///  - T_est: line between consecutive minute estimates, broken wherever T_est is null; optional +/-1 SD band.
    ///  - Forecast: drawn only when ForecastView.Visible; intervals at +20/+30/+60 only (dashed guides are labelled as such).
    ///  - Comparison (optional): T_plant and the derived T_plant - dT_heat, labelled SIMULATED / ASSUMED.
    ///  - Thresholds: drawn only when established or a labelled placeholder exists; otherwise "TBD" text, no line.
    /// All values are read from the replay; nothing is computed except screen coordinates and the display subtraction above.
    /// </summary>
    public sealed class ThermalChartElement : VisualElement
    {
        private static readonly CustomStyleProperty<Color> CBg = new CustomStyleProperty<Color>("--chart-bg");
        private static readonly CustomStyleProperty<Color> CGrid = new CustomStyleProperty<Color>("--chart-grid");
        private static readonly CustomStyleProperty<Color> CAxis = new CustomStyleProperty<Color>("--chart-axis");
        private static readonly CustomStyleProperty<Color> CObs = new CustomStyleProperty<Color>("--chart-obs");
        private static readonly CustomStyleProperty<Color> CObsFlag = new CustomStyleProperty<Color>("--chart-obs-flag");
        private static readonly CustomStyleProperty<Color> CEst = new CustomStyleProperty<Color>("--chart-est");
        private static readonly CustomStyleProperty<Color> CBand = new CustomStyleProperty<Color>("--chart-band");
        private static readonly CustomStyleProperty<Color> CFc = new CustomStyleProperty<Color>("--chart-fc");
        private static readonly CustomStyleProperty<Color> CFc80 = new CustomStyleProperty<Color>("--chart-fc-80");
        private static readonly CustomStyleProperty<Color> CFc95 = new CustomStyleProperty<Color>("--chart-fc-95");
        private static readonly CustomStyleProperty<Color> CFuture = new CustomStyleProperty<Color>("--chart-future");
        private static readonly CustomStyleProperty<Color> CHypo = new CustomStyleProperty<Color>("--chart-hypo");
        private static readonly CustomStyleProperty<Color> CTarget = new CustomStyleProperty<Color>("--chart-target");
        private static readonly CustomStyleProperty<Color> CPlant = new CustomStyleProperty<Color>("--chart-plant");
        private static readonly CustomStyleProperty<Color> CNoWarm = new CustomStyleProperty<Color>("--chart-nowarm");
        private static readonly CustomStyleProperty<Color> CNow = new CustomStyleProperty<Color>("--chart-now");
        private static readonly CustomStyleProperty<Color> CMissing = new CustomStyleProperty<Color>("--chart-missing");
        private static readonly CustomStyleProperty<Color> CShift = new CustomStyleProperty<Color>("--chart-shift");

        // Style-resolved colours (fallbacks mirror neram.uss).
        private Color _bg = new Color32(15, 19, 25, 255), _grid = new Color32(33, 39, 49, 255), _axis = new Color32(70, 80, 95, 255),
            _obs = new Color32(230, 234, 240, 255), _obsFlag = new Color32(251, 146, 60, 255), _est = new Color32(96, 165, 250, 255),
            _band = new Color(0.376f, 0.647f, 0.98f, 0.2f), _fcColor = new Color32(167, 139, 250, 255), _fc80 = new Color(0.655f, 0.545f, 0.98f, 0.85f),
            _fc95 = new Color(0.655f, 0.545f, 0.98f, 0.45f), _future = new Color(0.655f, 0.545f, 0.98f, 0.05f), _hypo = new Color32(248, 113, 113, 255),
            _target = new Color32(52, 211, 153, 255), _plant = new Color32(251, 191, 36, 255), _noWarm = new Color32(148, 163, 184, 255),
            _now = new Color32(226, 232, 240, 255), _missing = new Color32(107, 118, 132, 255), _shift = new Color32(236, 72, 153, 255);

        public bool ShowBand = true;
        public bool ShowFlags = true;
        public bool ShowCompare;
        public bool AutoScale;

        /// <summary>(minute start frame) when the user clicks a history point.</summary>
        public event Action<int> PointClicked;

        private ReplaySession _s;
        private int _frame;
        private ForecastView _fc;
        private double _fixedMin = 34, _fixedMax = 38, _yMin = 34, _yMax = 38;
        private double _tHypo = double.NaN, _tTarget = double.NaN;
        private string _hypoText, _targetText;
        private readonly VisualElement _overlay;
        private readonly Label _tooltip;
        private readonly List<Label> _pool = new List<Label>();
        private int _used;
        private readonly List<Vector2> _upper = new List<Vector2>(128);
        private readonly List<Vector2> _lower = new List<Vector2>(128);
        private Rect _plot;
        private bool _hasPlant;

        private const float PadRight = 10;
        private float PadLeft => 44 * _textScale;
        private float PadTop => 18 * _textScale;
        private float PadBottom => 20 * _textScale;
        private float _textScale = 1f;

        /// <summary>Label scale (v4: 1 on the dashboard, 1.3 on the MONITOR screen, matching the larger label font in
        /// neram.uss). Paddings, tick spacing and caption rows grow with it so labels never overlap the plot.</summary>
        public float TextScale
        {
            get => _textScale;
            set { if (Mathf.Approximately(_textScale, value)) return; _textScale = value; Relayout(); }
        }
        private const float MissingStripHeight = 8;

        public ThermalChartElement()
        {
            AddToClassList("chart");
            generateVisualContent += Draw;
            RegisterCallback<CustomStyleResolvedEvent>(OnStyles);
            RegisterCallback<GeometryChangedEvent>(_ => Relayout());
            RegisterCallback<PointerMoveEvent>(OnMove);
            RegisterCallback<PointerLeaveEvent>(_ => UiUtil.Show(_tooltip, false));
            RegisterCallback<PointerDownEvent>(OnDown);
            _overlay = new VisualElement { pickingMode = PickingMode.Ignore };
            _overlay.AddToClassList("chart-overlay");
            Add(_overlay);
            _tooltip = UiUtil.Label("", "tooltip", "hidden");
            _tooltip.pickingMode = PickingMode.Ignore;
            Add(_tooltip);
        }

        private void OnStyles(CustomStyleResolvedEvent e)
        {
            var cs = e.customStyle;
            cs.TryGetValue(CBg, out _bg); cs.TryGetValue(CGrid, out _grid); cs.TryGetValue(CAxis, out _axis);
            cs.TryGetValue(CObs, out _obs); cs.TryGetValue(CObsFlag, out _obsFlag); cs.TryGetValue(CEst, out _est);
            cs.TryGetValue(CBand, out _band); cs.TryGetValue(CFc, out _fcColor); cs.TryGetValue(CFc80, out _fc80);
            cs.TryGetValue(CFc95, out _fc95); cs.TryGetValue(CFuture, out _future); cs.TryGetValue(CHypo, out _hypo);
            cs.TryGetValue(CTarget, out _target); cs.TryGetValue(CPlant, out _plant); cs.TryGetValue(CNoWarm, out _noWarm);
            cs.TryGetValue(CNow, out _now); cs.TryGetValue(CMissing, out _missing); cs.TryGetValue(CShift, out _shift);
            MarkDirtyRepaint();
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            _frame = 0;
            var thermal = ThermalRules.Compute(s, 0);
            _tHypo = thermal.THypo;
            _tTarget = thermal.TTarget;
            var hypo = s.THypo;
            var target = s.TTarget;
            _hypoText = double.IsNaN(_tHypo) ? "t_hypo not established" : "t_hypo " + Fmt.Number(_tHypo, 1) + " °C" + (hypo != null && hypo.IsPlaceholderInUse ? "  PLACEHOLDER (" + hypo.Status + ")" : "  (" + hypo?.Status + ")");
            _targetText = double.IsNaN(_tTarget) ? "t_target not established (" + (target?.Status ?? "TBD") + ")" : "t_target " + Fmt.Number(_tTarget, 1) + " °C" + (target != null && target.IsPlaceholderInUse ? "  PLACEHOLDER (" + target.Status + ")" : "  (" + target?.Status + ")");
            _hasPlant = false;
            var tp = s.Table.Column(s.F.TPlant);
            for (int i = 0; i < tp.Length; i++) if (!double.IsNaN(tp[i])) { _hasPlant = true; break; }
            ComputeFixedRange();
            Relayout();
        }

        public bool HasPlant => _hasPlant;

        public void Unbind()
        {
            _s = null;
            _fc = null;
            ClearLabels();
            MarkDirtyRepaint();
        }

        public void SetFrame(int frame, ForecastView fc)
        {
            _frame = frame;
            _fc = fc;
            Relayout();
        }

        private void ComputeFixedRange()
        {
            var t = _s.Table;
            double lo = double.PositiveInfinity, hi = double.NegativeInfinity;
            void Acc(double v) { if (!double.IsNaN(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } }
            foreach (var m in t.MinuteStartFrames)
            {
                Acc(t.Get(_s.F.TObs, m));
                var e = t.Get(_s.F.TEst, m);
                var sd = t.Get(_s.F.TEstSd, m);
                Acc(e);
                if (!double.IsNaN(e) && !double.IsNaN(sd)) { Acc(e - sd); Acc(e + sd); }
                for (int h = 0; h < 3; h++) { Acc(t.Get(_s.F.L95[h], m)); Acc(t.Get(_s.F.U95[h], m)); }
                Acc(t.Get(_s.F.TPlant, m));
            }
            Acc(_tHypo);
            Acc(_tTarget);
            if (double.IsInfinity(lo)) { lo = 35; hi = 37; }
            Pad(ref lo, ref hi);
            _fixedMin = lo;
            _fixedMax = hi;
        }

        private void Pad(ref double lo, ref double hi)
        {
            var d = _s?.Display;
            double pad = d != null ? d.YPadding : 0.3, span = d != null ? d.YMinSpan : 2.0;
            lo -= pad; hi += pad;
            if (hi - lo < span) { var c = (hi + lo) / 2; lo = c - span / 2; hi = c + span / 2; }
        }

        private double HistS => _s != null ? _s.Display.HistoryWindowS : 3600;
        private double FutS => _s != null ? _s.Display.ForecastWindowS : 3600;
        private double Now => _s != null ? _s.Table.T[_frame] : 0;
        private float X(double t) => _plot.xMin + (float)((t - (Now - HistS)) / (HistS + FutS)) * _plot.width;
        private float Y(double v) => _plot.yMax - (float)((v - _yMin) / (_yMax - _yMin)) * _plot.height;

        private void Relayout()
        {
            var r = contentRect;
            if (float.IsNaN(r.width) || r.width < 50 || r.height < 50) return;
            _plot = new Rect(PadLeft, PadTop, r.width - PadLeft - PadRight, r.height - PadTop - PadBottom - MissingStripHeight - 4);
            if (_s != null)
            {
                if (AutoScale) ComputeWindowRange(); else { _yMin = _fixedMin; _yMax = _fixedMax; }
                LayoutLabels();
            }
            MarkDirtyRepaint();
        }

        private void ComputeWindowRange()
        {
            var t = _s.Table;
            double lo = double.PositiveInfinity, hi = double.NegativeInfinity;
            int m0 = t.FrameMinute[t.FrameAtTime(Now - HistS)], m1 = t.FrameMinute[_frame];
            for (int m = m0; m <= m1; m++)
            {
                int f = t.MinuteStartFrames[m];
                foreach (var v in new[] { t.Get(_s.F.TObs, f), t.Get(_s.F.TEst, f) })
                    if (!double.IsNaN(v)) { lo = Math.Min(lo, v); hi = Math.Max(hi, v); }
            }
            if (_fc != null && _fc.Visible)
                foreach (var h in _fc.Horizons) { lo = Math.Min(lo, h.L95); hi = Math.Max(hi, h.U95); }
            if (!double.IsNaN(_tHypo)) { lo = Math.Min(lo, _tHypo); hi = Math.Max(hi, _tHypo); }
            if (double.IsInfinity(lo)) { _yMin = _fixedMin; _yMax = _fixedMax; return; }
            Pad(ref lo, ref hi);
            _yMin = lo; _yMax = hi;
        }

        // ------------------------------------------------------------ labels (outside the repaint pass)
        private void ClearLabels()
        {
            for (int i = 0; i < _used; i++) _pool[i].style.display = DisplayStyle.None;
            _used = 0;
        }

        private Label NextLabel(string text, float x, float y, string cls = "axis-label", bool alignRight = false)
        {
            if (_used == _pool.Count)
            {
                var nl = new Label { pickingMode = PickingMode.Ignore };
                _overlay.Add(nl);
                _pool.Add(nl);
            }
            var l = _pool[_used++];
            l.ClearClassList();
            l.AddToClassList(cls);
            l.style.display = DisplayStyle.Flex;
            l.text = text;
            l.style.left = alignRight ? (StyleLength)StyleKeyword.Auto : new StyleLength(x);
            l.style.right = alignRight ? new StyleLength(contentRect.width - x) : (StyleLength)StyleKeyword.Auto;
            l.style.top = y;
            return l;
        }

        private void LayoutLabels()
        {
            ClearLabels();
            // y ticks
            double step = NiceStep(_yMax - _yMin);
            // keep at least ~13 px between tick labels when the panel is short (verified in Unity: labels overlapped)
            double span = Math.Max(1e-6, _yMax - _yMin);
            while (step < span && _plot.height * step / span < 13 * _textScale) step *= 2;
            for (double v = Math.Ceiling(_yMin / step) * step; v <= _yMax + 1e-9; v += step)
                NextLabel(Fmt.Number(v, step < 0.1 ? 2 : 1), PadLeft - 4, Y(v) - 7 * _textScale, "axis-label", true);
            // x ticks every 10 min relative to now; on a narrow plot only every 20 or 30 min, so the labels never run
            // into each other (seen in FULL ANALYSIS at 1366×768)
            float per10 = Math.Abs(X(Now + 600) - X(Now));
            int every = per10 >= 52f * _textScale ? 1 : per10 >= 26f * _textScale ? 2 : 3;
            for (int k = -6; k <= 6; k++)
            {
                if (k % every != 0) continue;
                var t = Now + k * 600;
                var txt = k == 0 ? "now" : (k > 0 ? "+" : "−") + Math.Abs(k * 10) + " min";
                NextLabel(txt, X(t) - 16 * _textScale, _plot.yMax + MissingStripHeight + 6);
            }
            NextLabel("missing", 2, _plot.yMax + 1);
            // thresholds
            // Threshold captions: one row each, kept inside the plot and never on top of each other or of the
            // "history (60 min)" caption (row 0). A short plot gets a single combined caption instead.
            float row = 12f * _textScale;
            float top = _plot.yMin + 1, bottom = _plot.yMax - row;
            if (bottom - top < 2 * row)
                NextLabel(_hypoText + "   ·   " + _targetText, _plot.xMin + 4, Mathf.Max(top, bottom), "chart-note-dim");
            else
            {
                float yHypo = !double.IsNaN(_tHypo) ? Y(_tHypo) + 1 : top;
                float yTarget = !double.IsNaN(_tTarget) ? Y(_tTarget) - row - 2 : top + row;
                yHypo = Mathf.Clamp(yHypo, top, bottom);
                yTarget = Mathf.Clamp(yTarget, top, bottom);
                if (Mathf.Abs(yHypo - yTarget) < row)
                {
                    if (yTarget <= yHypo) yTarget = Mathf.Max(top, yHypo - row); else yTarget = Mathf.Min(bottom, yHypo + row);
                    if (Mathf.Abs(yHypo - yTarget) < row) yHypo = Mathf.Min(bottom, yTarget + row);
                }
                NextLabel(_hypoText, _plot.xMin + 4, yHypo, "chart-note");
                NextLabel(_targetText, _plot.xMin + 4, yTarget, "chart-note");
            }
            // forecast region title
            var fx = X(Now) + 6;
            if (_fc != null)
            {
                if (_fc.Visible) NextLabel(_fc.Label + "  ·  80/95 % intervals at +20/+30/+60 min only", fx, 1, "chart-note");
                else NextLabel(_fc.HiddenMessage ?? "Forecast hidden", fx, _plot.center.y - 8 * _textScale, "chart-note");
            }
            NextLabel("history (60 min)", _plot.xMin + 4, 1, "chart-note-dim");
        }

        private static double NiceStep(double span)
        {
            if (span <= 1.2) return 0.2;
            if (span <= 3) return 0.5;
            if (span <= 6) return 1;
            return 2;
        }

        // ------------------------------------------------------------ drawing
        private void Draw(MeshGenerationContext mgc)
        {
            var p = mgc.painter2D;
            var r = contentRect;
            FillRect(p, new Rect(0, 0, r.width, r.height), _bg);
            if (_s == null || _plot.width <= 0) return;
            var t = _s.Table;
            var f = _s.F;
            float xNow = X(Now);

            // future region
            FillRect(p, new Rect(xNow, _plot.yMin, _plot.xMax - xNow, _plot.height), _future);
            // grid
            p.lineWidth = 1;
            double step = NiceStep(_yMax - _yMin);
            for (double v = Math.Ceiling(_yMin / step) * step; v <= _yMax + 1e-9; v += step) Line(p, _plot.xMin, Y(v), _plot.xMax, Y(v), _grid, 1);
            for (int k = -6; k <= 6; k++) Line(p, X(Now + k * 600), _plot.yMin, X(Now + k * 600), _plot.yMax, _grid, 1);
            // missing strip baseline
            Line(p, _plot.xMin, _plot.yMax + MissingStripHeight, _plot.xMax, _plot.yMax + MissingStripHeight, _grid, 1);

            // thresholds
            if (!double.IsNaN(_tHypo)) Dashed(p, _plot.xMin, _plot.xMax, Y(_tHypo), _hypo, 1.2f, 6, 4);
            if (!double.IsNaN(_tTarget)) Dashed(p, _plot.xMin, _plot.xMax, Y(_tTarget), _target, 1.2f, 6, 4);

            double t0 = Now - HistS;
            int fStart = t.FrameAtTime(t0);
            int m0 = t.FrameMinute[fStart], m1 = t.FrameMinute[_frame];

            // state transitions within window (vertical markers coloured by the new state)
            foreach (var ev in _s.Events.All)
            {
                if (ev.Frame > _frame) break;
                if (ev.Kind != EventKind.StateChange || ev.T < t0) continue;
                float x = X(ev.T);
                var st = _s.Enums.NameOf(EnumNames.ControllerState, t.GetInt(f.State, ev.Frame));
                Line(p, x, _plot.yMin, x, _plot.yMax, new Color(1, 1, 1, 0.08f), 1);
                FillRect(p, new Rect(x - 1.5f, _plot.yMin - 6, 3, 6), UiUtil.StateColor(st));
            }

            // estimate band
            if (ShowBand)
            {
                _upper.Clear(); _lower.Clear();
                for (int m = m0; m <= m1 + 1; m++)
                {
                    bool ok = m <= m1;
                    double e = 0, sd = 0, tm = 0;
                    if (ok)
                    {
                        int fr = t.MinuteStartFrames[m];
                        tm = t.T[fr]; e = t.Get(f.TEst, fr); sd = t.Get(f.TEstSd, fr);
                        ok = !double.IsNaN(e) && !double.IsNaN(sd) && tm >= t0;
                    }
                    if (ok) { _upper.Add(new Vector2(X(tm), Y(e + sd))); _lower.Add(new Vector2(X(tm), Y(e - sd))); }
                    else if (_upper.Count > 0) { Band(p); _upper.Clear(); _lower.Clear(); }
                }
            }

            // comparison: simulated plant and derived no-warming trajectory
            if (ShowCompare && _hasPlant)
            {
                int stride = Math.Max(1, (_frame - fStart) / 360);
                DrawSeries(p, fStart, _frame, stride, fr => t.Get(f.TPlant, fr), _plant, 1.4f, true);
                DrawSeries(p, fStart, _frame, stride, fr => t.Get(f.TPlant, fr) - t.Get(f.DTHeat, fr), _noWarm, 1.2f, true);
            }

            // estimate line (broken at nulls; drawn between minute estimates)
            p.strokeColor = _est;
            p.lineWidth = 2f;
            p.lineJoin = LineJoin.Round;
            bool pen = false;
            p.BeginPath();
            for (int m = m0; m <= m1; m++)
            {
                int fr = t.MinuteStartFrames[m];
                double e = t.Get(f.TEst, fr);
                if (double.IsNaN(e) || t.T[fr] < t0) { pen = false; continue; }
                var pt = new Vector2(X(t.T[fr]), Y(e));
                if (!pen) { p.MoveTo(pt); pen = true; } else p.LineTo(pt);
            }
            p.Stroke();

            // observations, missing markers, flags
            double thrO = _s.Display.FlagOutlier, thrL = _s.Display.FlagLevelShift;
            for (int m = m0; m <= m1; m++)
            {
                int fr = t.MinuteStartFrames[m];
                if (t.T[fr] < t0) continue;
                float x = X(t.T[fr]);
                bool missing = t.GetBool(f.ObsMissing, fr);
                if (missing)
                {
                    StrokeRect(p, new Rect(x - 2.5f, _plot.yMax + 1.5f, 5, 5), _missing, 1);
                }
                else
                {
                    float y = Y(t.Get(f.TObs, fr));
                    double po = t.Get(f.POutlier, fr);
                    bool flagged = ShowFlags && !double.IsNaN(po) && po >= thrO;
                    Circle(p, x, y, 2.4f, flagged ? _obsFlag : _obs, true);
                    if (flagged) Circle(p, x, y, 5.5f, _obsFlag, false);
                }
                if (ShowFlags)
                {
                    double pl = t.Get(f.PLevelShift, fr);
                    if (!double.IsNaN(pl) && pl >= thrL) Triangle(p, x, _plot.yMin + 1, 5, _shift);
                }
            }

            // forecast
            if (_fc != null && _fc.Visible && !double.IsNaN(_fc.NowEstimate))
            {
                var origin = new Vector2(xNow, Y(_fc.NowEstimate));
                foreach (var h in _fc.Horizons)
                {
                    float x = X(Now + h.Minutes * 60);
                    DashedLine(p, origin, new Vector2(x, Y(h.Mean)), _fc95, 1f, 4, 4);
                    Line(p, x, Y(h.L95), x, Y(h.U95), _fc95, 1.5f);
                    Line(p, x - 4, Y(h.L95), x + 4, Y(h.L95), _fc95, 1.5f);
                    Line(p, x - 4, Y(h.U95), x + 4, Y(h.U95), _fc95, 1.5f);
                    Line(p, x, Y(h.L80), x, Y(h.U80), _fc80, h.InformationOnly ? 4f : 6f);
                    Circle(p, x, Y(h.Mean), 3.2f, _fcColor, true);
                    Circle(p, x, Y(h.Mean), 1.4f, _bg, true);
                }
            }

            // now cursor and axis
            Line(p, xNow, _plot.yMin - 8, xNow, _plot.yMax + MissingStripHeight, _now, 1.2f);
            Line(p, _plot.xMin, _plot.yMin, _plot.xMin, _plot.yMax, _axis, 1);
        }

        private void DrawSeries(Painter2D p, int from, int to, int stride, Func<int, double> value, Color c, float w, bool dashed)
        {
            var t = _s.Table;
            Vector2? prev = null;
            p.strokeColor = c;
            p.lineWidth = w;
            p.BeginPath();
            int k = 0;
            for (int fr = from; fr <= to; fr += stride)
            {
                double v = value(fr);
                if (double.IsNaN(v)) { prev = null; continue; }
                var pt = new Vector2(X(t.T[fr]), Y(v));
                if (prev == null) p.MoveTo(pt);
                else if (!dashed || (k++ % 2 == 0)) p.LineTo(pt);
                else p.MoveTo(pt);
                prev = pt;
            }
            p.Stroke();
        }

        private void Band(Painter2D p)
        {
            if (_upper.Count < 2) return;
            p.fillColor = _band;
            p.BeginPath();
            p.MoveTo(_upper[0]);
            for (int i = 1; i < _upper.Count; i++) p.LineTo(_upper[i]);
            for (int i = _lower.Count - 1; i >= 0; i--) p.LineTo(_lower[i]);
            p.ClosePath();
            p.Fill();
        }

        private static void FillRect(Painter2D p, Rect r, Color c)
        {
            p.fillColor = c;
            p.BeginPath();
            p.MoveTo(new Vector2(r.xMin, r.yMin));
            p.LineTo(new Vector2(r.xMax, r.yMin));
            p.LineTo(new Vector2(r.xMax, r.yMax));
            p.LineTo(new Vector2(r.xMin, r.yMax));
            p.ClosePath();
            p.Fill();
        }

        private static void StrokeRect(Painter2D p, Rect r, Color c, float w)
        {
            p.strokeColor = c;
            p.lineWidth = w;
            p.BeginPath();
            p.MoveTo(new Vector2(r.xMin, r.yMin));
            p.LineTo(new Vector2(r.xMax, r.yMin));
            p.LineTo(new Vector2(r.xMax, r.yMax));
            p.LineTo(new Vector2(r.xMin, r.yMax));
            p.ClosePath();
            p.Stroke();
        }

        private static void Line(Painter2D p, float x0, float y0, float x1, float y1, Color c, float w)
        {
            p.strokeColor = c;
            p.lineWidth = w;
            p.BeginPath();
            p.MoveTo(new Vector2(x0, y0));
            p.LineTo(new Vector2(x1, y1));
            p.Stroke();
        }

        private static void Dashed(Painter2D p, float x0, float x1, float y, Color c, float w, float dash, float gap)
        {
            p.strokeColor = c;
            p.lineWidth = w;
            p.BeginPath();
            for (float x = x0; x < x1; x += dash + gap)
            {
                p.MoveTo(new Vector2(x, y));
                p.LineTo(new Vector2(Math.Min(x + dash, x1), y));
            }
            p.Stroke();
        }

        private static void DashedLine(Painter2D p, Vector2 a, Vector2 b, Color c, float w, float dash, float gap)
        {
            var d = b - a;
            float len = d.magnitude;
            if (len < 1) return;
            var u = d / len;
            p.strokeColor = c;
            p.lineWidth = w;
            p.BeginPath();
            for (float s = 0; s < len; s += dash + gap)
            {
                p.MoveTo(a + u * s);
                p.LineTo(a + u * Math.Min(s + dash, len));
            }
            p.Stroke();
        }

        private static void Circle(Painter2D p, float cx, float cy, float rad, Color c, bool fill)
        {
            const int n = 14;
            p.BeginPath();
            for (int i = 0; i <= n; i++)
            {
                float a = i * Mathf.PI * 2 / n;
                var pt = new Vector2(cx + Mathf.Cos(a) * rad, cy + Mathf.Sin(a) * rad);
                if (i == 0) p.MoveTo(pt); else p.LineTo(pt);
            }
            p.ClosePath();
            if (fill) { p.fillColor = c; p.Fill(); }
            else { p.strokeColor = c; p.lineWidth = 1.2f; p.Stroke(); }
        }

        private static void Triangle(Painter2D p, float x, float y, float s, Color c)
        {
            p.fillColor = c;
            p.BeginPath();
            p.MoveTo(new Vector2(x - s, y));
            p.LineTo(new Vector2(x + s, y));
            p.LineTo(new Vector2(x, y + s * 1.4f));
            p.ClosePath();
            p.Fill();
        }

        // ------------------------------------------------------------ interaction
        private double TimeAt(float x) => (Now - HistS) + (x - _plot.xMin) / _plot.width * (HistS + FutS);

        private int MinuteFrameAt(float x)
        {
            var t = _s.Table;
            double tm = Math.Min(TimeAt(x), Now);
            int fr = t.FrameAtTime(tm);
            return t.MinuteStartFrames[t.FrameMinute[fr]];
        }

        private void OnMove(PointerMoveEvent e)
        {
            if (_s == null || _plot.width <= 0) return;
            var lp = (Vector2)e.localPosition;
            if (!_plot.Contains(lp)) { UiUtil.Show(_tooltip, false); return; }
            string text;
            if (TimeAt(lp.x) > Now)
            {
                if (_fc == null || !_fc.Visible) { text = _fc?.HiddenMessage ?? "No forecast"; }
                else
                {
                    var best = _fc.Horizons[0];
                    foreach (var h in _fc.Horizons)
                        if (Math.Abs(X(Now + h.Minutes * 60) - lp.x) < Math.Abs(X(Now + best.Minutes * 60) - lp.x)) best = h;
                    text = _fc.Label + " +" + best.Minutes + " min\nmean " + Fmt.Number(best.Mean, 2) + " °C\n80 % [" + Fmt.Number(best.L80, 2) + ", " + Fmt.Number(best.U80, 2) + "]\n95 % [" +
                           Fmt.Number(best.L95, 2) + ", " + Fmt.Number(best.U95, 2) + "]\nP(below t_hypo) " + Fmt.Probability(best.PBelow) + (best.InformationOnly ? "\n(+60 min: information only)" : "");
                }
            }
            else
            {
                int fr = MinuteFrameAt(lp.x);
                text = DescribeMinute(_s, fr);
            }
            _tooltip.text = text;
            UiUtil.Show(_tooltip, true);
            _tooltip.style.left = Math.Min(lp.x + 12, contentRect.width - 200);
            _tooltip.style.top = Math.Max(0, lp.y - 40);
        }

        private void OnDown(PointerDownEvent e)
        {
            if (_s == null || e.button != 0) return;
            var lp = (Vector2)e.localPosition;
            if (!_plot.Contains(lp) || TimeAt(lp.x) > Now) return;
            PointClicked?.Invoke(MinuteFrameAt(lp.x));
        }

        public static string DescribeMinute(ReplaySession s, int fr)
        {
            var t = s.Table;
            var f = s.F;
            var obs = t.GetBool(f.ObsMissing, fr) ? "missing" : Fmt.Number(t.Get(f.TObs, fr), 2) + " °C";
            return Fmt.Time(t.T[fr]) + "\nT_obs  " + obs +
                   "\nT_est  " + Fmt.Number(t.Get(f.TEst, fr), 2) + " ± " + Fmt.Number(t.Get(f.TEstSd, fr), 3) + " °C" +
                   "\nTwin   " + s.Enums.NameOf(EnumNames.TwinValid, t.GetInt(f.TwinValid, fr)) +
                   "\nP(artefact) " + Fmt.Probability(t.Get(f.POutlier, fr)) + "  P(level shift) " + Fmt.Probability(t.Get(f.PLevelShift, fr)) +
                   "\nState  " + s.Enums.NameOf(EnumNames.ControllerState, t.GetInt(f.State, fr));
        }
    }
}
