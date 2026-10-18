using Neram.Core;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>
    /// Forecast cards for +20 / +30 / +60 min: mean, 80 % and 95 % intervals, and P(below t_hypo) as a bar.
    /// The fan itself is drawn in the thermal chart (intervals at the horizons only).
    /// Rules (ForecastRules): hidden unless Twin_Valid is VALID and the controller is not TWIN_DEGRADED; while any
    /// Heat_i > 0 the title says "No-intervention forecast" (open loop / stand-in) or "Forecast under ASSUMED warming"
    /// (twin in the loop). +60 min is labelled information only ("INFO", full text in the card tooltip).
    /// </summary>
    public sealed class ForecastFan : IReplayView
    {
        private readonly Label _title, _prov, _hidden;
        private readonly VisualElement _cards;
        private readonly SourceBadge _badge;
        private readonly Card[] _c = new Card[3];
        private ReplaySession _s;
        private string _hypoNote = "";

        private sealed class Card
        {
            public VisualElement Root, Fill;
            public Label H, Mean, I80, I95, P;
        }

        public ForecastFan(VisualElement root)
        {
            _title = UiUtil.Req<Label>(root, "forecast-title");
            _prov = UiUtil.Req<Label>(root, "forecast-prov");
            _hidden = UiUtil.Req<Label>(root, "forecast-hidden");
            _cards = UiUtil.Req<VisualElement>(root, "forecast-cards");
            _badge = new SourceBadge("twin");
            UiUtil.Req<VisualElement>(root, "forecast-src").Add(_badge.Root);
            for (int i = 0; i < 3; i++)
            {
                var c = new Card { Root = UiUtil.Box("fc-card") };
                c.H = UiUtil.Label("", "fc-h");
                c.Mean = UiUtil.Label("—", "fc-mean");
                c.I80 = UiUtil.Label("", "fc-int");
                c.I95 = UiUtil.Label("", "fc-int");
                var track = UiUtil.Box("p-track");
                c.Fill = UiUtil.Box("p-fill");
                track.Add(c.Fill);
                c.P = UiUtil.Label("", "p-text");
                c.Root.Add(c.H); c.Root.Add(c.Mean); c.Root.Add(c.I80); c.Root.Add(c.I95); c.Root.Add(track); c.Root.Add(c.P);
                _cards.Add(c.Root);
                _c[i] = c;
            }
        }

        public void Bind(ReplaySession s)
        {
            _s = s;
            var hypo = s.THypo;
            _hypoNote = hypo == null || double.IsNaN(hypo.EffectiveScalar) ? " (t_hypo not established)" :
                hypo.IsPlaceholderInUse ? " vs PLACEHOLDER t_hypo " + Fmt.Number(hypo.EffectiveScalar, 1) + " °C" : "";
        }

        public void ShowFrame(int frame)
        {
            if (_s == null) return;
            var v = ForecastRules.Compute(_s, frame);
            _badge.Set(_s, "twin", frame);
            UiUtil.SetText(_title, (v.Visible ? v.Label.ToUpperInvariant() : "FORECAST") + "  ·  +20 / +30 / +60 MIN");
            // The t_hypo status is stated once here (not in every card) so the 300-px column keeps the cards short.
            UiUtil.SetText(_prov, v.Provenance + ". Intervals at the three horizons only." + (_hypoNote.Length > 0 ? " P(<t_hypo)" + _hypoNote + "." : ""));
            UiUtil.Show(_cards, v.Visible);
            UiUtil.Show(_hidden, !v.Visible);
            if (!v.Visible)
            {
                UiUtil.SetText(_hidden, v.HiddenMessage);
                return;
            }
            for (int i = 0; i < 3; i++)
            {
                var h = v.Horizons[i];
                var c = _c[i];
                UiUtil.SetText(c.H, "+" + h.Minutes + (h.InformationOnly ? " · INFO" : " MIN"));
                UiUtil.SetText(c.Mean, Fmt.Number(h.Mean, 2) + " °C");
                // Card text is shortened to fit a 300-px column (intervals to 0.1 °C); the tooltip carries the full values.
                UiUtil.SetText(c.I80, "80% " + Fmt.Number(h.L80, 1) + "–" + Fmt.Number(h.U80, 1));
                UiUtil.SetText(c.I95, "95% " + Fmt.Number(h.L95, 1) + "–" + Fmt.Number(h.U95, 1));
                c.Fill.style.width = new StyleLength(new Length(double.IsNaN(h.PBelow) ? 0 : (float)(h.PBelow * 100), LengthUnit.Percent));
                UiUtil.SetText(c.P, "P<t_hypo " + Fmt.Probability(h.PBelow));
                c.Root.tooltip = "+" + h.Minutes + " min" + (h.InformationOnly ? " (INFORMATION ONLY)" : "") + ": mean " + Fmt.Number(h.Mean, 2) +
                                 " °C · 80 % " + Fmt.Number(h.L80, 2) + " – " + Fmt.Number(h.U80, 2) + " · 95 % " + Fmt.Number(h.L95, 2) + " – " +
                                 Fmt.Number(h.U95, 2) + " · P(below t_hypo) " + Fmt.Probability(h.PBelow) + _hypoNote;
                c.Root.EnableInClassList("fc-info", h.InformationOnly);
            }
        }

        public void Unbind()
        {
            _s = null;
            UiUtil.Show(_cards, false);
            UiUtil.Show(_hidden, true);
            UiUtil.SetText(_hidden, "No replay loaded");
        }
    }
}
