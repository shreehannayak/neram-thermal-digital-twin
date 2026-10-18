using System;
using System.Collections.Generic;
using System.Globalization;

namespace Neram.Core
{
    public enum EventKind
    {
        StateChange,
        AlertRaised,
        SafetyShutdownEnter,
        SafetyShutdownExit,
        SystemFault,
        ChannelFaultSet,
        ChannelFaultCleared,
        HwCutoff,
        ModuleDisconnected,
        ModuleReconnected,
        TwinValidChange,
        ClinicianStart,
        ClinicianStop,
        ClinicianReset,
        FlagOutlier,
        FlagLevelShift,
        DataStaleTwin,
        DataStaleHw,
        PlantModeChange,
    }

    [Flags]
    public enum EventCategory
    {
        None = 0,
        Transition = 1,
        Fault = 2,
        Safety = 4,
        Twin = 8,
        Clinician = 16,
        Flag = 32,
        Alert = 64,
        All = 127,
    }

    public enum EventSeverity { Info, Warning, Critical }

    /// <summary>A bookmark derived from changes in replay columns. Events describe what the data says happened;
    /// they never add a decision the external controller did not make.</summary>
    public sealed class ReplayEvent
    {
        public int Frame;
        public double T;
        public EventKind Kind;
        public EventCategory Category;
        public EventSeverity Severity;
        public string Title;
        public string Detail;
        /// <summary>Channel 1-4, or 0 when not channel-specific.</summary>
        public int Channel;
        public int Code;
        /// <summary>Model probability for flag events (NaN otherwise).</summary>
        public double Probability = double.NaN;
        /// <summary>True when the event was inferred (e.g. a clinician press inferred from Trigger_Reason because
        /// the replay does not carry the optional Clinician_* fields).</summary>
        public bool Inferred;

        public override string ToString() => Fmt.Time(T) + " " + Title + (Detail != null ? " - " + Detail : "");
    }

    public sealed class EventIndex
    {
        private readonly List<ReplayEvent> _events = new List<ReplayEvent>();
        public IReadOnlyList<ReplayEvent> All => _events;
        public bool ClinicianPressesInferred { get; private set; }

        public static EventIndex Build(ReplayTable t, EnumRegistry enums, FaultCodeTable faults, DisplayConfig display)
        {
            var idx = new EventIndex();
            idx.BuildInternal(t, enums, faults, display);
            idx._events.Sort((a, b) => a.Frame != b.Frame ? a.Frame.CompareTo(b.Frame) : a.Kind.CompareTo(b.Kind));
            return idx;
        }

        private void Add(ReplayTable t, int frame, EventKind kind, EventCategory cat, EventSeverity sev, string title, string detail,
            int channel = 0, int code = 0, double p = double.NaN, bool inferred = false)
        {
            _events.Add(new ReplayEvent
            {
                Frame = frame, T = t.T[frame], Kind = kind, Category = cat, Severity = sev, Title = title, Detail = detail,
                Channel = channel, Code = code, Probability = p, Inferred = inferred,
            });
        }

