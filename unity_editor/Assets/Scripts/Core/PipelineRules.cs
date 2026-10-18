using System;
using System.Globalization;

namespace Neram.Core
{
    /// <summary>One stage of the NERAM pipeline panel (display only).</summary>
    public sealed class PipelineStage
    {
        public int Index;
        public string Title;
        public string Value;
        public string Detail;
        /// <summary>Source tag of the replay group the stage reads ("obs", "twin", "ctrl"), or "VIEW" for the visualisation stage.</summary>
        public string Tag;
        /// <summary>False when the replay has no value for this stage at this frame (shown as unavailable).</summary>
        public bool Available;
        /// <summary>Replay time (s) of the most recent change of this stage within the look-back window, NaN if none.</summary>
        public double LastChange = double.NaN;
    }

    public sealed class PipelineView
    {
        public readonly PipelineStage[] Stages = new PipelineStage[5];
        /// <summary>0-based index of the stage that changed most recently within the look-back window (-1 = nothing changed).</summary>
        public int ActiveStage = -1;
        public double[] Heat = new double[4];
    }

    /// <summary>
    /// Pipeline panel: temperature input -> state estimator -> controller decision -> warming channels -> visualisation.
    /// Every value is read from the replay at the given frame. The rules only DESCRIBE what the replay contains and which
    /// stage changed most recently; they never derive a controller decision or a heat command from temperature (the
    /// canonical model and controller run outside Unity). The warming-channel stage reports the replayed Heat_i exactly.
    /// </summary>
    public static class PipelineRules
    {
        public const double DefaultLookbackS = 60.0;
        private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static PipelineView Compute(ReplaySession s, int frame, double lookbackS = DefaultLookbackS)
        {
            var t = s.Table;
            var f = s.F;
            frame = Math.Max(0, Math.Min(frame, t.FrameCount - 1));
            var v = new PipelineView();

            // 1. temperature input
            double obs = t.Get(f.TObs, frame);
            bool missing = double.IsNaN(obs) || t.GetBool(f.ObsMissing, frame);
            v.Stages[0] = new PipelineStage
            {
                Index = 0, Title = "TEMPERATURE INPUT", Tag = s.Tag("obs", frame), Available = !missing,
                Value = missing ? "no observation" : Fmt.Value(obs, f.TObs),
                Detail = "patient temperature signal · site not established",
            };

            // 2. state estimator
            double est = t.Get(f.TEst, frame), sd = t.Get(f.TEstSd, frame), p30 = t.Get(f.PBelow[1], frame);
            var validity = s.Enums.LabelOf(EnumNames.TwinValid, t.GetInt(f.TwinValid, frame));
            v.Stages[1] = new PipelineStage
            {
                Index = 1, Title = "STATE ESTIMATOR", Tag = s.Tag("twin", frame), Available = !double.IsNaN(est),
                Value = double.IsNaN(est) ? "estimate unavailable" : Fmt.Value(est, f.TEst) + (double.IsNaN(sd) ? "" : " ± " + Fmt.Number(sd, 2)),
                Detail = validity + (double.IsNaN(p30) ? "" : " · P(below +30 min) " + Fmt.Probability(p30)),
            };

            // 3. controller decision
            var state = s.Enums.LabelOf(EnumNames.ControllerState, t.GetInt(f.State, frame));
            var reason = s.Enums.LabelOf(EnumNames.TriggerReason, t.GetInt(f.Reason, frame));
            var alertCode = t.GetInt(f.Alert, frame);
            var alert = alertCode != 0 ? s.Enums.LabelOf(EnumNames.AlertCode, alertCode) : null;
            v.Stages[2] = new PipelineStage
            {
                Index = 2, Title = "CONTROLLER DECISION", Tag = s.Tag("ctrl", frame), Available = true,
                Value = state,
                Detail = "reason: " + reason + (alert != null ? " · alert: " + alert : "") + (t.GetBool(f.SafetyShutdown, frame) ? " · SAFETY SHUTDOWN" : ""),
            };

            // 4. warming channels (replayed commands, exactly)
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < 4; i++)
            {
                v.Heat[i] = t.Get(f.Heat[i], frame);
                if (i > 0) sb.Append("  ");
                sb.Append("CH").Append(i + 1).Append(' ').Append(Fmt.Number(v.Heat[i], 0)).Append('%');
            }
            v.Stages[3] = new PipelineStage
            {
                Index = 3, Title = "WARMING CHANNELS", Tag = s.Tag("ctrl", frame), Available = true,
                Value = sb.ToString(), Detail = "replayed heat commands (not measured heating)",
            };

