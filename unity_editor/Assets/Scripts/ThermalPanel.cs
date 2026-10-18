using System;
using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Thermal panel: rolling 60-minute chart of the patient temperature signal (observations), the twin estimate with
    /// uncertainty, thresholds, flags, state-transition markers and the forecast region. Display only.
    /// </summary>
    public sealed class ThermalPanel : IReplayView
    {
        private readonly ThermalChartElement _chart;
        private readonly SourceBadge _obsBadge, _twinBadge, _plantBadge;
        private readonly Button _tgBand, _tgFlags, _tgCompare, _tgAuto;
        private readonly VisualElement _legend;
        private ReplaySession _s;

        /// <summary>(minute start frame) clicked in the chart: shown in the diagnostic inspector.</summary>
        public event Action<int> PointInspected;

        public ThermalPanel(VisualElement root)
        {
            var host = UiUtil.Req<VisualElement>(root, "thermal-chart-host");
            _chart = new ThermalChartElement();
            _chart.style.flexGrow = 1;
            host.Add(_chart);
            _chart.PointClicked += f => PointInspected?.Invoke(f);

            var src = UiUtil.Req<VisualElement>(root, "thermal-src");
            _obsBadge = new SourceBadge("obs");
            _twinBadge = new SourceBadge("twin");
            _plantBadge = new SourceBadge("plant");
            src.Add(_obsBadge.Root);
            src.Add(_twinBadge.Root);
            src.Add(_plantBadge.Root);

            _legend = UiUtil.Req<VisualElement>(root, "thermal-legend");
            BuildLegend();

            _tgBand = UiUtil.Req<Button>(root, "tg-uncertainty");
            _tgFlags = UiUtil.Req<Button>(root, "tg-flags");
            _tgCompare = UiUtil.Req<Button>(root, "tg-compare");
            _tgAuto = UiUtil.Req<Button>(root, "tg-autoscale");
            _tgBand.clicked += () => Toggle(_tgBand, ref _chart.ShowBand);
            _tgFlags.clicked += () => Toggle(_tgFlags, ref _chart.ShowFlags);
            _tgCompare.clicked += () => { Toggle(_tgCompare, ref _chart.ShowCompare); RebuildLegend(); };
            _tgAuto.clicked += () => Toggle(_tgAuto, ref _chart.AutoScale);
            _tgCompare.tooltip = "Shows T_plant (synthetic signal including the ASSUMED warming response) and T_plant - dT_heat (derived: the same synthetic signal without the ASSUMED warming contribution). " +
                                 "Not a measured or predicted clinical benefit.";
        }

        private void Toggle(Button b, ref bool flag)
        {
            flag = !flag;
            b.EnableInClassList("selected", flag);
            if (_s != null) ShowFrame(_lastFrame);
        }

        private int _lastFrame;

        private void BuildLegend()
        {
            _legend.Clear();
            // Short labels so the legend stays at most two rows and chart B keeps its plot height (seen in Unity 6000.3:
            // the long v3 labels wrapped to five rows and squeezed the plot). Full meanings are in the toggles' tooltips.
            AddLegend("legend-dot", new Color32(230, 234, 240, 255), "T_obs (1/min)");
            AddLegend("legend-swatch", new Color32(96, 165, 250, 255), "T_est ±1 SD");
            AddLegend("legend-dot", new Color32(251, 146, 60, 255), "artefact?");
            AddLegend("legend-swatch", new Color32(236, 72, 153, 255), "level shift?");
            AddLegend("legend-swatch", new Color32(167, 139, 250, 255), "forecast 80/95 %");
            AddLegend("legend-swatch", new Color32(107, 118, 132, 255), "□ missing");
        }

        /// <summary>Base legend plus the two ASSUMED comparison entries, only while the comparison is shown.</summary>
        private void RebuildLegend()
        {
            BuildLegend();
            if (_chart.HasPlant && _chart.ShowCompare)
            {
                AddLegend("legend-swatch", new Color32(251, 191, 36, 255), "T_plant (ASSUMED response)");
                AddLegend("legend-swatch", new Color32(148, 163, 184, 255), "T_plant \u2212 dT_heat");
            }
        }

        private void AddLegend(string shapeClass, Color c, string text)
        {
            var item = UiUtil.Box("legend-item");
            var sw = UiUtil.Box(shapeClass);
            sw.style.backgroundColor = c;
            item.Add(sw);
            item.Add(UiUtil.Label(text, "legend-text"));
            _legend.Add(item);
        }

        /// <summary>Label scale of graph B (v4 MONITOR screen: 1.3).</summary>
        public void SetTextScale(float scale) => _chart.TextScale = scale;

        public void Bind(ReplaySession s)
        {
            _s = s;
            _lastFrame = 0;
            _chart.Bind(s);
            if (!_chart.HasPlant && _chart.ShowCompare)
            {
                _chart.ShowCompare = false;
                _tgCompare.EnableInClassList("selected", false);
            }
            _tgCompare.SetEnabled(_chart.HasPlant);
            _tgCompare.text = _chart.HasPlant ? "ASSUMED compare" : "Compare: n/a (open loop)";
            RebuildLegend();
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            _lastFrame = frame;
            _chart.SetFrame(frame, ForecastRules.Compute(_s, frame));
            _obsBadge.Set(_s, "obs", frame);
            _twinBadge.Set(_s, "twin", frame);
            _plantBadge.Set(_s, "plant", frame);
        }

        public void Unbind()
        {
            _s = null;
            _chart.Unbind();
            BuildLegend();
        }
    }
}