        private void BuildInternal(ReplayTable t, EnumRegistry enums, FaultCodeTable faults, DisplayConfig display)
        {
            var fState = ReplayFields.Get("ctrl", "Controller_State");
            var fReason = ReplayFields.Get("ctrl", "Trigger_Reason");
            var fAlert = ReplayFields.Get("ctrl", "Alert");
            var fSafety = ReplayFields.Get("ctrl", "Safety_Shutdown");
            var fFault = ReplayFields.Get("ctrl", "fault_code");
            var fMode = ReplayFields.Get("ctrl", "Clinician_Mode");
            var fTv = ReplayFields.Get("twin", "Twin_Valid");
            var fPo = ReplayFields.Get("twin", "P_outlier");
            var fPl = ReplayFields.Get("twin", "P_level_shift");
            var fPlant = ReplayFields.Get("plant", "plant_mode");
            var fStaleT = ReplayFields.Get("ctrl", "Data_Stale_Twin");
            var fStaleH = ReplayFields.Get("ctrl", "Data_Stale_HW");
            var fStart = ReplayFields.Get("ctrl", "Clinician_Start");
            var fStop = ReplayFields.Get("ctrl", "Clinician_Stop");
            var fReset = ReplayFields.Get("ctrl", "Clinician_Reset");
            var chFault = new FieldDef[4];
            var cutoff = new FieldDef[4];
            var conn = new FieldDef[4];
            for (int i = 0; i < 4; i++)
            {
                chFault[i] = ReplayFields.Get("ctrl", "Channel_Fault_" + (i + 1));
                cutoff[i] = ReplayFields.Get("hw", "HW_Cutoff_" + (i + 1));
                conn[i] = ReplayFields.Get("hw", "Module_Connected_" + (i + 1));
            }
            int reasonStart = enums.ValueOf(EnumNames.TriggerReason, "CLINICIAN_START");
            int reasonStop = enums.ValueOf(EnumNames.TriggerReason, "CLINICIAN_STOP");
            int reasonReset = enums.ValueOf(EnumNames.TriggerReason, "CLINICIAN_RESET");
            int alertResetBlocked = enums.ValueOf(EnumNames.AlertCode, "RESET_BLOCKED");
            int alertNone = enums.ValueOf(EnumNames.AlertCode, "NONE");

            bool hasPressFields = HasAnyValue(t, fStart) || HasAnyValue(t, fStop) || HasAnyValue(t, fReset);
            ClinicianPressesInferred = !hasPressFields;

            for (int f = 0; f < t.FrameCount; f++)
            {
                bool first = f == 0;
                int st = t.GetInt(fState, f);
                int prevSt = first ? st : t.GetInt(fState, f - 1);
                int reason = t.GetInt(fReason, f);
                if (!first && st != prevSt)
                {
                    var sev = enums.NameOf(EnumNames.ControllerState, st) == "SAFETY_SHUTDOWN" ? EventSeverity.Critical : EventSeverity.Info;
                    Add(t, f, EventKind.StateChange, EventCategory.Transition, sev,
                        enums.NameOf(EnumNames.ControllerState, prevSt) + " → " + enums.NameOf(EnumNames.ControllerState, st),
                        "reason: " + enums.LabelOf(EnumNames.TriggerReason, reason));
                    if (!hasPressFields)
                    {
                        if (reason == reasonStart) Add(t, f, EventKind.ClinicianStart, EventCategory.Clinician, EventSeverity.Info, "Clinician START", "inferred from Trigger_Reason", inferred: true);
                        else if (reason == reasonStop) Add(t, f, EventKind.ClinicianStop, EventCategory.Clinician, EventSeverity.Info, "Clinician STOP", "inferred from Trigger_Reason", inferred: true);
                        else if (reason == reasonReset) Add(t, f, EventKind.ClinicianReset, EventCategory.Clinician, EventSeverity.Info, "Clinician RESET (released)", "inferred from Trigger_Reason", inferred: true);
                    }
                }
                if (!hasPressFields && !first && t.GetBool(fMode, f) && !t.GetBool(fMode, f - 1) && !(st != prevSt && reason == reasonStart))
                    Add(t, f, EventKind.ClinicianStart, EventCategory.Clinician, EventSeverity.Info, "Clinician START", "inferred from Clinician_Mode rising", inferred: true);

                if (hasPressFields)
                {
                    if (Rising(t, fStart, f)) Add(t, f, EventKind.ClinicianStart, EventCategory.Clinician, EventSeverity.Info, "Clinician START", null);
                    if (Rising(t, fStop, f)) Add(t, f, EventKind.ClinicianStop, EventCategory.Clinician, EventSeverity.Info, "Clinician STOP", null);
                    if (Rising(t, fReset, f)) Add(t, f, EventKind.ClinicianReset, EventCategory.Clinician, EventSeverity.Info, "Clinician RESET", null);
                }

                int alert = t.GetInt(fAlert, f);
                int prevAlert = first ? alertNone : t.GetInt(fAlert, f - 1);
                if (alert != prevAlert && alert != alertNone)
                {
                    var a = enums.Find(EnumNames.AlertCode, alert);
                    var sev = a != null && a.Severity == "critical" ? EventSeverity.Critical : a != null && a.Severity == "warning" ? EventSeverity.Warning : EventSeverity.Info;
                    Add(t, f, EventKind.AlertRaised, EventCategory.Alert, sev, "Alert: " + enums.LabelOf(EnumNames.AlertCode, alert), null, code: alert);
                    if (alert == alertResetBlocked && !hasPressFields)
                        Add(t, f, EventKind.ClinicianReset, EventCategory.Clinician, EventSeverity.Warning, "Clinician RESET (blocked)", "inferred from Alert RESET_BLOCKED", inferred: true);
                }

                bool sd = t.GetBool(fSafety, f);
                bool prevSd = !first && t.GetBool(fSafety, f - 1);
                if (sd && !prevSd) Add(t, f, EventKind.SafetyShutdownEnter, EventCategory.Safety, EventSeverity.Critical, "SAFETY SHUTDOWN (latched)", faults.Describe(t.GetInt(fFault, f)), code: t.GetInt(fFault, f));
                if (!sd && prevSd) Add(t, f, EventKind.SafetyShutdownExit, EventCategory.Safety, EventSeverity.Info, "Safety shutdown released", "reason: " + enums.LabelOf(EnumNames.TriggerReason, reason));

                int fc = t.GetInt(fFault, f);
                int prevFc = first ? 0 : t.GetInt(fFault, f - 1);
                if (fc != prevFc && fc > 0 && fc < 100)
                    Add(t, f, EventKind.SystemFault, EventCategory.Fault, EventSeverity.Critical, "System fault " + fc + " " + faults.NameOf(fc), faults.Describe(fc), code: fc);

                for (int i = 0; i < 4; i++)
                {
                    int c = t.GetInt(chFault[i], f);
                    int pc = first ? 0 : t.GetInt(chFault[i], f - 1);
                    if (c != pc && c != 0)
                        Add(t, f, EventKind.ChannelFaultSet, EventCategory.Fault, EventSeverity.Warning, "CH" + (i + 1) + " fault " + c + " " + faults.NameOf(c), faults.Describe(c), i + 1, c);
                    if (c == 0 && pc != 0)
                        Add(t, f, EventKind.ChannelFaultCleared, EventCategory.Fault, EventSeverity.Info, "CH" + (i + 1) + " fault cleared", "was " + pc + " " + faults.NameOf(pc), i + 1, pc);
                    if (t.GetBool(cutoff[i], f) && (first || !t.GetBool(cutoff[i], f - 1)))
                        Add(t, f, EventKind.HwCutoff, EventCategory.Safety | EventCategory.Fault, EventSeverity.Critical, "CH" + (i + 1) + " hardware cutoff tripped", "reported by hardware (simulated)", i + 1);
                    bool cn = t.GetBool(conn[i], f);
                    bool pcn = first || t.GetBool(conn[i], f - 1);
                    if (!cn && pcn) Add(t, f, EventKind.ModuleDisconnected, EventCategory.Fault, EventSeverity.Warning, "CH" + (i + 1) + " module disconnected", null, i + 1);
                    if (cn && !pcn) Add(t, f, EventKind.ModuleReconnected, EventCategory.Fault, EventSeverity.Info, "CH" + (i + 1) + " module reconnected", null, i + 1);
                }

                int tv = t.GetInt(fTv, f);
                if (!first && tv != t.GetInt(fTv, f - 1))
                    Add(t, f, EventKind.TwinValidChange, EventCategory.Twin, enums.NameOf(EnumNames.TwinValid, tv) == "DEGRADED" ? EventSeverity.Warning : EventSeverity.Info,
                        "Twin " + enums.NameOf(EnumNames.TwinValid, t.GetInt(fTv, f - 1)) + " → " + enums.NameOf(EnumNames.TwinValid, tv), null);

                if (Rising(t, fStaleT, f)) Add(t, f, EventKind.DataStaleTwin, EventCategory.Twin, EventSeverity.Warning, "Twin data stale", null);
                if (Rising(t, fStaleH, f)) Add(t, f, EventKind.DataStaleHw, EventCategory.Safety, EventSeverity.Critical, "Hardware data stale", null);

                if (!first && t.GetString(fPlant, f) != t.GetString(fPlant, f - 1))
                    Add(t, f, EventKind.PlantModeChange, EventCategory.Transition, EventSeverity.Info, "plant_mode " + t.GetString(fPlant, f - 1) + " → " + t.GetString(fPlant, f), null);
            }

            // Model-probability flags, evaluated once per twin update (first frame of each minute bucket).
            AddFlagRuns(t, fPo, display.FlagOutlier, EventKind.FlagOutlier, "Possible artefact");
            AddFlagRuns(t, fPl, display.FlagLevelShift, EventKind.FlagLevelShift, "Possible level shift");
        }

