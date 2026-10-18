using System.Collections.Generic;
using System.Globalization;

namespace Neram.Core
{
    // View-models are pure functions of (session, frame). They translate replay values into what the UI shows.
    // They contain DISPLAY rules only (what to show, how to label it). They never compute a controller decision,
    // a twin estimate or a physiological quantity.

    public sealed class HorizonView
    {
        public int Minutes;
        public double Mean, L80, U80, L95, U95, PBelow;
        /// <summary>+60 min is information only in the plan: it can raise an alert but never trigger heating.</summary>
        public bool InformationOnly;
    }

    public sealed class ForecastView
    {
        public bool Visible;
        /// <summary>Shown instead of the fan when Visible is false.</summary>
        public string HiddenMessage;
        /// <summary>"Forecast", "No-intervention forecast" or "Forecast under ASSUMED warming".</summary>
        public string Label;
        /// <summary>Extra provenance line, e.g. that twin values come from a stand-in.</summary>
        public string Provenance;
        public readonly HorizonView[] Horizons = { new HorizonView(), new HorizonView(), new HorizonView() };
        public double NowEstimate;
    }

    public static class ForecastRules
    {
        public const string LabelPlain = "Forecast";
        public const string LabelNoIntervention = "No-intervention forecast";
        public const string LabelAssumedWarming = "Forecast under ASSUMED warming";
        public const string MsgDegradedMonitor = "Twin unreliable — monitoring only";
        public const string MsgDegradedClinician = "Twin unreliable — clinician fixed demand only; no autonomous warming";
        public const string MsgInitialising = "Twin initialising — no forecast yet";
        public const string MsgNoData = "No twin data";
        public const string MsgTwinDegradedValidity = "Twin validity DEGRADED — forecast hidden";

        /// <summary>
        /// Plan rules: the forecast is hidden unless Twin_Valid is VALID (4K) and is hidden in TWIN_DEGRADED (section 15).
        /// When any heating command is &gt; 0 the label says what the forecast does NOT know: open loop and stand-in
        /// forecasts are no-intervention forecasts; only TWIN_IN_LOOP forecasts include the ASSUMED warming input.
        /// </summary>
        public static ForecastView Compute(ReplaySession s, int frame)
        {
            var t = s.Table;
            var f = s.F;
            var v = new ForecastView();
            int tv = t.GetInt(f.TwinValid, frame);
            int st = t.GetInt(f.State, frame);
            v.NowEstimate = t.Get(f.TEst, frame);
            if (st == s.StDegraded)
            {
                v.Visible = false;
                v.HiddenMessage = t.GetInt(f.Substate, frame) == s.SubClinicianFixed ? MsgDegradedClinician : MsgDegradedMonitor;
            }
            else if (tv != s.TvValid)
            {
                v.Visible = false;
                v.HiddenMessage = tv == s.TvInitialising ? MsgInitialising : tv == s.TvNoData ? MsgNoData : MsgTwinDegradedValidity;
            }
            else v.Visible = true;

            var mode = t.GetString(f.PlantMode, frame);
            if (!s.AnyHeat(frame)) v.Label = LabelPlain;
            else v.Label = mode == "TWIN_IN_LOOP" ? LabelAssumedWarming : LabelNoIntervention;

            if (s.Tag("twin", frame) == "SIMULATED")
                v.Provenance = mode == "STANDIN" ? "Twin stand-in values (SIMULATED) — not the NERAM twin" : "Simulated twin values — not the NERAM twin";
            else v.Provenance = "NERAM twin output (MODEL)";

            for (int h = 0; h < 3; h++)
            {
                var hv = v.Horizons[h];
                hv.Minutes = ReplayFields.Horizons[h];
                hv.InformationOnly = hv.Minutes == 60;
                hv.Mean = t.Get(f.PredMean[h], frame);
                hv.L80 = t.Get(f.L80[h], frame);
                hv.U80 = t.Get(f.U80[h], frame);
                hv.L95 = t.Get(f.L95[h], frame);
                hv.U95 = t.Get(f.U95[h], frame);
                hv.PBelow = t.Get(f.PBelow[h], frame);
            }
            return v;
        }
    }

    public enum ChannelStatus { Off, Heating, Fault, Disconnected, Cutoff, Shutdown }

