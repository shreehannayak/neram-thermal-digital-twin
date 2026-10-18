using System;
using System.Globalization;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Dashboard charts A and C (chart B is the rolling ThermalPanel):
    ///  A · Patient temperature signal over the whole replay: T_obs only, gaps where the replay has no observation
    ///      (shaded, never interpolated), cursor at the current frame. The signal is not called core temperature.
    ///  C · Warming-channel activity: controller heat command Heat_1..Heat_4 (%) as four lanes, cursor at the current
    ///      frame. These are controller COMMANDS from the replay (source tag shown), not measured hardware responses.
    /// Clicking a chart seeks the replay to that time.
    /// </summary>
    public sealed class ChartsPanel : IReplayView
    {
        private readonly SeriesChartElement _a, _c;
        private readonly SourceBadge _aBadge, _cBadge;
        private readonly Label _aNote, _cNote, _aValue, _cValue;
        private ReplaySession _s;

        public static readonly Color[] ChannelColors =
        {
            new Color32(45, 212, 191, 255), new Color32(34, 158, 180, 255), new Color32(245, 158, 11, 255), new Color32(234, 120, 32, 255),
        };

        public event Action<double> SeekRequested;

        public ChartsPanel(VisualElement root)
        {
            _a = new SeriesChartElement { ChartMode = SeriesChartElement.Mode.Lines, Unit = "°C", MinSpan = 1.0 };
            _a.style.flexGrow = 1;
            UiUtil.Req<VisualElement>(root, "chart-a-host").Add(_a);
            _c = new SeriesChartElement { ChartMode = SeriesChartElement.Mode.Lanes, LaneMax = 100, Unit = "%" };
            _c.style.flexGrow = 1;
            UiUtil.Req<VisualElement>(root, "chart-c-host").Add(_c);
            _a.Clicked += t => SeekRequested?.Invoke(t);
            _c.Clicked += t => SeekRequested?.Invoke(t);
            _aBadge = new SourceBadge("obs");
            _cBadge = new SourceBadge("ctrl");
            UiUtil.Req<VisualElement>(root, "chart-a-src").Add(_aBadge.Root);
            UiUtil.Req<VisualElement>(root, "chart-c-src").Add(_cBadge.Root);
            _aNote = UiUtil.Req<Label>(root, "chart-a-note");
            _cNote = UiUtil.Req<Label>(root, "chart-c-note");
            _aValue = UiUtil.Req<Label>(root, "chart-a-value");
            _cValue = UiUtil.Req<Label>(root, "chart-c-value");
            var legA = UiUtil.Req<VisualElement>(root, "chart-a-legend");
            legA.Add(LegendItem("T_obs", new Color32(230, 234, 240, 255), false));
            legA.Add(LegendItem("gap = no observation (not interpolated)", new Color(0.42f, 0.46f, 0.52f, 0.6f), true));
            var legC = UiUtil.Req<VisualElement>(root, "chart-c-legend");
            for (int i = 0; i < 4; i++) legC.Add(LegendItem("CH" + (i + 1) + " " + (i % 2 == 0 ? "L " : "R ") + (i < 2 ? "hand" : "foot"), ChannelColors[i], true));
            _aNote.text = "Measurement site not established · not core temperature";
            _cNote.text = "Replayed heat commands (0–100 %) · not measured heating";
        }

        private static VisualElement LegendItem(string text, Color c, bool block)
        {
            var item = UiUtil.Box("legend-item");
            var sw = UiUtil.Box(block ? "legend-block" : "legend-swatch");
            sw.style.backgroundColor = c;
            item.Add(sw);
            item.Add(UiUtil.Label(text, "legend-text"));
            return item;
        }

        /// <summary>Label scale of graphs A and C (v4 MONITOR screen: 1.3).</summary>
        public void SetTextScale(float scale)
        {
            _a.TextScale = scale;
            _c.TextScale = scale;
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            var t = s.Table;
            var obs = t.Column(s.F.TObs);
            var miss = new bool[t.FrameCount];
            for (int i = 0; i < t.FrameCount; i++) miss[i] = double.IsNaN(obs[i]) || t.GetBool(s.F.ObsMissing, i);
            // A missing observation is drawn as a gap even if a stale value were present in the column.
            var a = new double[t.FrameCount];
            for (int i = 0; i < t.FrameCount; i++) a[i] = miss[i] ? double.NaN : obs[i];
            _a.MissingMask = miss;
            _a.SetData(t.T, new[] { new SeriesChartElement.Series { Name = "T_obs", Values = a, Color = new Color32(230, 234, 240, 255), Width = 1.6f } });
            var lanes = new SeriesChartElement.Series[4];
            for (int ch = 0; ch < 4; ch++)
                lanes[ch] = new SeriesChartElement.Series { Name = "CH" + (ch + 1) + " " + ShortLimb(ch), Values = t.Column(s.F.Heat[ch]), Color = ChannelColors[ch] };
            _c.SetData(t.T, lanes);
            _aBadge.Set(s.Tag("obs", 0), ProvenanceRules.Meaning("obs", s.Tag("obs", 0), s, 0));
            _cBadge.Set(s.Tag("ctrl", 0), ProvenanceRules.Meaning("ctrl", s.Tag("ctrl", 0), s, 0));
        }

        private static string ShortLimb(int ch) => ch == 0 ? "L hand" : ch == 1 ? "R hand" : ch == 2 ? "L foot" : "R foot";

        public void Unbind()
        {
            _s = null;
            _a.ClearData();
            _c.ClearData();
            _aValue.text = "";
            _cValue.text = "";
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var t = _s.Table;
            double time = t.T[frame];
            string clock = Fmt.Time(time - t.StartTime);
            double obs = t.Get(_s.F.TObs, frame);
            bool missing = double.IsNaN(obs) || t.GetBool(_s.F.ObsMissing, frame);
            string obsText = missing ? "no observation at this frame" : Fmt.Value(obs, _s.F.TObs);
            _a.SetCursor(time, clock);
            _c.SetCursor(time, clock);
            _aValue.text = obsText;
            var sb = new System.Text.StringBuilder();
            for (int ch = 0; ch < 4; ch++)
            {
                if (ch > 0) sb.Append("   ");
                sb.Append("CH").Append(ch + 1).Append(' ').Append(Fmt.Number(t.Get(_s.F.Heat[ch], frame), 0)).Append(" %");
            }
            _cValue.text = sb.ToString();
            _aBadge.Set(_s.Tag("obs", frame), ProvenanceRules.Meaning("obs", _s.Tag("obs", frame), _s, frame));
            _cBadge.Set(_s.Tag("ctrl", frame), ProvenanceRules.Meaning("ctrl", _s.Tag("ctrl", frame), _s, frame));
        }
    }
}
