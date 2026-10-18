using System;
using System.Collections.Generic;
using System.Globalization;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Full-case time-series chart (Painter2D) used by the dashboard charts A and C.
    ///  - Line mode: each series is drawn as a polyline that BREAKS at every null (NaN) sample; gaps are never bridged
    ///    or interpolated. Optional grey shading marks frames where a "missing" mask is true.
    ///  - Lane mode: one horizontal lane per series (0..laneMax), drawn as a filled area; used for CH1-CH4 heating
    ///    commands so overlapping channels stay readable.
    /// The cursor (current replay frame) is a separate child element, so moving it does not redraw the data.
    /// Values come only from replay columns; the element computes nothing except screen coordinates and a per-pixel
    /// min/max reduction for drawing.
    /// </summary>
    public sealed class SeriesChartElement : VisualElement
    {
        public sealed class Series
        {
            public string Name;
            public double[] Values;
            public Color Color;
            public float Width = 1.6f;
        }

        public enum Mode { Lines, Lanes }

        public Mode ChartMode = Mode.Lines;
        public string Unit = "";
        public double LaneMax = 100;
        public double FixedMin = double.NaN, FixedMax = double.NaN;
        public double MinSpan = 1.0;
        public bool[] MissingMask;
        public string MissingLabel = "no observation";

        public event Action<double> Clicked; // replay time (s)

        private readonly List<Series> _series = new List<Series>();
        private double[] _t;
        private double _t0, _t1, _yMin = 0, _yMax = 1;
        private readonly VisualElement _cursor;
        private readonly Label _cursorLabel;
        private readonly List<Label> _labels = new List<Label>();
        private int _labelUsed;
        private Rect _plot;
        private const float PadR = 10, PadT = 8;
        private float PadL => 46 * _textScale;
        private float PadB => 18 * _textScale;
        private float _textScale = 1f;

        /// <summary>Label scale (v4: 1 on the dashboard, 1.3 on the MONITOR screen, matching the larger label font in
        /// neram.uss). Paddings and label offsets grow with it so labels never overlap the plot.</summary>
        public float TextScale
        {
            get => _textScale;
            set { if (Mathf.Approximately(_textScale, value)) return; _textScale = value; Relayout(); }
        }
        private static readonly Color Grid = new Color32(33, 41, 52, 255);
        private static readonly Color Axis = new Color32(70, 82, 98, 255);
        private static readonly Color MissingFill = new Color(0.42f, 0.46f, 0.52f, 0.16f);

        public SeriesChartElement()
        {
            AddToClassList("series-chart");
            generateVisualContent += Draw;
            _cursor = new VisualElement { pickingMode = PickingMode.Ignore };
            _cursor.AddToClassList("chart-cursor");
            Add(_cursor);
            _cursorLabel = new Label { pickingMode = PickingMode.Ignore };
            _cursorLabel.AddToClassList("chart-cursor-label");
            Add(_cursorLabel);
            RegisterCallback<GeometryChangedEvent>(_ => Relayout());
            RegisterCallback<PointerDownEvent>(e =>
            {
                if (_t == null || _plot.width <= 0) return;
                double x = Mathf.Clamp01((e.localPosition.x - _plot.xMin) / _plot.width);
                Clicked?.Invoke(_t0 + x * (_t1 - _t0));
                e.StopPropagation();
            });
        }

        public void SetData(double[] t, IList<Series> series)
        {
            _t = t;
            _series.Clear();
            if (series != null) _series.AddRange(series);
            if (_t != null && _t.Length > 0) { _t0 = _t[0]; _t1 = _t[_t.Length - 1]; if (_t1 <= _t0) _t1 = _t0 + 1; }
            ComputeRange();
            Relayout();
        }

        public void ClearData()
        {
            _t = null;
            _series.Clear();
            MissingMask = null;
            Relayout();
            _cursor.style.display = DisplayStyle.None;
            _cursorLabel.style.display = DisplayStyle.None;
        }

        private void ComputeRange()
        {
            if (ChartMode == Mode.Lanes) { _yMin = 0; _yMax = 1; return; }
            double lo = double.PositiveInfinity, hi = double.NegativeInfinity;
            foreach (var s in _series)
            {
                if (s.Values == null) continue;
                foreach (var v in s.Values)
                {
                    if (double.IsNaN(v)) continue;
                    if (v < lo) lo = v;
                    if (v > hi) hi = v;
                }
            }
            if (!double.IsNaN(FixedMin)) lo = FixedMin;
            if (!double.IsNaN(FixedMax)) hi = FixedMax;
            if (double.IsInfinity(lo) || double.IsInfinity(hi)) { lo = 0; hi = 1; }
            if (hi - lo < MinSpan) { double c = (hi + lo) / 2; lo = c - MinSpan / 2; hi = c + MinSpan / 2; }
            double pad = (hi - lo) * 0.08;
            _yMin = lo - pad;
            _yMax = hi + pad;
        }

        /// <summary>Move the cursor to replay time t (cheap: no data redraw).</summary>
        public void SetCursor(double t, string label)
        {
            if (_t == null || _plot.width <= 0) { _cursor.style.display = DisplayStyle.None; _cursorLabel.style.display = DisplayStyle.None; return; }
            float x = X(t);
            _cursor.style.display = DisplayStyle.Flex;
            _cursor.style.left = x - 1;
            _cursor.style.top = _plot.yMin;
            _cursor.style.height = _plot.height;
            _cursorLabel.style.display = string.IsNullOrEmpty(label) ? DisplayStyle.None : DisplayStyle.Flex;
            _cursorLabel.text = label ?? "";
            bool right = x > _plot.center.x;
            _cursorLabel.style.left = right ? new StyleLength(StyleKeyword.Auto) : new StyleLength(x + 4);
            _cursorLabel.style.right = right ? new StyleLength(contentRect.width - x + 4) : new StyleLength(StyleKeyword.Auto);
            _cursorLabel.style.top = _plot.yMin + 1;
        }

        private float X(double t) => _plot.xMin + (float)((t - _t0) / (_t1 - _t0)) * _plot.width;
        private float Y(double v) => _plot.yMax - (float)((v - _yMin) / (_yMax - _yMin)) * _plot.height;

        private Label NextLabel(string text, float x, float y, string cls, bool alignRight = false)
        {
            Label l;
            if (_labelUsed < _labels.Count) l = _labels[_labelUsed];
            else
            {
                l = new Label { pickingMode = PickingMode.Ignore };
                _labels.Add(l);
                Add(l);
            }
            _labelUsed++;
            if (l.userData is string prev && prev != cls) l.RemoveFromClassList(prev);
            l.AddToClassList(cls);
            l.userData = cls;
            if (l.text != text) l.text = text;
            l.style.display = DisplayStyle.Flex;
            l.style.position = Position.Absolute;
            if (alignRight) { l.style.left = StyleKeyword.Auto; l.style.right = contentRect.width - x; }
            else { l.style.right = StyleKeyword.Auto; l.style.left = x; }
            l.style.top = y;
            return l;
        }

        /// <summary>Plot rectangle + every text label. Runs OUTSIDE the repaint pass (UI Toolkit forbids changing the
        /// visual tree during generateVisualContent), then requests a repaint.</summary>
        private void Relayout()
        {
            var r = contentRect;
            if (float.IsNaN(r.width) || r.width <= 0) { MarkDirtyRepaint(); return; }
            _plot = new Rect(PadL, PadT, Mathf.Max(10, r.width - PadL - PadR), Mathf.Max(10, r.height - PadT - PadB));
            _labelUsed = 0;
            if (_t == null || _t.Length < 2)
            {
                NextLabel("no replay loaded", _plot.xMin + 6, _plot.center.y - 8 * _textScale, "chart-note");
            }
            else
            {
                if (MissingMask != null && MissingMask.Length == _t.Length)
                {
                    int i = 0, shown = 0;
                    while (i < _t.Length && shown < 12)
                    {
                        if (!MissingMask[i]) { i++; continue; }
                        int j = i;
                        while (j + 1 < _t.Length && MissingMask[j + 1]) j++;
                        float x0 = X(_t[i]), x1 = Mathf.Max(X(_t[j]), x0 + 1.5f);
                        if (x1 - x0 > 46) { NextLabel(MissingLabel, x0 + 3, _plot.yMax - 14 * _textScale, "chart-note-dim"); shown++; }
                        i = j + 1;
                    }
                }
                if (ChartMode == Mode.Lines)
                {
                    double step = NiceStep((_yMax - _yMin) / 4);
                    for (double v = Math.Ceiling(_yMin / step) * step; v <= _yMax + 1e-9; v += step)
                        NextLabel(Fmt.Number(v, step < 0.1 ? 2 : step < 1 ? 1 : 0) + (Unit.Length > 0 ? " " + Unit : ""), PadL - 4, Y(v) - 7 * _textScale, "axis-label", true);
                }
                else
                {
                    int n = Mathf.Max(1, _series.Count);
                    float laneH = _plot.height / n;
                    for (int k = 0; k < _series.Count; k++)
                        NextLabel(_series[k].Name, 4, _plot.yMin + k * laneH + laneH / 2 - 7 * _textScale, "lane-label");
                }
                double tStep = NiceTimeStep((_t1 - _t0) / 6);
                for (double tt = Math.Ceiling(_t0 / tStep) * tStep; tt <= _t1 + 1e-6; tt += tStep)
                    NextLabel(TimeLabel(tt - _t0), X(tt) - 14 * _textScale, _plot.yMax + 3, "axis-label");
            }
            for (int i = _labelUsed; i < _labels.Count; i++) _labels[i].style.display = DisplayStyle.None;
            MarkDirtyRepaint();
        }

        private void Draw(MeshGenerationContext mgc)
        {
            var r = contentRect;
            _plot = new Rect(PadL, PadT, Mathf.Max(10, r.width - PadL - PadR), Mathf.Max(10, r.height - PadT - PadB));
            var p = mgc.painter2D;
            p.lineJoin = LineJoin.Round;
            p.lineCap = LineCap.Round;
            if (_t == null || _t.Length < 2) return;
            // missing-observation shading
            if (MissingMask != null && MissingMask.Length == _t.Length)
            {
                p.fillColor = MissingFill;
                int i = 0;
                while (i < _t.Length)
                {
                    if (!MissingMask[i]) { i++; continue; }
                    int j = i;
                    while (j + 1 < _t.Length && MissingMask[j + 1]) j++;
                    float x0 = X(_t[i]), x1 = Mathf.Max(X(_t[j]), x0 + 1.5f);
                    p.BeginPath();
                    p.MoveTo(new Vector2(x0, _plot.yMin));
                    p.LineTo(new Vector2(x1, _plot.yMin));
                    p.LineTo(new Vector2(x1, _plot.yMax));
                    p.LineTo(new Vector2(x0, _plot.yMax));
                    p.ClosePath();
                    p.Fill();
                    i = j + 1;
                }
            }
            // grid + axes
            p.strokeColor = Grid;
            p.lineWidth = 1;
            if (ChartMode == Mode.Lines)
            {
                double step = NiceStep((_yMax - _yMin) / 4);
                for (double v = Math.Ceiling(_yMin / step) * step; v <= _yMax + 1e-9; v += step)
                {
                    float y = Y(v);
                    p.BeginPath(); p.MoveTo(new Vector2(_plot.xMin, y)); p.LineTo(new Vector2(_plot.xMax, y)); p.Stroke();
                }
            }
            double tStep = NiceTimeStep((_t1 - _t0) / 6);
            for (double tt = Math.Ceiling(_t0 / tStep) * tStep; tt <= _t1 + 1e-6; tt += tStep)
            {
                float x = X(tt);
                p.BeginPath(); p.MoveTo(new Vector2(x, _plot.yMin)); p.LineTo(new Vector2(x, _plot.yMax)); p.Stroke();
            }
            p.strokeColor = Axis;
            p.BeginPath(); p.MoveTo(new Vector2(_plot.xMin, _plot.yMin)); p.LineTo(new Vector2(_plot.xMin, _plot.yMax)); p.LineTo(new Vector2(_plot.xMax, _plot.yMax)); p.Stroke();

            if (ChartMode == Mode.Lines) DrawLines(p);
            else DrawLanes(p);
        }

        private void DrawLines(Painter2D p)
        {
            int cols = Mathf.Max(2, (int)_plot.width);
            foreach (var s in _series)
            {
                if (s.Values == null || s.Values.Length != _t.Length) continue;
                p.strokeColor = s.Color;
                p.lineWidth = s.Width;
                // per-pixel-column min/max; a column without any finite sample breaks the line (honest gaps)
                bool open = false;
                int k = 0;
                for (int c = 0; c < cols; c++)
                {
                    double tc1 = _t0 + (c + 1) / (double)cols * (_t1 - _t0);
                    double lo = double.PositiveInfinity, hi = double.NegativeInfinity;
                    bool anyNull = false;
                    while (k < _t.Length && _t[k] <= tc1)
                    {
                        var v = s.Values[k];
                        if (double.IsNaN(v)) anyNull = true;
                        else { if (v < lo) lo = v; if (v > hi) hi = v; }
                        k++;
                    }
                    if (double.IsInfinity(lo))
                    {
                        if (open) { p.Stroke(); open = false; }
                        continue;
                    }
                    float x = _plot.xMin + c + 0.5f;
                    if (!open) { p.BeginPath(); p.MoveTo(new Vector2(x, Y(lo))); open = true; }
                    else p.LineTo(new Vector2(x, Y(lo)));
                    if (hi > lo) p.LineTo(new Vector2(x, Y(hi)));
                    if (anyNull) { p.Stroke(); open = false; } // a null inside this column ends the segment here
                }
                if (open) p.Stroke();
            }
        }

        private void DrawLanes(Painter2D p)
        {
            int n = Mathf.Max(1, _series.Count);
            float laneH = _plot.height / n;
            int cols = Mathf.Max(2, (int)_plot.width);
            for (int i = 0; i < _series.Count; i++)
            {
                var s = _series[i];
                float top = _plot.yMin + i * laneH + 3;
                float bottom = _plot.yMin + (i + 1) * laneH - 3;
                p.strokeColor = Grid;
                p.lineWidth = 1;
                p.BeginPath(); p.MoveTo(new Vector2(_plot.xMin, bottom)); p.LineTo(new Vector2(_plot.xMax, bottom)); p.Stroke();
                if (s.Values == null || s.Values.Length != _t.Length) continue;
                var fill = s.Color;
                fill.a = 0.35f;
                int k = 0;
                var top_pts = new List<Vector2>();
                void FlushArea()
                {
                    if (top_pts.Count < 2) { top_pts.Clear(); return; }
                    p.fillColor = fill;
                    p.BeginPath();
                    p.MoveTo(new Vector2(top_pts[0].x, bottom));
                    foreach (var q in top_pts) p.LineTo(q);
                    p.LineTo(new Vector2(top_pts[top_pts.Count - 1].x, bottom));
                    p.ClosePath();
                    p.Fill();
                    p.strokeColor = s.Color;
                    p.lineWidth = 1.4f;
                    p.BeginPath();
                    p.MoveTo(top_pts[0]);
                    for (int q = 1; q < top_pts.Count; q++) p.LineTo(top_pts[q]);
                    p.Stroke();
                    top_pts.Clear();
                }
                for (int c = 0; c < cols; c++)
                {
                    double tc1 = _t0 + (c + 1) / (double)cols * (_t1 - _t0);
                    double hi = double.NegativeInfinity;
                    bool anyNull = false;
                    while (k < _t.Length && _t[k] <= tc1)
                    {
                        var v = s.Values[k];
                        if (double.IsNaN(v)) anyNull = true; else if (v > hi) hi = v;
                        k++;
                    }
                    if (double.IsInfinity(hi)) { FlushArea(); continue; }
                    float y = bottom - (float)(Math.Max(0, Math.Min(LaneMax, hi)) / LaneMax) * (bottom - top);
                    top_pts.Add(new Vector2(_plot.xMin + c + 0.5f, y));
                    if (anyNull) FlushArea();
                }
                FlushArea();
            }
        }

        private static double NiceStep(double raw)
        {
            if (raw <= 0 || double.IsNaN(raw)) return 1;
            double mag = Math.Pow(10, Math.Floor(Math.Log10(raw)));
            double f = raw / mag;
            return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
        }

        private static double NiceTimeStep(double raw)
        {
            double[] steps = { 60, 120, 300, 600, 900, 1200, 1800, 3600, 7200 };
            foreach (var s in steps) if (s >= raw) return s;
            return 7200;
        }

        public static string TimeLabel(double seconds)
        {
            int s = (int)Math.Round(seconds);
            return (s / 3600).ToString("0", CultureInfo.InvariantCulture) + ":" + (s / 60 % 60).ToString("00", CultureInfo.InvariantCulture);
        }
    }
}