    public sealed class ChannelView
    {
        public int Channel;
        public string Limb;
        public ChannelStatus Status;
        public string StatusText;
        public double Heat, TempA, TempB, Current;
        public bool Connected, Cutoff;
        public int FaultCode;
        public string FaultText;
    }

    public static class ChannelRules
    {
        public static readonly string[] Limbs = { "Left hand", "Right hand", "Left foot", "Right foot" };
        public static readonly string[] ModuleNames = { "Left_Hand_Module", "Right_Hand_Module", "Left_Foot_Module", "Right_Foot_Module" };

        /// <summary>Display classification of one channel from the replayed signals (priority: shutdown, hardware cutoff,
        /// disconnected, fault, heating, off). It does not change or infer any controller output.</summary>
        public static ChannelView Compute(ReplaySession s, int frame, int channel)
        {
            var t = s.Table;
            var f = s.F;
            int i = channel - 1;
            var v = new ChannelView
            {
                Channel = channel,
                Limb = Limbs[i],
                Heat = t.Get(f.Heat[i], frame),
                TempA = t.Get(f.TempA[i], frame),
                TempB = t.Get(f.TempB[i], frame),
                Current = t.Get(f.Current[i], frame),
                Connected = t.GetBool(f.Connected[i], frame),
                Cutoff = t.GetBool(f.Cutoff[i], frame),
                FaultCode = t.GetInt(f.ChannelFault[i], frame),
            };
            v.FaultText = v.FaultCode > 0 ? s.Faults.Describe(v.FaultCode) : null;
            if (t.GetBool(f.SafetyShutdown, frame)) { v.Status = ChannelStatus.Shutdown; v.StatusText = "OFF — safety shutdown"; }
            else if (v.Cutoff) { v.Status = ChannelStatus.Cutoff; v.StatusText = "HW CUTOFF"; }
            else if (!v.Connected) { v.Status = ChannelStatus.Disconnected; v.StatusText = "DISCONNECTED"; }
            else if (v.FaultCode > 0) { v.Status = ChannelStatus.Fault; v.StatusText = "FAULT " + v.FaultCode.ToString(CultureInfo.InvariantCulture); }
            else if (v.Heat > 0) { v.Status = ChannelStatus.Heating; v.StatusText = "HEATING " + Fmt.Number(v.Heat, 0) + " %"; }
            else { v.Status = ChannelStatus.Off; v.StatusText = "OFF"; }
            return v;
        }
    }

    public enum ResetState { None, AwaitingReset, Blocked, Released }

    public sealed class SafetyView
    {
        public bool InShutdown;
        public string Title;
        public int FaultCode;
        public string FaultName;
        public string FaultText;
        public string AlertText;
        public readonly List<string> AffectedChannels = new List<string>();
        public ResetState Reset;
        public string ResetText;
        public double LatchedAtT = double.NaN;
        public double ReleasedAtT = double.NaN;
        /// <summary>Channel faults latched while the system is NOT in shutdown.</summary>
        public readonly List<string> ChannelFaults = new List<string>();
        public bool FaultLatched;
    }

    public static class SafetyRules
    {
        public const string ShutdownTitle = "SAFETY SHUTDOWN — LATCHED";
        /// <summary>How long after a release the banner keeps saying "released" (display only, frames).</summary>
        public const int ReleasedNoticeFrames = 30;

