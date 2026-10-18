using System;
using System.Globalization;

namespace Neram.Core
{
    /// <summary>Display formatting. A missing value is always shown as an em dash, never as 0.</summary>
    public static class Fmt
    {
        public const string Missing = "—";
        private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static string Number(double v, int decimals)
        {
            if (double.IsNaN(v) || double.IsInfinity(v)) return Missing;
            return v.ToString("F" + Math.Max(0, decimals), Inv);
        }

        public static string Unit(string unit) => DisplayUnits.Of(unit);

        /// <summary>Non-breaking space placed between a number and its unit so wrapped text never separates them.</summary>
        public const string UnitSep = "\u00A0";

        /// <summary>Value with unit, e.g. "36.42 °C" (number and unit joined by a non-breaking space); "—" when null.</summary>
        public static string Value(double v, FieldDef f)
        {
            if (double.IsNaN(v)) return Missing;
            switch (f.Kind)
            {
                case FieldKind.Bool: return v > 0.5 ? "true" : "false";
                case FieldKind.Int:
                case FieldKind.Enum: return ((long)v).ToString(Inv);
            }
            var u = DisplayUnits.Of(f.Unit);
            var n = Number(v, f.Decimals);
            return u.Length == 0 ? n : n + UnitSep + u;
        }

        public static string Probability(double p) => double.IsNaN(p) ? Missing : p.ToString("0.00", Inv);

        public static string Percent(double p) => double.IsNaN(p) ? Missing : (p * 100).ToString("0", Inv) + " %";

        /// <summary>Replay time as T+hh:mm:ss (logical seconds since settled start).</summary>
        public static string Time(double seconds)
        {
            if (double.IsNaN(seconds)) return Missing;
            var neg = seconds < 0;
            var s = (long)Math.Floor(Math.Abs(seconds));
            var str = $"{s / 3600:00}:{s / 60 % 60:00}:{s % 60:00}";
            return (neg ? "T-" : "T+") + str;
        }

        /// <summary>Signed difference with arrow, e.g. "+0.12 ▲", "−0.05 ▼", "0.00 ▬".</summary>
        public static string Trend(double delta, int decimals, double deadband)
        {
            if (double.IsNaN(delta)) return Missing;
            var mag = Math.Abs(delta).ToString("F" + decimals, Inv);
            if (Math.Abs(delta) <= deadband) return "±" + mag;
            return delta > 0 ? "+" + mag + " ▲" : "−" + mag + " ▼";
        }
    }
}
