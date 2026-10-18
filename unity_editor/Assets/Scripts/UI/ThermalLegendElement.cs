using Neram.Core;
using UnityEngine;
using UnityEngine.UIElements;

namespace Neram.Unity
{
    /// <summary>Colour bar of the Thermal View (ThermalScale, 34-38 °C) with a marker at the current patient-level signal.
    /// Labels and the marker are child elements created once in the constructor; the repaint only paints the gradient.</summary>
    public sealed class ThermalLegendElement : VisualElement
    {
        private readonly VisualElement _marker;
        private double _value = double.NaN;

        public ThermalLegendElement()
        {
            AddToClassList("thermal-bar");
            generateVisualContent += Draw;
            _marker = new VisualElement { pickingMode = PickingMode.Ignore };
            _marker.AddToClassList("thermal-marker");
            Add(_marker);
            var lo = new Label(ThermalScale.Min.ToString("0") + " °C") { pickingMode = PickingMode.Ignore };
            lo.AddToClassList("thermal-tick");
            lo.style.left = 0;
            Add(lo);
            var hi = new Label(ThermalScale.Max.ToString("0") + " °C") { pickingMode = PickingMode.Ignore };
            hi.AddToClassList("thermal-tick");
            hi.style.right = 0;
            Add(hi);
            RegisterCallback<GeometryChangedEvent>(_ => PlaceMarker());
        }

        public void SetValue(double celsius)
        {
            _value = celsius;
            PlaceMarker();
        }

        private void PlaceMarker()
        {
            var p = ThermalScale.Position(_value);
            float w = contentRect.width;
            if (double.IsNaN(p) || float.IsNaN(w) || w <= 0) { _marker.style.display = DisplayStyle.None; return; }
            _marker.style.display = DisplayStyle.Flex;
            _marker.style.left = (float)p * w - 1f;
        }

        private void Draw(MeshGenerationContext mgc)
        {
            var r = contentRect;
            if (r.width <= 0 || r.height <= 0) return;
            var p = mgc.painter2D;
            const int n = 48;
            float h = Mathf.Min(10f, r.height);
            for (int i = 0; i < n; i++)
            {
                double c = ThermalScale.Min + (ThermalScale.Max - ThermalScale.Min) * (i + 0.5) / n;
                ThermalScale.Color(c, out var cr, out var cg, out var cb);
                p.fillColor = new Color((float)cr, (float)cg, (float)cb, 1f);
                float x0 = r.width * i / n, x1 = r.width * (i + 1) / n + 0.5f;
                p.BeginPath();
                p.MoveTo(new Vector2(x0, 0));
                p.LineTo(new Vector2(x1, 0));
                p.LineTo(new Vector2(x1, h));
                p.LineTo(new Vector2(x0, h));
                p.ClosePath();
                p.Fill();
            }
        }
    }
}