        public static SafetyView Compute(ReplaySession s, int frame)
        {
            var t = s.Table;
            var f = s.F;
            var v = new SafetyView
            {
                InShutdown = t.GetBool(f.SafetyShutdown, frame),
                FaultLatched = t.GetBool(f.FaultLatched, frame),
                FaultCode = t.GetInt(f.FaultCode, frame),
            };
            v.FaultName = s.Faults.NameOf(v.FaultCode);
            v.FaultText = s.Faults.Describe(v.FaultCode);
            int alert = t.GetInt(f.Alert, frame);
            v.AlertText = s.Enums.LabelOf(EnumNames.AlertCode, alert);
            for (int i = 0; i < 4; i++)
            {
                int c = t.GetInt(f.ChannelFault[i], frame);
                bool cut = t.GetBool(f.Cutoff[i], frame);
                if (c > 0 || cut)
                {
                    var txt = "CH" + (i + 1) + " " + ChannelRules.Limbs[i] + ": " + (c > 0 ? c + " " + s.Faults.Describe(c) : "") + (cut ? (c > 0 ? "; " : "") + "hardware cutoff tripped" : "");
                    if (v.InShutdown) v.AffectedChannels.Add(txt); else v.ChannelFaults.Add(txt);
                }
            }
            if (v.InShutdown)
            {
                v.Title = ShutdownTitle;
                var enter = s.Events.LastOfKind(frame, EventKind.SafetyShutdownEnter);
                if (enter != null) v.LatchedAtT = enter.T;
                if (alert == s.AlertResetBlocked) { v.Reset = ResetState.Blocked; v.ResetText = "Reset blocked — condition still present"; }
                else { v.Reset = ResetState.AwaitingReset; v.ResetText = "Latched — awaiting clinician RESET"; }
            }
            else
            {
                var exit = s.Events.LastOfKind(frame, EventKind.SafetyShutdownExit);
                if (exit != null && frame - exit.Frame <= ReleasedNoticeFrames)
                {
                    v.Reset = ResetState.Released;
                    v.ReleasedAtT = exit.T;
                    v.ResetText = "Safety shutdown released at " + Fmt.Time(exit.T) + " (" + exit.Detail + ")";
                }
            }
            return v;
        }
    }

    public enum BannerTone { Neutral, Warming, Degraded, Critical }

    public sealed class ControllerBannerView
    {
        public string StateName, StateLabel, StateDescription, SubstateLabel, ReasonLabel, AlertLabel, AlertSeverity;
        public BannerTone Tone;
        public bool SafetyShutdown, FaultLatched, ClinicianMode;
        /// <summary>NaN when the replay does not carry Data_Stale_* (optional fields).</summary>
        public double DataStaleTwin = double.NaN, DataStaleHw = double.NaN;
        public double SinceT = double.NaN;
    }

    public static class BannerRules
    {
        public static ControllerBannerView Compute(ReplaySession s, int frame)
        {
            var t = s.Table;
            var f = s.F;
            int st = t.GetInt(f.State, frame);
            var ev = s.Enums.Find(EnumNames.ControllerState, st);
            var v = new ControllerBannerView
            {
                StateName = s.Enums.NameOf(EnumNames.ControllerState, st),
                StateLabel = ev != null ? ev.Label : "Unknown",
                StateDescription = ev?.Description,
                ReasonLabel = s.Enums.LabelOf(EnumNames.TriggerReason, t.GetInt(f.Reason, frame)),
                SafetyShutdown = t.GetBool(f.SafetyShutdown, frame),
                FaultLatched = t.GetBool(f.FaultLatched, frame),
                ClinicianMode = t.GetBool(f.ClinicianMode, frame),
                DataStaleTwin = t.Get(f.DataStaleTwin, frame),
                DataStaleHw = t.Get(f.DataStaleHw, frame),
            };
            int sub = t.GetInt(f.Substate, frame);
            v.SubstateLabel = sub == s.SubNone ? null : s.Enums.LabelOf(EnumNames.DegradedSubstate, sub);
            var a = s.Enums.Find(EnumNames.AlertCode, t.GetInt(f.Alert, frame));
            v.AlertLabel = a != null ? a.Label : "Unknown alert";
            v.AlertSeverity = a != null ? a.Severity ?? "none" : "warning";
            if (st == s.StShutdown) v.Tone = BannerTone.Critical;
            else if (st == s.StDegraded) v.Tone = BannerTone.Degraded;
            else if (st == s.StNormal) v.Tone = BannerTone.Neutral;
            else v.Tone = BannerTone.Warming;
            var last = s.Events.LastOfKind(frame, EventKind.StateChange);
            v.SinceT = last != null ? last.T : t.StartTime;
            return v;
        }
    }

    public enum ThermalBand { Unknown, NoThresholds, BelowHypo, BetweenHypoAndTarget, AtOrAboveTarget, AboveHypoNoTarget }

    public sealed class ThermalStateView
    {
        public double Estimate, Sd;
        public ThermalBand Band;
        public string BandText;
        public string ThresholdNote;
        public double THypo = double.NaN, TTarget = double.NaN;
    }