        private void AddFlagRuns(ReplayTable t, FieldDef f, double threshold, EventKind kind, string title)
        {
            int runStart = -1;
            double peak = 0;
            for (int m = 0; m <= t.MinuteStartFrames.Length; m++)
            {
                bool on = false;
                double p = double.NaN;
                if (m < t.MinuteStartFrames.Length)
                {
                    p = t.Get(f, t.MinuteStartFrames[m]);
                    on = !double.IsNaN(p) && p >= threshold;
                }
                if (on)
                {
                    if (runStart < 0) { runStart = m; peak = p; }
                    else if (p > peak) peak = p;
                }
                else if (runStart >= 0)
                {
                    int frame = t.MinuteStartFrames[runStart];
                    int minutes = m - runStart;
                    Add(t, frame, kind, EventCategory.Flag, EventSeverity.Info, title,
                        "model probability peak " + peak.ToString("0.00", CultureInfo.InvariantCulture) + " over " + minutes + " twin update(s); not a confirmed physiological event",
                        p: peak);
                    runStart = -1;
                }
            }
        }

        private static bool HasAnyValue(ReplayTable t, FieldDef f)
        {
            var col = t.Column(f);
            for (int i = 0; i < col.Length; i++) if (!double.IsNaN(col[i])) return true;
            return false;
        }