            // 5. visualisation
            v.Stages[4] = new PipelineStage
            {
                Index = 4, Title = "PATIENT / DEVICE VIEW", Tag = "VIEW", Available = true,
                Value = Fmt.Time(t.T[frame] - t.StartTime),
                Detail = "glow follows CH commands · charts at this frame",
            };

            // most recent change per stage inside the look-back window
            double now = t.T[frame];
            for (int k = frame; k > 0 && now - t.T[k] <= lookbackS; k--)
            {
                int j = k - 1;
                if (double.IsNaN(v.Stages[0].LastChange) && ObsChanged(t, f, k, j)) v.Stages[0].LastChange = t.T[k];
                if (double.IsNaN(v.Stages[1].LastChange) && (Diff(t.Get(f.TEst, k), t.Get(f.TEst, j)) || t.GetInt(f.TwinValid, k) != t.GetInt(f.TwinValid, j)))
                    v.Stages[1].LastChange = t.T[k];
                if (double.IsNaN(v.Stages[2].LastChange) && (t.GetInt(f.State, k) != t.GetInt(f.State, j) || t.GetInt(f.Reason, k) != t.GetInt(f.Reason, j) || t.GetInt(f.Alert, k) != t.GetInt(f.Alert, j)))
                    v.Stages[2].LastChange = t.T[k];
                if (double.IsNaN(v.Stages[3].LastChange))
                    for (int i = 0; i < 4; i++)
                        if (Diff(t.Get(f.Heat[i], k), t.Get(f.Heat[i], j))) { v.Stages[3].LastChange = t.T[k]; break; }
            }
            if (!double.IsNaN(v.Stages[3].LastChange)) v.Stages[4].LastChange = v.Stages[3].LastChange; // the view follows the commands
            double best = double.NegativeInfinity;
            for (int i = 0; i < 4; i++)
            {
                var lc = v.Stages[i].LastChange;
                if (!double.IsNaN(lc) && lc >= best) { best = lc; v.ActiveStage = i; }
            }
            return v;
        }

        private static bool ObsChanged(ReplayTable t, FrameFields f, int k, int j)
        {
            bool mk = t.GetBool(f.ObsMissing, k) || double.IsNaN(t.Get(f.TObs, k));
            bool mj = t.GetBool(f.ObsMissing, j) || double.IsNaN(t.Get(f.TObs, j));
            if (mk != mj) return true;
            return !mk && Diff(t.Get(f.TObs, k), t.Get(f.TObs, j));
        }