    public static class ThermalRules
    {
        /// <summary>Display banding of T_est against t_hypo / t_target as loaded from configuration. The colour band is a
        /// display aid; it is not a clinical classification. Thresholds that are TBD or placeholders are labelled.</summary>
        public static ThermalStateView Compute(ReplaySession s, int frame)
        {
            var t = s.Table;
            var v = new ThermalStateView { Estimate = t.Get(s.F.TEst, frame), Sd = t.Get(s.F.TEstSd, frame) };
            var hypo = s.THypo;
            var target = s.TTarget;
            v.THypo = hypo != null ? hypo.EffectiveScalar : double.NaN;
            v.TTarget = target != null ? target.EffectiveScalar : double.NaN;
            var notes = new List<string>();
            if (hypo == null || double.IsNaN(v.THypo)) notes.Add("t_hypo not established");
            else if (hypo.IsPlaceholderInUse) notes.Add("t_hypo " + Fmt.Number(v.THypo, 1) + " °C is a PLACEHOLDER (" + hypo.Status + ")");
            if (target == null || double.IsNaN(v.TTarget)) notes.Add("t_target not established (" + (target?.Status ?? "missing") + ")");
            else if (target.IsPlaceholderInUse) notes.Add("t_target " + Fmt.Number(v.TTarget, 1) + " °C is a PLACEHOLDER (" + target.Status + ")");
            v.ThresholdNote = notes.Count == 0 ? "thresholds from " + (hypo?.Origin ?? "config") : string.Join("; ", notes);

            if (double.IsNaN(v.Estimate)) { v.Band = ThermalBand.Unknown; v.BandText = "No estimate"; }
            else if (double.IsNaN(v.THypo)) { v.Band = ThermalBand.NoThresholds; v.BandText = "Thresholds not established"; }
            else if (v.Estimate < v.THypo) { v.Band = ThermalBand.BelowHypo; v.BandText = "Below t_hypo"; }
            else if (double.IsNaN(v.TTarget)) { v.Band = ThermalBand.AboveHypoNoTarget; v.BandText = "At or above t_hypo (t_target not established)"; }
            else if (v.Estimate < v.TTarget) { v.Band = ThermalBand.BetweenHypoAndTarget; v.BandText = "Between t_hypo and t_target"; }
            else { v.Band = ThermalBand.AtOrAboveTarget; v.BandText = "At or above t_target"; }
            return v;
        }
    }

    public sealed class ProvenanceEntry
    {
        public string Group;
        public string Tag;
        public string Meaning;
    }

    public static class ProvenanceRules
    {
        public static readonly string[] Groups = { "obs", "twin", "ctrl", "hw", "plant" };
        public static readonly string[] GroupTitles = { "Observation", "Twin", "Controller", "Hardware", "Plant" };

        public static List<ProvenanceEntry> Compute(ReplaySession s, int frame)
        {
            var list = new List<ProvenanceEntry>(5);
            for (int i = 0; i < Groups.Length; i++)
            {
                var tag = s.Tag(Groups[i], frame);
                list.Add(new ProvenanceEntry { Group = GroupTitles[i], Tag = tag, Meaning = Meaning(Groups[i], tag, s, frame) });
            }
            return list;
        }

        public static string Meaning(string group, string tag, ReplaySession s, int frame)
        {
            switch (group)
            {
                case "obs": return tag == "REAL_DEV" ? "Development-set VitalDB patient temperature signal (site not established)" : "Synthetic patient temperature signal";
                case "twin": return tag == "MODEL" ? "NERAM robust state-space twin output" : "Simulated / stand-in twin values, not the NERAM twin";
                case "ctrl": return "Controller log (external Simulink/Stateflow or scripted); simulated, clinician-supervised prototype";
                case "hw": return "Hardware signals are simulated; no physical hardware in the loop";
                case "plant":
                    var mode = s.Table.GetString(s.F.PlantMode, frame);
                    return mode == "OPEN_LOOP" ? "Open loop: no warming effect is applied" : "SIMULATED / ASSUMED PROTOTYPE RESPONSE (assumed warming equation)";
                default: return tag;
            }
        }
    }
}