        private static bool Rising(ReplayTable t, FieldDef f, int frame)
        {
            if (t.IsNull(f, frame) || !t.GetBool(f, frame)) return false;
            return frame == 0 || t.IsNull(f, frame - 1) || !t.GetBool(f, frame - 1);
        }

        /// <summary>Number of events at or before the given frame.</summary>
        public int CountUpTo(int frame)
        {
            int lo = 0, hi = _events.Count;
            while (lo < hi)
            {
                int mid = (lo + hi) >> 1;
                if (_events[mid].Frame <= frame) lo = mid + 1; else hi = mid;
            }
            return lo;
        }

        /// <summary>First event strictly after the frame matching the category mask, or null.</summary>
        public ReplayEvent Next(int frame, EventCategory mask)
        {
            for (int i = CountUpTo(frame); i < _events.Count; i++)
                if ((_events[i].Category & mask) != 0) return _events[i];
            return null;
        }

        /// <summary>Last event strictly before the frame matching the category mask, or null.</summary>
        public ReplayEvent Previous(int frame, EventCategory mask)
        {
            int i = CountUpTo(frame - 1) - 1;
            for (; i >= 0; i--)
                if ((_events[i].Category & mask) != 0) return _events[i];
            return null;
        }

        /// <summary>Most recent event of a kind at or before the frame, or null.</summary>
        public ReplayEvent LastOfKind(int frame, EventKind kind)
        {
            for (int i = CountUpTo(frame) - 1; i >= 0; i--)
                if (_events[i].Kind == kind) return _events[i];
            return null;
        }
    }
}