        private static bool Diff(double a, double b)
        {
            if (double.IsNaN(a) && double.IsNaN(b)) return false;
            if (double.IsNaN(a) || double.IsNaN(b)) return true;
            return Math.Abs(a - b) > 1e-9;
        }
    }

    /// <summary>
    /// Colour scale for the Thermal View. The body is tinted UNIFORMLY with the single patient-level signal: the replay
    /// contains no regional temperatures, so no limb or organ gets a value of its own. Palette: deep blue (cool) -> teal
    /// -> pale -> amber (warm); red is reserved for critical states and is never part of the scale.
    /// </summary>
    public static class ThermalScale
    {
        public const double Min = 34.0, Max = 38.0;
        private static readonly double[][] Stops =
        {
            new[] { 0.00, 0.10, 0.22, 0.52 }, new[] { 0.35, 0.10, 0.55, 0.62 }, new[] { 0.60, 0.70, 0.85, 0.80 },
            new[] { 0.80, 0.95, 0.80, 0.42 }, new[] { 1.00, 0.98, 0.58, 0.12 },
        };

        /// <summary>Normalised position 0..1 on the scale (clamped), NaN for a missing value.</summary>
        public static double Position(double celsius) =>
            double.IsNaN(celsius) ? double.NaN : Math.Max(0, Math.Min(1, (celsius - Min) / (Max - Min)));

        /// <summary>sRGB colour (0..1) for a value; a missing value maps to neutral grey (shown as "no observation").</summary>
        public static void Color(double celsius, out double r, out double g, out double b)
        {
            var p = Position(celsius);
            if (double.IsNaN(p)) { r = g = b = 0.55; return; }
            for (int i = 1; i < Stops.Length; i++)
            {
                if (p > Stops[i][0] && i < Stops.Length - 1) continue;
                var a = Stops[i - 1];
                var c = Stops[i];
                double u = (p - a[0]) / (c[0] - a[0]);
                u = Math.Max(0, Math.Min(1, u));
                r = a[1] + (c[1] - a[1]) * u;
                g = a[2] + (c[2] - a[2]) * u;
                b = a[3] + (c[3] - a[3]) * u;
                return;
            }
            r = g = b = 0.55;
        }
    }

    /// <summary>
    /// Navigation bounds for the Free Roam camera: keeps the camera sphere inside the room and outside keep-out boxes
    /// (patient + table, theatre equipment). Pure maths (no UnityEngine) so it is unit-tested outside Unity.
    /// </summary>
    public static class NavBounds
    {
        public struct Box
        {
            public double Cx, Cy, Cz, Hx, Hy, Hz;
            public Box(double cx, double cy, double cz, double hx, double hy, double hz) { Cx = cx; Cy = cy; Cz = cz; Hx = hx; Hy = hy; Hz = hz; }
            public bool Contains(double x, double y, double z, double pad) =>
                Math.Abs(x - Cx) < Hx + pad && Math.Abs(y - Cy) < Hy + pad && Math.Abs(z - Cz) < Hz + pad;
        }

        /// <summary>Clamp (x,y,z) into the room (minus radius) and push it out of every keep-out box along the axis of least
        /// penetration. Returns true when the position was changed.</summary>
        public static bool Resolve(ref double x, ref double y, ref double z, double radius, Box room, Box[] keepOut)
        {
            double ox = x, oy = y, oz = z;
            for (int iter = 0; iter < 3; iter++)
            {
                x = Clamp(x, room.Cx - room.Hx + radius, room.Cx + room.Hx - radius);
                y = Clamp(y, room.Cy - room.Hy + radius, room.Cy + room.Hy - radius);
                z = Clamp(z, room.Cz - room.Hz + radius, room.Cz + room.Hz - radius);
                bool moved = false;
                if (keepOut != null)
                {
                    foreach (var b in keepOut)
                    {
                        if (!b.Contains(x, y, z, radius)) continue;
                        double px = b.Hx + radius - Math.Abs(x - b.Cx);
                        double py = b.Hy + radius - Math.Abs(y - b.Cy);
                        double pz = b.Hz + radius - Math.Abs(z - b.Cz);
                        if (px <= py && px <= pz) x += (x >= b.Cx ? 1 : -1) * (px + 1e-6);
                        else if (py <= pz) y += (y >= b.Cy ? 1 : -1) * (py + 1e-6);
                        else z += (z >= b.Cz ? 1 : -1) * (pz + 1e-6);
                        moved = true;
                    }
                }
                if (!moved) break;
            }
            return x != ox || y != oy || z != oz;
        }

        private static double Clamp(double v, double lo, double hi) => lo > hi ? (lo + hi) / 2 : v < lo ? lo : v > hi ? hi : v;
    }
}
